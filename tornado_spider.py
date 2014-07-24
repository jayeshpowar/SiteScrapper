import argparse
import logging
import sys
import time

from lxml import objectify
from tornado.gen import coroutine
from tornado.httpclient import HTTPClient
from tornado.ioloop import IOLoop
from toro import JoinableQueue, BoundedSemaphore

from config import DOMAINS_TO_BE_SKIPPED, START_URL, \
    IMPLEMENTATION_CLIENT, MAX_CONCURRENT_REQUESTS_PER_SERVER
from resource_issue_detector import detect_js_and_resource_issues
from tornado_client_page import TornadoClientPage
from util import print_pages_with_errors, print_pages_with_hardcoded_links, print_pages_to_file, extract_domain, \
    extract_base_site, decode_to_unicode
from web_page import WebPage


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler('spider.log', mode='w'))

RESOURCES_STATE = dict()
universal_messages = []


def _get_client_page(*args):
    if IMPLEMENTATION_CLIENT == 'tornado':
        return TornadoClientPage(*args)
    else:
        return WebPage(args)


class TornadoSpider:
    def __init__(self, start_url, sitemap_url=None, max_concurrent_connections=MAX_CONCURRENT_REQUESTS_PER_SERVER):

        self.visited_urls = set()
        self.intermediate_urls = set()
        self.base_domain = extract_domain(start_url)
        self.base_site = extract_base_site(start_url)
        self.base_page = _get_client_page(start_url, None, start_url, self.base_domain, DOMAINS_TO_BE_SKIPPED)
        self.non_visited_urls = {self.base_page}
        self.added_count = 1
        self.idle_ping = 0
        self.start_idle_counter = False
        self.sitemap_url = u'{}/sitemap.xml'.format(self.base_site) if not sitemap_url else sitemap_url
        self.max_concurrent_connections = max_concurrent_connections

        self.page_queue = JoinableQueue()
        self.semaphore = BoundedSemaphore(self.max_concurrent_connections)
        self.start = time.time()


    @coroutine
    def initiate_crawl(self):
        self.non_visited_urls.add(self.base_page)
        self.add_sitemap_urls(self.base_page)
        self.page_queue.put(self.base_page)
        self._crawl_web_page()
        yield self.page_queue.join()

    @coroutine
    def _crawl_web_page(self):
        while True:
            if len(self.intermediate_urls) < 5 and self.start_idle_counter:
                for page in self.intermediate_urls:
                    print(u'>>>>>> %s ' % page.encoded_url)
            # print("Available Semaphore %s" % self.semaphore.counter)
            yield self.semaphore.acquire()
            # print("0.Issued Semaphore %s  " % (self.semaphore.counter+1))
            self._fetch_page(self.semaphore.counter + 1)
            if len(self.intermediate_urls) < 5 and self.start_idle_counter:
                print("Unprocessed urls : ")
                for page in self.intermediate_urls:
                    print(u'>> %s ' % page.encoded_url)
                self.wrap_up()

    @coroutine
    def _fetch_page(self, semaphore_count):
        try:
            page = yield self.page_queue.get()
            if page in self.visited_urls or page in self.intermediate_urls:
                return
            logger.debug(
                u"1.Sempahore in use> %s int.count %s for %s" % (semaphore_count, len(self.intermediate_urls),
                                                                 page.encoded_url))
            self.intermediate_urls.add(page)
            page.process(self)
            response = yield page.make_head_request()
            get_response = yield page._process_head_response(response)
            if get_response:
                page.process_get_response(get_response)
            print(
                u"Total urls added :  {} , Total urls visited : {} , Total urls in process : {} semaphore used : {} " \
                .format(self.added_count, len(self.visited_urls), len(self.intermediate_urls), semaphore_count))

            logger.debug(
                u"Total urls added :  {} , Total urls visited : {} , Total urls in process : {} semaphore {} \r"
                .format(self.added_count, len(self.visited_urls), len(self.intermediate_urls),
                        self.semaphore.counter))
        except Exception as ex:
            logger.debug(ex)
        finally:
            self.page_queue.task_done()
            self.semaphore.release()
            logger.debug(
                u"2.Sempahore returned>> %s  available %s after %s" % (semaphore_count, self.semaphore.counter,
                                                                       page.encoded_url))

    def _filter_visited_links(self, page):
        return page not in self.visited_urls and page not in self.intermediate_urls

    def add_sitemap_urls(self, parent_page):
        logger.debug("Adding sitemap urls as well for processing")
        http_client = HTTPClient()
        try:
            response = http_client.fetch(self.sitemap_url)
            val = bytes(response.body)
            root = objectify.fromstring(val)

            for url_element in root.url:
                page = _get_client_page(decode_to_unicode(url_element.loc.text), parent_page, self.base_site,
                                        self.base_domain, DOMAINS_TO_BE_SKIPPED)
                if page not in self.visited_urls and page not in self.non_visited_urls \
                        and page not in self.intermediate_urls:
                    print(u"Added {}".format(url_element.loc))
                    self.non_visited_urls.add(page)
                    self.added_count += 1
                    self.page_queue.put(page)

        except Exception as e:
            logger.error(u"Error adding sitemap urls from %s " % self.sitemap_url)
        finally:
            http_client.close()

    def _get_unique_non_visited_links(self, page):
        # l = Lock()
        # l.acquire()
        filtered_links = set(filter(self._filter_visited_links, page.links))
        # l.release()
        return filtered_links

    def process_web_page(self, web_page):
        logger.debug(u"Called {} for {}".format('process_web_page', unicode(web_page.url).encode("utf-8")))
        logger.debug(u"Removing %s " % web_page.url)
        self.visited_urls.add(web_page)
        self.non_visited_urls.discard(web_page)
        self.intermediate_urls.discard(web_page)
        unique_pages = self._get_unique_non_visited_links(web_page)

        for page in unique_pages:
            if page not in self.non_visited_urls:
                self.non_visited_urls.add(page)
                self.page_queue.put(page)
                self.added_count += 1

        self.start_idle_counter = True

    def wrap_up(self):
        self.print_stats()
        IOLoop.instance().stop()
        print('Done crawling in %d seconds, fetched %s URLs.' % (time.time() - self.start, len(self.visited_urls)))

    def print_stats(self):
        print_pages_with_errors(True, self.visited_urls, "broken_external_links.txt")
        print_pages_with_errors(False, self.visited_urls, "broken_internal_links.txt")
        print_pages_with_hardcoded_links(self.visited_urls, "hardcoded_url_links.txt")

        print("\nTotal pages visited : {}\n".format(len(self.visited_urls)))

        print_pages_to_file("all_internal_pages.txt", False, self.visited_urls)
        print_pages_to_file("all_external_pages.txt", True, self.visited_urls)


def process_parameters():
    parser = argparse.ArgumentParser(description='A Simple website scrapper')
    parser.add_argument("--url", help="the start url , defaults to the config.ini url", default=START_URL)
    parser.add_argument("--sitemap-url", dest="sitemap_url", help="the sitemap url ")
    parser.add_argument("--url-file", dest="url_file", help="File containing list of urls ", action="store")
    parser.add_argument('--jserrors', dest='testjs', action='store_true')
    parser.add_argument('--no-jserrors', dest='testjs', action='store_false')
    parser.add_argument('--process-exisitng-urls', dest='process_file', action='store')
    parser.set_defaults(testjs=False)
    return parser.parse_args()


if __name__ == "__main__":

    # url ='http://appdynamics.com/blog/2010/09/01/application-virtualization-survey'
    #
    # link_info = extract(url)
    # parsed_link = u"{}.{}.{}".format(link_info.subdomain, link_info.domain, link_info.suffix)
    #
    # for skipped_domain in DOMAINS_TO_BE_SKIPPED:
    # if parsed_link == skipped_domain:
    # pass
    # pass

    args = process_parameters()
    base_url = decode_to_unicode(args.url)
    sitemap_url = decode_to_unicode(args.sitemap_url)
    enable_js_tests = args.testjs
    process_existing_urls = args.process_file
    url_list_file = decode_to_unicode(args.url_file)

    if process_existing_urls:
        if not url_list_file:
            print("Missing file containing  url list, please provide one with --url-file parameter")
            sys.exit(1)
        detect_js_and_resource_issues(url_list_file)
        sys.exit(0)

    scrapper = TornadoSpider(base_url, sitemap_url)
    future = scrapper.initiate_crawl()
    IOLoop.instance().start()

    if enable_js_tests:
        detect_js_and_resource_issues("all_internal_pages.txt")

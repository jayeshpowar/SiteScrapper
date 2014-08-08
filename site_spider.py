import argparse
from threading import Lock
import logging
import sys

from lxml import objectify
from tornado import gen
from tornado.httpclient import HTTPClient, HTTPError
from tornado.ioloop import IOLoop

from config import DOMAINS_TO_BE_SKIPPED, START_URL, \
    IDLE_PING_COUNT, IMPLEMENTATION_CLIENT
from resource_issue_detector import detect_js_and_resource_issues
from tornado_client_page import TornadoClientPage
from util import print_pages_with_errors, print_pages_with_hardcoded_links, print_pages_to_file, extract_domain, \
    extract_base_site
from web_page import WebPage







# logging.basicConfig(filemode='w', level=DEFAULT_LOGGER_LEVEL)
# handler = logging.FileHandler('scrapper.log')
logger = logging.getLogger(__name__)
# logger.addHandler(handler)

RESOURCES_STATE = dict()
universal_messages = []


class Resource:
    def __init__(self, parent=''):
        self.parent = parent
        self.error = set()
        self.resource_issues = set()

    def add_error(self, error):
        self.error.add(error)
        return self

    def add_resource(self, resource):
        self.resource_issues.add(resource)
        return self

    def __str__(self):
        str = '\n\nExamined %s' % self.parent.encode('utf8')
        errors = ("\nJavascript Errors : \n" + "\n".join(self.error)) if self.error else ""
        resources = ("\nBroken Resources : \n" + "\n".join(self.resource_issues)) if self.resource_issues else ""
        str += errors.encode('utf8')
        str += resources.encode('utf8')
        return str


def print_pages_to_file(file_name, identify_external, page_set,
                        filter_function=None):
    if not filter_function:
        filter_function = lambda wp: wp.external_url == identify_external \
                                     and wp.response_code not in ERROR_CODES \
                                     and 'text/html' in wp.content_type
    list_to_print = sorted(filter(filter_function, page_set))
    with open(file_name, 'w') as output_file:
        for page in list_to_print:
            output_file.write("{}\n".format(page.url))


def print_pages_with_errors(is_external_page, page_set, file_name):
    with open(file_name, 'w') as output_file:
        for error_code in ERROR_CODES:
            pages = sorted(filter((lambda wp: wp.external_url == is_external_page and wp.response_code == error_code), page_set))
            pages.sort(key=lambda x: x.parent)
            parent_page = ''
            for page in pages:
                failure_message_format = ''
                if not page.parent:
                    continue
                code = str(error_code)
                if error_code == -1:
                    code = '-1 (unknown)'
                    failure_message_format = '[{}]'
                if parent_page != page.parent.url:
                    parent_page = page.parent.url
                    output_file.write("\nExamined {} : \nPages with response Code {} : \n".format(parent_page.encode('utf8'), code))
                    print("\nExamined {} : \nPages with response Code {} :".format(parent_page.encode('utf8'), code))
                failure_message = failure_message_format.format(
                    page.failure_message) if failure_message_format else ''
                output_file.write("{} {} \n".format(page.url.encode('utf8'), failure_message))
                print("{} {} ".format(page.url.encode('utf8'), failure_message))


def print_pages_with_hardcoded_links(page_set, file_name):
    with open(file_name, 'w') as output_file:
        for page in page_set:
            if page.hardcoded_urls:
                output_file.write(
                    "\nExamined {} : \nHardcoded links found : {}\n".format(page.url.encode('utf8'),
                                                                           len(page.hardcoded_urls)))
                print("\nExamined {} : \nHardcoded links found : {}\n".format(page.url.encode('utf8'),
                                                                             len(page.hardcoded_urls)))
                for url in page.hardcoded_urls:
                    output_file.write("{} \n".format(url.encode('utf8')))
                    print("{}".format(url.encode('utf8')))


class SiteSpider:
    def __init__(self, start_url, sitemap_url=None):
        self.visited_urls = set()
        self.intermediate_urls = set()
        self.logger = logging.getLogger(__name__)
        self.base_domain = extract_domain(start_url)
        self.base_site = extract_base_site(start_url)
        self.non_visited_urls = {
            _get_client_page(start_url, None, start_url, self.base_domain, DOMAINS_TO_BE_SKIPPED)}
        self.added_count = 1
        self.idle_ping = 0
        # self.coop = task.Cooperator()
        self.start_idle_counter = False
        self.sitemap_url = '{}/sitemap.xml'.format(self.base_site) if not sitemap_url else sitemap_url

    def _filter_visited_links(self, page):
        return page not in self.visited_urls and page not in self.non_visited_urls \
               and page not in self.intermediate_urls

    # TODO : Fix the https handling properly
    def add_sitemap_urls(self):
        logger.debug("Adding sitemap urls as well for processing")
        # response = requests.get(self.sitemap_url)


        http_client = HTTPClient()
        try:
            response = http_client.fetch(self.sitemap_url)
            val = bytes(response.body)
            root = objectify.fromstring(val)
        except HTTPError as e:
            print "Error:", e
        http_client.close()

        for url in root.url:
            page = _get_client_page(bytes(url.loc), next(iter(self.visited_urls)), self.base_site,
                                    self.base_domain, DOMAINS_TO_BE_SKIPPED)
            if page not in self.visited_urls and page not in self.non_visited_urls \
                    and page not in self.intermediate_urls:
                print("Added {}".format(url.loc))
                self.non_visited_urls.add(page)
                self.added_count += 1

    def _get_unique_non_visited_links(self, page):
        l = Lock()
        l.acquire()
        filtered_links = set(filter(self._filter_visited_links, page.links))
        l.release()
        return filtered_links

    def process_web_page(self, web_page):
        logger.debug("Called {} for {}".format('process_web_page', unicode(web_page.url).encode("utf-8")))
        self.visited_urls.add(web_page)
        self.intermediate_urls.discard(web_page)
        unique_links = self._get_unique_non_visited_links(web_page)
        self.non_visited_urls = self.non_visited_urls.union(unique_links)
        self.added_count += len(unique_links)
        self.start_idle_counter = True

    # @coroutine
    def generate_urls_to_visit(self):
        processed_site_map_url = 0
        while processed_site_map_url < 2:
            while self.idle_ping < IDLE_PING_COUNT:
                if len(self.visited_urls) > 0:
                    print "Total urls added :  {} , Total urls visited : {} , Total urls in process : {}  \r".format(
                        self.added_count, len(self.visited_urls), len(self.intermediate_urls))

                    logger.debug(
                        "Total urls added :  {} , Total urls visited : {} , Total urls in process : {} ping {} \r"
                        .format(self.added_count, len(self.visited_urls), len(self.intermediate_urls),
                                self.idle_ping))

                if len(self.non_visited_urls) > 0:
                    self.idle_ping = 0
                    web_page = self.non_visited_urls.pop()
                    self.intermediate_urls.add(web_page)
                    yield web_page
                    # self.start_idle_counter = True
                elif self.start_idle_counter:
                    # d = Deferred()
                    # reactor.callLater(0.1, d.callback, None)
                    # yield d
                    self.idle_ping += 1
                    if self.idle_ping == IDLE_PING_COUNT:
                        break
                        # else:
                        # d = Deferred()
                        # reactor.callLater(0.1, d.callback, None)
                        #     yield d

                        # elif self.start_idle_counter:
                        #     d = Deferred()
                        #     reactor.callLater(0.1, d.callback, None)
                        #     yield d
                        #     self.idle_ping += 1
                        #     if self.idle_ping == IDLE_PING_COUNT:
                        #         break
                        # else:
                        #     d = Deferred()
                        #     reactor.callLater(0.1, d.callback, None)
                        #     yield d

            if self.sitemap_url:
                self.add_sitemap_urls()
            processed_site_map_url += 1
            self.idle_ping = 0
            logger.debug("Processed sitemap url iteration {}".format(processed_site_map_url))
        raise StopIteration

    def crawl(self):
        logger.debug("Called {}".format('crawl'))
        # deferred_list = []
        # coop = task.Cooperator()
        page_generator = self.generate_urls_to_visit()
        # page_generator.send(None)
        for page in page_generator:
            result = gen.Task(page.process(self))




            # print('>>>> %s/ '  %result)


            # for i in xrange(MAX_CONCURRENT_REQUESTS_PER_SERVER):
            # d = coop.coiterate(work)
            # deferred_list.append(d)
            # dl = DeferredList(deferred_list)
            # dl.addCallback(self.wrap_up)

    def wrap_up(self, resp):
        self.print_stats()
        IOLoop.stop()
        # reactor.stop()

    def print_stats(self):
        """
        Function to print the stats viz: pages with js errors , pages with 404
        error , external and internal pages .
        """
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

    args = process_parameters()
    base_url = args.url
    sitemap_url = args.sitemap_url
    enable_js_tests = args.testjs
    process_existing_urls = args.process_file
    url_list_file = args.url_file

    if process_existing_urls:
        if not url_list_file:
            print("Missing file containing  url list, please provide one with --url-file parameter")
            sys.exit(1)
        detect_js_and_resource_issues(url_list_file)
        sys.exit(0)

    scrapper = SiteSpider(base_url, sitemap_url)
    # if IMPLEMENTATION_CLIENT == 'twisted':
    # reactor.callLater(4, scrapper.crawl)
    # reactor.callLater(3, IOLoop.instance().start)
    # reactor.run()
    IOLoop.instance().call_later(2, scrapper.crawl)
    IOLoop.instance().start()
    # else:
    # IOLoop.instance().call_later()
    # tornado.ioloop.IOLoop.instance().start()

    if enable_js_tests:
        detect_js_and_resource_issues("all_internal_pages.txt")

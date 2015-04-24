import argparse
import logging
from datetime import timedelta

from tornado import gen
from tornado.ioloop import IOLoop
from toro import BoundedSemaphore, JoinableQueue

from config import START_URL, MAX_CONCURRENT_REQUESTS_PER_SERVER
from inventory_queue import InventoryQueue
from page_util import is_page_to_be_skipped
from util import extract_domain, print_pages_to_file, print_pages_with_errors, print_pages_with_hardcoded_links


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler('spider.log', mode='w'))



class Spider:
    def __init__(self, start_url, sitemap_file_url=None, max_concurrent_connections=MAX_CONCURRENT_REQUESTS_PER_SERVER):

        base_domain = extract_domain(start_url)
        self.inventory = InventoryQueue(start_url, sitemap_file_url, base_domain)
        self.semaphore = BoundedSemaphore(max_concurrent_connections)
        self.initial_queue = JoinableQueue()
        self.first_attempt = True

    @gen.coroutine
    def crawl(self):

        while True:
            logger.info("visited pages %s non visited %s , semaphore counter %s , in processing url %s  " % (
                str(len(self.inventory.visited_pages)), str(len(self.inventory.non_visited_pages)),
                str(self.semaphore.counter), str(len(self.inventory.in_process_pages))))

            if len(self.inventory.non_visited_pages) == 0 and self.semaphore.counter == 40:
                IOLoop.current().stop()
                self.print_stats()
            # logger.debug("START SEM COUNTER %d " % self.semaphore.counter)
            yield self.semaphore.acquire()
            # logger.debug("CURRENT SEM COUNTER %d " % self.semaphore.counter)
            if len(self.inventory.non_visited_pages) > 0:
                page = self.inventory.non_visited_pages.pop()
                logger.debug("ACQUIRED %s " % page.url)

                if page:
                    self.crawl_individual_page(page)
                    if self.first_attempt:
                        yield self.initial_queue.get()
            else:
                self.semaphore.release()
                self.inventory.non_visited_pages_queue.get()

            yield gen.Task(IOLoop.current().add_timeout, timedelta(seconds=0.1))

            # logger.debug("ITERATION done for %s " % page.url)

    @gen.coroutine
    def crawl_individual_page(self, non_visited_page):
        if non_visited_page not in self.inventory.visited_pages \
                and non_visited_page not in self.inventory.in_process_pages:

            self.inventory.in_process_pages.add(non_visited_page)
            head_response = yield non_visited_page.make_head_request()
            if head_response and not head_response.error:
                non_visited_page.response_code = head_response.code
                non_visited_page.content_type = u"".join(head_response.headers.get('Content-Type', ''))
                non_visited_page.redirection_url = head_response.effective_url

                # effective_url = head_response.effective_url if head_response.effective_url else non_visited_page.url
                if not non_visited_page.external and u'text/html' in non_visited_page.content_type:
                    get_response = yield non_visited_page.make_get_request()
                    if not get_response.error:
                        logger.debug("RESPONSE FOR GET >>> %s " % non_visited_page.url)

                        # TODO : Consider page set get returned instead of string url set.
                        # child_page_links = extract_links_from_response_for_url(non_visited_page.url, get_response)
                        non_visited_page.add_child_pages(get_response)
                        self.add_non_visited_pages(non_visited_page)
                        # self.add_non_visited_pages(non_visited_page.child_pages)
                        # self.add_non_visited_pages(non_visited_page.external_child_pages)

                        self.inventory.hardcoded_pages = \
                            self.inventory.hardcoded_pages | non_visited_page.hardcoded_child_pages
                        logger.debug("ADDED PAGES  FOR  >>> %s " % non_visited_page.url)
                    else:
                        logger.debug("ERROR FOR GET >>> %s " % non_visited_page.url)
                        non_visited_page.failure_message = get_response.reason
                else:
                    logger.debug("ADDED EXTERNAL PAGE AS    >>> %s " % non_visited_page.url)
                    self.inventory.external_pages.add(non_visited_page)
                    # TODO: Handle the response properly since no further processing to be done on the external page

        self.inventory.visited_pages.add(non_visited_page)
        self.inventory.in_process_pages.remove(non_visited_page)
        if self.first_attempt:
            self.first_attempt = False
            self.initial_queue.put(non_visited_page)
        logger.debug("REMOVED IN PROCESS PAGES  FOR  >>> %s " % non_visited_page.url)

        self.semaphore.release()
        logger.debug("SEMAPHORE COUNT %d , non-visited-pages %d  in-process %d" % (
            self.semaphore.counter, len(self.inventory.non_visited_pages), len(self.inventory.in_process_pages)))
        if len(self.inventory.non_visited_pages) <= 1 \
                and len(self.inventory.in_process_pages) == 0 \
                and self.semaphore.counter == 40:
            IOLoop.current().stop()
            self.print_stats()

    def add_non_visited_pages(self, page):
        child_pages = page.child_pages | page.external_child_pages
        for child_page in child_pages:
            existing_page = self.lookup_existing_page(child_page)
            if existing_page:
                existing_page.parents.add(page)
            if child_page not in self.inventory.in_process_pages \
                    and child_page not in self.inventory.visited_pages \
                    and child_page not in self.inventory.non_visited_pages \
                    and not is_page_to_be_skipped(child_page.url):
                self.inventory.non_visited_pages.add(child_page)
                self.inventory.non_visited_pages_queue.put(child_page)

    def lookup_existing_page(self, page):
        if page in self.inventory.in_process_pages:
            for existing_page in self.inventory.in_process_pages:
                if existing_page == page:
                    return existing_page

        if page in self.inventory.visited_pages:
            for existing_page in self.inventory.visited_pages:
                if existing_page == page:
                    return existing_page

        if page in self.inventory.non_visited_pages:
            for existing_page in self.inventory.non_visited_pages:
                if existing_page == page:
                    return existing_page

        return None

    def print_stats(self):
        # TODO : Specify parent specific external pages

        # print_pages_with_errors(True, self.inventory.visited_pages, "broken_external_links.txt")
        # print_pages_with_errors(False, self.inventory.visited_pages, "broken_internal_links.txt")
        print_pages_with_hardcoded_links(self.inventory.visited_pages, "hardcoded_url_links.txt")

        logger.info("\nTotal pages visited >> : {}\n".format(len(self.inventory.visited_pages)))
        print_pages_to_file("all_internal_pages.txt", False, self.inventory.visited_pages)
        print_pages_to_file("all_external_pages.txt", True, self.inventory.visited_pages,  print_parents=True)
        # print_pages_to_file("experimental_in_pages.txt", False, self.inventory.visited_pages)
        # print_pages_to_file("experimental_ex_pages.txt", True, self.inventory.visited_pages)


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
    base_url = "http://www.appdynamics.com"
    # base_url ="https://www.appdynamics.com/solutions/azure/how-to-guide"
    spider = Spider(base_url)
    # with StackContext(die_on_error):
    spider.crawl()
    IOLoop.instance().start()

    # url ='http://appdynamics.com/blog/2010/09/01/application-virtualization-survey'
    #
    # link_info = extract(url)
    # parsed_link = u"{}.{}.{}".format(link_info.subdomain, link_info.domain, link_info.suffix)
    #
    # for skipped_domain in DOMAINS_TO_BE_SKIPPED:
    # if parsed_link == skipped_domain:
    # pass
    # pass

'''
    args = process_parameters()
    base_url = decode_to_unicode(args.url)
    sitemap_url = decode_to_unicode(args.sitemap_url)
    enable_js_tests = args.testjs
    process_existing_urls = args.process_file
    url_list_file = decode_to_unicode(args.url_file)
    ext = tldextract.extract(base_url)

    if process_existing_urls:
        if not url_list_file:
            print("Missing file containing  url list, please provide one with --url-file parameter")
            sys.exit(1)
        detect_js_and_resource_issues(url_list_file, "js_and_broken_resources.txt")
        sys.exit(0)

    scrapper = TornadoSpider(base_url, sitemap_url)
    future = scrapper.initiate_crawl()
    IOLoop.instance().start()

    if enable_js_tests:
        detect_js_and_resource_issues("all_internal_pages.txt", "js_and_broken_resources.txt")
'''
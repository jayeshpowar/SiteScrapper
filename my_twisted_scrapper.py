import ConfigParser
from threading import Lock
import sys

from twisted.internet import task
from twisted.internet.defer import DeferredList






# pollreactor.install()
from twisted.internet import reactor
from my_twisted_page import extract_domain, extract_base_site, MyTwistedPage
import logging

logging.basicConfig(filemode='w', level=logging.INFO)
handler = logging.FileHandler('scrapper.log')
logger = logging.getLogger(__name__)
logger.addHandler(handler)

START_URL = ''
config = ConfigParser.RawConfigParser()
config.readfp(open(r'config.ini'))
MAX_CONCURRENT_REQUESTS = config.getint('scrapper-params',
                                        'MAX_CONCURRENT_REQUESTS_PER_SERVER')
IDLE_PING_COUNT = config.getint('scrapper-params', 'IDLE_PING_COUNT')
PAGE_TIMEOUT = config.getint('page-params', 'PAGE_TIMEOUT')
DOMAINS_TO_BE_SKIPPED = config.get('scrapper-params',
                                   'DOMAINS_TO_BE_SKIPPED').split(',')


class MyTwistedScrapper:
    def __init__(self, base_url):
        self.visited_urls = set()
        self.intermediate_urls = set()
        self.logger = logging.getLogger(__name__)
        self.base_domain = extract_domain(base_url)
        self.base_site = extract_base_site(base_url)
        self.non_visited_urls = set(
            [MyTwistedPage(base_url, None, base_url, self.base_domain,
                           DOMAINS_TO_BE_SKIPPED)])
        self.added_count = 1
        self.idle_ping = 1

    def filter_visited_links(self, page):
        return page not in self.visited_urls \
                   and page not in self.non_visited_urls \
            and page not in self.intermediate_urls

    def get_unique_non_visited_links(self, page):
        l = Lock()
        l.acquire()
        filtered_links = set(filter(self.filter_visited_links, page.links))
        l.release()
        return filtered_links

    def process_web_page(self, resp, web_page):
        logger.debug(
            "Called {} for {}".format('process_web_page', web_page.url))
        self.visited_urls.add(web_page)
        self.intermediate_urls.discard(web_page)
        unique_links = self.get_unique_non_visited_links(web_page)
        self.non_visited_urls = self.non_visited_urls.union(unique_links)
        self.added_count += len(unique_links)

    def trial_fetch(self):

        while len(self.non_visited_urls) > 0:
            web_page = self.non_visited_urls.pop()
            self.intermediate_urls.add(web_page)
            d = web_page.process()
            d.addCallback(self.process_web_page, web_page)
            yield d

    def crawl(self):
        logger.debug("Called {}".format('crawl'))

        print("Yet to visit {} urls with {} urls currently being processed "
              .format(self.added_count - len(self.visited_urls),
                      len(self.intermediate_urls)))

        deferred = []
        coop = task.Cooperator()
        work = self.trial_fetch()
        for i in xrange(MAX_CONCURRENT_REQUESTS):
            coop_deferred = coop.coiterate(work)
            deferred.append(coop_deferred)
        dl = DeferredList(deferred)
        self.idle_ping += 1
        print("Total added {} urls and visited {} urls "
              .format(self.added_count, len(self.visited_urls)))
        if self.idle_ping > IDLE_PING_COUNT > len(self.intermediate_urls):
            self.wrap_up()

    def wrap_up(self):
        print("Total  visited  links {} ".format(len(self.visited_urls)))
        self.print_stats()
        # for page in filter((lambda x: not x.external_url
        # and 'text/html' in x.content_type
        # and x.response_code != 404), self.visited_urls):
        #     page.browse_page()
        # self.print_stats()
        reactor.stop()


    def print_stats(self):
        """
        Function to print the stats viz: pages with js errors , pages with 404
        error , external and internal pages .
        """
        # print("\n\nPages with js error")
        # pages_with_js_errors = sorted(filter((lambda wp: len(wp.errors) > 0),
        #                               self.visited_urls))
        # for url in pages_with_js_errors:
        #     print(url)

        # print("\n\nPages with 404 error")
        # pages_with_404_errors = sorted(filter((lambda wp: wp.response_code == 404),
        #                                self.visited_urls))
        # for url in pages_with_404_errors:
        #     print(url)

        # print("\n\nExternal pages")
        # external_pages = sorted(filter((lambda wp: wp.external_url), self.visited_urls))
        # for url in external_pages:
        #     print(url)

        print("\n\nExternal pages with 404 errors")
        external_404_pages = sorted(filter((lambda wp: wp.external_url
        and wp.response_code == 404), self.visited_urls))
        for url in external_404_pages:
            print(url)

        # print("\n\nInternal pages")
        # intenal_pages = sorted(filter((lambda wp: not wp.external_url),
        #                        self.visited_urls))
        # for url in intenal_pages:
        #     print(url)

        print("\n\nInternal pages with 404 errors")
        internal_404_pages = sorted(filter((lambda wp: not wp.external_url
        and wp.response_code == 404), self.visited_urls))
        for url in internal_404_pages:
            print(url)

            # print(
            #     "\nTotal pages visited : {}\nPages with JS errors : {}"
            #     "\nPages with 404 errors : {}\n"
            #     "External Pages : {} \nInternal Pages : {}"
            #     "\nExternal Pages with 404: {} \nInternal Pages  with 404: {}"
            #     .format(len(self.visited_urls),
            #             len(pages_with_js_errors), len(pages_with_404_errors),
            #             len(external_pages), len(intenal_pages),
            #             len(external_404_pages), len(internal_404_pages)))

        print(
            "\nTotal pages visited : {}\n"
            "\nExternal Pages with 404: {} \nInternal Pages  with 404: {}"
            .format(len(self.visited_urls),
                    len(external_404_pages), len(internal_404_pages)))


def main(start_url):
    scrapper = MyTwistedScrapper(start_url)
    l = task.LoopingCall(scrapper.crawl)
    l.start(2.0)
    reactor.run()

if __name__ == "__main__":
    START_URL = sys.argv[1] if len(sys.argv) == 2 \
        else config.get('scrapper-params', 'START_URL')

    main(START_URL)



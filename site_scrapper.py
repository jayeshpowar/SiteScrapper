import argparse
from threading import Lock
import subprocess

from twisted.internet import task
from twisted.internet.defer import DeferredList, Deferred







# pollreactor.install()
from twisted.internet import reactor
from config import DOMAINS_TO_BE_SKIPPED, START_URL, \
    MAX_CONCURRENT_REQUESTS_PER_SERVER, PHANTOM_JS_LOCATION, IDLE_PING_COUNT
from web_page import extract_domain, extract_base_site, MyTwistedPage
import logging

logging.basicConfig(filemode='w', level=logging.INFO)
handler = logging.FileHandler('scrapper.log')
logger = logging.getLogger(__name__)
logger.addHandler(handler)

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
        self.idle_ping = 0
        self.coop = task.Cooperator()
        self.start_idle_counter = False

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
            "Called {} for {}".format('process_web_page',
                                      unicode(web_page.url).encode("utf-8")))
        self.visited_urls.add(web_page)
        self.intermediate_urls.discard(web_page)
        unique_links = self.get_unique_non_visited_links(web_page)
        self.non_visited_urls = self.non_visited_urls.union(unique_links)
        self.added_count += len(unique_links)
        self.start_idle_counter = True

    def trial_fetch(self):

        while self.idle_ping < IDLE_PING_COUNT:
            # logger.info(
            #     "Total urls added :  {} , Total urls visited : {} , Total urls in process : {}  "
            #     .format(self.added_count, len(self.visited_urls),
            #             len(self.intermediate_urls)))
            print "Total urls added :  {} , Total urls visited : {} , Total urls in process : {}  \r" \
                .format(self.added_count, len(self.visited_urls),
                        len(self.intermediate_urls))

            if len(self.non_visited_urls) > 0:
                self.idle_ping = 0
                web_page = self.non_visited_urls.pop()
                self.intermediate_urls.add(web_page)
                d = web_page.process()
                d.addCallback(self.process_web_page, web_page)
                yield d
            elif self.start_idle_counter:
                d = Deferred()
                reactor.callLater(0.1, d.callback, None)
                yield d
                self.idle_ping += 1
                if self.idle_ping == 300:
                    break
            else:
                d = Deferred()
                reactor.callLater(0.1, d.callback, None)
                yield d
        raise StopIteration


    def crawl(self):
        logger.debug("Called {}".format('crawl'))
        deferreds = []
        coop = task.Cooperator()
        work = self.trial_fetch()
        for i in xrange(MAX_CONCURRENT_REQUESTS_PER_SERVER):
            d = coop.coiterate(work)
            deferreds.append(d)
        dl = DeferredList(deferreds)
        dl.addCallback(self.wrap_up)

    def wrap_up(self, resp):
        print("Total  visited  links {} ".format(len(self.visited_urls)))
        self.print_stats()
        reactor.stop()


    def print_stats(self):
        """
        Function to print the stats viz: pages with js errors , pages with 404
        error , external and internal pages .
        """

        print("\n\nExternal pages with 404 errors")
        external_404_pages = sorted(filter((lambda wp: wp.external_url
        and wp.response_code == 404), self.visited_urls))

        external_404_pages.sort(key=lambda x: x.parent)
        parent_page = ''
        for page in external_404_pages:
            if parent_page != page.parent.url:
                parent_page = page.parent.url
                print(
                    "\nExamined {} : \nPages with response Code 404 : ".format(
                        parent_page))
            print("{} ".format(page.url))

        print("\n\nInternal pages with 404 errors")
        internal_404_pages = sorted(filter((lambda wp: not wp.external_url
        and wp.response_code == 404), self.visited_urls))

        internal_404_pages.sort(key=lambda x: x.parent)
        parent_page = ''
        for page in internal_404_pages:
            if parent_page != page.parent.url:
                parent_page = page.parent.url
                print(
                    "\nExamined {} : \nPages with response Code 404 : ".format(
                        parent_page))
            print("{} ".format(page.url))

        print(
            "\nTotal pages visited : {}\n"
            "\nExternal Pages with 404: {} \nInternal Pages  with 404: {}"
            .format(len(self.visited_urls),
                    len(external_404_pages), len(internal_404_pages)))

        internal_pages = sorted(filter((lambda wp: not wp.external_url
                                                   and wp.response_code == 200 and wp.content_type == 'text/html'),
                                       self.visited_urls))

        with open("urls.txt", 'w') as file:
            for page in internal_pages:
                file.write("{}\n".format(page.url))


def process_parameters():
    parser = argparse.ArgumentParser(description='A Simple website scrapper')
    parser.add_argument("--url",
                        help="the start url , defaults to the confog.ini url",
                        default=START_URL)
    parser.add_argument('--jserrors', dest='testjs', action='store_true')
    parser.add_argument('--no-jserrors', dest='testjs', action='store_false')
    parser.set_defaults(testjs=False)

    args = parser.parse_args()
    return args


if __name__ == "__main__":

    args = process_parameters()
    base_url = args.url
    enable_js_tests = args.testjs

    scrapper = MyTwistedScrapper(base_url)
    reactor.callLater(2, scrapper.crawl)
    reactor.run()

    intenal_pages = sorted(filter((lambda wp: not wp.external_url),
                                  scrapper.visited_urls))

    if enable_js_tests:
        print("\n\nIdentifying the javascript and page loading errors\n\n")
        SCRIPT = 'visitor.js'
        params = [PHANTOM_JS_LOCATION, SCRIPT, "urls.txt", ""]
        js_console = subprocess.check_output(params)

        print(js_console)





 

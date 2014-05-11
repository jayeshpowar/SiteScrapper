import logging
from threading import Lock

from twisted.internet import pollreactor, task


pollreactor.install()

from twisted.internet import reactor

from my_twisted_page import extract_domain, extract_base_site, MyTwistedPage


__author__ = 'jayesh'


def js_error_filter():
    """
    Filter function to filter out only pages with javascript errors .
    """
    return lambda wp: len(wp.errors) > 0


def page_not_found_error_filter():
    """
    Filter function to filter out only pages with 404 response code.
    """
    return lambda wp: wp.response_code == 404


def external_page_filter():
    """
    Filter function to filter out only pages from a different domain than the starting domain  .
    """
    return lambda wp: wp.external_url


def internal_page_filter():
    """
    Filter function to filter out only pages within the base domain .
    """
    return lambda wp: not wp.external_url


class MyTwistedScrapper:
    def __init__(self, base_url):
        self.visited_urls = set()
        self.intermediate_urls = set()
        logging.basicConfig(filename='myapp.log', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.base_domain = extract_domain(base_url)
        self.base_site = extract_base_site(base_url)
        self.non_visited_urls = set(
            [MyTwistedPage(base_url, None, base_url, self.base_domain)])
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
        # self.logger.debug("Adding {}  for {}".format(len(filtered_links),
        #                                              page.url))
        return filtered_links

    # Make sure this gets called for failed pages as well
    def process_web_page(self, resp, web_page):
        # print("Called {} for {}".format('process_web_page', web_page.url))
        self.visited_urls.add(web_page)
        self.intermediate_urls.discard(web_page)
        unique_links = self.get_unique_non_visited_links(web_page)
        # print("Adding {} links for {}".format(len(unique_links), web_page.url))
        self.non_visited_urls = self.non_visited_urls.union(unique_links)
        self.added_count += len(unique_links)

    def crawl(self):
        # print("Called {}".format('crawl'))

        print("Yet to visit {} with {} intermediate urls ".format(
            self.added_count - len(self.visited_urls),
            len(self.intermediate_urls)))

        if self.idle_ping == -1:
            for url in self.intermediate_urls:
                print(url.url)
        while len(self.non_visited_urls) > 0:
            # counter = 500
            # while len(self.non_visited_urls) > 0 and counter > 0:
            web_page = self.non_visited_urls.pop()
            self.intermediate_urls.add(web_page)
            d = web_page.process()
            d.addCallback(self.process_web_page, web_page)
            # counter -= 1

        self.idle_ping += 1

        print("Total added {} and visited {} ".format(self.added_count,
                                                      len(self.visited_urls)))

        if self.idle_ping > 10 \
                and len(self.intermediate_urls) < 10:
            print("Total  visited  links {} ".format(len(self.visited_urls)))
            self.print_stats()
            reactor.stop()

    def print_stats(self):
        """
        Function to print the stats viz: pages with js errors , pages with 404 error , external and internal pages .
        """
        print("\n\nPages with js error")
        for url in filter((lambda wp: len(wp.errors) > 0), self.visited_urls):
            print(url)

        print("\n\nPages with 404 error")
        for url in filter((lambda wp: wp.response_code == 404),
                          self.visited_urls):
            print(url)

        print("\n\nExternal pages")
        for url in filter((lambda wp: wp.external_url), self.visited_urls):
            print(url)

        print("\n\nInternal pages")
        for url in filter((lambda wp: not wp.external_url), self.visited_urls):
            print(url)


def main(args):
    base_url = args
    scrapper = MyTwistedScrapper(base_url)

    l = task.LoopingCall(scrapper.crawl)
    l.start(2.0)
    reactor.run()


if __name__ == "__main__":
    # base_url = 'http://www.neevtech.com'
    base_url = 'http://www.boddie.org.uk'
    # base_url = 'http://www.boddie.org.uk/david/Projects/Python/KDE/Software/kparts-2005-09-19.tar.gz'
    # base_url = 'http://modsnake.sf.net'
    # base_url = 'https://sourceforge.net/p/irefindex/drugbank'
    # base_url = 'http://www.boddie.org.uk/david/Projects/Python/index.html'
    # base_url = 'http://www.appdynamics.com/'
    main(base_url)
    # main(sys.argv[1:])



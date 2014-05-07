import logging
import atexit
import sys

from selenium import webdriver

from WebPage import WebPage, extract_domain, extract_base_site


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


class SiteScrapper:
    def __init__(self, base_url):
        self.visited_web_pages = []
        self.external_web_pages = []
        browser_profile = webdriver.FirefoxProfile()
        browser_profile.add_extension('JSErrorCollector.xpi')
        self.driver = webdriver.Firefox(firefox_profile=browser_profile)
        self.driver.implicitly_wait(20)

        self.base_domain = extract_domain(base_url)
        self.base_site = extract_base_site(base_url)
        self.non_visited_web_pages = set([WebPage(base_url, self.base_domain, self.base_site, self.driver)])
        self.non_visited_web_pages.add(WebPage(base_url + "#", self.base_domain, self.base_site, self.driver))
        logging.basicConfig(filename='test.out', level=logging.DEBUG)

    def crawl(self):
        """
        Function that crawls the web site starting from a provided base url .
        """
        index = 0
        while len(self.non_visited_web_pages) > 0:
            web_page = self.non_visited_web_pages.pop()
            if web_page in self.visited_web_pages or not web_page.is_valid_web_page():
                continue
            self.process_web_page(web_page)
            index += 1
            # if index > 5:
            #     break

        self.driver.quit()

    def print_stats(self):
        """
        Function to print the stats viz: pages with js errors , pages with 404 error , external and internal pages .
        """
        # print("\n\nPages with js error")
        # for url in filter(js_error_filter(), self.visited_web_pages):
        #     print(url)
        #
        # print("\n\nPages with 404 error")
        # for url in filter(page_not_found_error_filter(), self.visited_web_pages):
        #     print(url)
        #
        # print("\n\nExternal pages")
        # for url in filter(external_page_filter(), self.visited_web_pages):
        #     print(url)

        print("\n\nInternal pages")
        for url in filter(internal_page_filter(), self.visited_web_pages):
            print(url)

    def process_web_page(self, web_page):
        """
        Function to process the web page i:e In case of a page within domain open the page in the browser using
        selenium firefox driver , also if the accessed web page doesn't have content type of "text/html" just fetch the
        response code instead of opening in the browser .In case the page is from an external source just fetch the
        response code of the page .
        """
        web_page.browse(self.visited_web_pages, self.non_visited_web_pages)
        self.non_visited_web_pages.update(web_page.links)
        self.visited_web_pages.append(web_page)
        if web_page.external_url:
            self.external_web_pages.append(web_page)


def main(args):
    base_url = args[0]
    scrapper = SiteScrapper(base_url)
    atexit.register(scrapper.print_stats)
    scrapper.crawl()


if __name__ == "__main__":
    main(sys.argv[1:])






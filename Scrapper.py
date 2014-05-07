import concurrent.futures
import logging
from threading import Lock
import atexit
from bs4 import BeautifulSoup
import requests
import sys
from WebPage import WebPage, extract_domain, extract_base_site


# def fetch_links_for_page(web_page):
#     """
#         Function to fetch the content-type and response code for a url .
#     """
#     if not web_page.external_url:
#         if 'text/html' in web_page.content_type:
#             # self.driver.get(self.url)
#             response = requests.get(web_page.url, verify=False)
#             html_source = response.text
#             soup = BeautifulSoup(html_source)
#             link_elements = soup.find_all("a")
#
#             link_count = 0
#             for link_tag in link_elements:
#                 link = None
#                 if link_tag.has_attr('href'):
#                     if link_tag['href'].startswith('/'):
#                         link = "{}{}".format(web_page.base_site,
#                                              link_tag['href'])
#                     elif link_tag['href'].startswith('#'):
#                         link = "{}/{}".format(web_page.url,
#                                               link_tag['href'])
#                     elif not link_tag['href'].startswith('http'):
#                         link = "{}/{}".format(web_page.base_site,
#                                               link_tag['href'])
#                     else:
#                         link = link_tag['href']
#                 else:
#                     continue
#
#                 if link is not None:
#                     link_page = WebPage(link, web_page.base_domain,
#                                         web_page.base_site,
#                                         web_page.driver)
#                     web_page.links.add(link_page)
#                     link_page.parent = web_page
#                     link_count += 1
#
#     return web_page
#
#
# def fetch_url(web_page):
#     """
#         Function to fetch the content-type and response code for a url .
#     """
#     fetched_page = web_page
#     if web_page.is_valid_web_page():
#         try:
#             response = requests.head(web_page.url, verify=False)
#             response_code = response.status_code
#             content_type = response.headers.get('Content-Type', '')
#             fetched_page = fetch_links_for_page(web_page)
#             fetched_page.response_code = response_code
#             fetched_page.content_type = content_type
#             # self.visited_urls.add(fetched_page)
#         except requests.exceptions.RequestException:
#             fetched_page.response_code = -1
#             fetched_page.content_type = 'unknown'
#             # self.logger.error("Error parsing {}".format(web_page.url),
#             #                   exc_info=True)
#     return fetched_page


class Scrapper:
    def __init__(self, base_url, max_workers=200):

        self.visited_urls = set()
        self.max_workers = max_workers
        logging.basicConfig(filename='myapp.log', level=logging.DEBUG)
        self.logger = logging.getLogger(__name__)
        self.base_domain = extract_domain(base_url)
        self.base_site = extract_base_site(base_url)
        self.non_visited_urls = set([WebPage(base_url, self.base_domain, self.base_site, None)])


    def filter_visited_links(self, page):
        return page not in self.visited_urls and page not in self.non_visited_urls

    def get_unique_non_visited_links(self, page):
        l = Lock()
        l.acquire()
        filtered_links = set(filter(self.filter_visited_links, page.links))
        l.release()
        self.logger.debug("Adding {}  for {}".format(len(filtered_links),
                                                     page.url))
        return filtered_links

    def crawl(self):

        # We can use a with statement to ensure threads are cleaned up promptly
        with concurrent.futures.ThreadPoolExecutor \
                        (max_workers=self.max_workers) as executor:

            while len(self.non_visited_urls) > 0:
                print("Still {} to be visited ".format(len(self.non_visited_urls)))
                future_list = {}
                for loop_count in range(5):
                    thread_count = 0
                    while thread_count < self.max_workers:
                        if len(self.non_visited_urls) == 0:
                            thread_count += 1
                            continue
                        web_page = self.non_visited_urls.pop()
                        future = executor.submit(web_page.fetch_url)
                        future_list[future] = web_page
                        thread_count += 1

                for future in concurrent.futures.as_completed(future_list):
                    web_page = future_list[future]
                    try:
                        web_page = future.result()
                        self.visited_urls.add(web_page)
                        non_visited_links = \
                            self.get_unique_non_visited_links(web_page)
                        self.non_visited_urls = self.non_visited_urls.union(
                            non_visited_links)
                    except Exception as exc:
                        print('%r generated an exception: %s'
                              % (web_page.url, exc))



        print("++++++++++")

        for wp in self.visited_urls:
            print(wp)


def main(args):
    base_url = args[0]
    scrapper = Scrapper(base_url)
    # atexit.register(scrapper.print_stats)
    scrapper.crawl()


if __name__ == "__main__":
    main(sys.argv[1:])


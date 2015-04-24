import logging
from lxml import objectify
from tornado.httpclient import HTTPClient
from toro import JoinableQueue
from page import Page

logger = logging.getLogger(__name__)


class InventoryQueue:

    def __init__(self, start_url, sitemap_url, base_domain):
        self.base_page = ''

        self.pages_with_errors = set()
        self.broken_pages = set()
        self.external_pages = set()
        self.internal_pages = set()
        self.hardcoded_pages = set()
        self.sitemap_url = sitemap_url

        # Store the intermediate urls
        self.in_process_pages = set()
        self.visited_pages = set()
        self.non_visited_pages = set()

        self.non_visited_pages.add(Page(start_url, None, base_domain))
        urls_from_sitemap_file = self.extract_urls_from_sitemap_url()
        self._add_sitemap_pages_to_non_visited_list(urls_from_sitemap_file)

        self.non_visited_pages_queue = JoinableQueue()

    def extract_urls_from_sitemap_url(self):
        if self.sitemap_url:
            logger.debug("Adding sitemap urls as well for processing")
            http_client = HTTPClient()
            url_list = list()
            try:
                response = http_client.fetch(self.sitemap_url)
                val = bytes(response.body)
                root = objectify.fromstring(val)

                for url_element in root.url:
                    url = url_element.loc.text
                    url_list.append(url)

            except Exception as e:
                logger.error(u"Error extracting sitemap urls from %s " % self.sitemap_url)
            finally:
                http_client.close()
                return url_list

    def _add_sitemap_pages_to_non_visited_list(self, urls_from_sitemap_file):
        if urls_from_sitemap_file:
            for url in urls_from_sitemap_file:
                self.non_visited_pages.put(Page(url))



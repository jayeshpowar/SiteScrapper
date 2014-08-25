import logging

from tornado.httpclient import AsyncHTTPClient
from tldextract import extract

from config import DEFAULT_LOGGER_LEVEL, HARD_CODED_LINKS, HARD_CODED_LINK_EXCLUSIONS, URL_SEGMENTS_TO_SKIP
from util import extract_domain, decode_to_unicode, obtain_domain_with_subdomain_for_page


logging.basicConfig(filemode='w', filename='default.log', level=DEFAULT_LOGGER_LEVEL)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler('page.log', mode='w'))


class WebPage(object):
    def __init__(self, url, parent, base_site, base_domain, domains_to_skip):
        self.url = decode_to_unicode(url) if url is not None else decode_to_unicode('')
        self.encoded_url = decode_to_unicode(self.url)
        self.base_domain = base_domain
        self.response_code = -1
        self.errors = []
        self.links = set()
        self.visited = False
        self.parent = parent
        self.base_site = base_site
        self.content_type = decode_to_unicode("text/html")
        self.domains_to_skip = domains_to_skip
        self.redirect_location = decode_to_unicode('')
        self.hardcoded_urls = set()
        self.failure_message = decode_to_unicode('')
        AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

    def is_page_internal(self):
        if self.base_domain not in extract_domain(self.url):
            return False

        parsed_link = obtain_domain_with_subdomain_for_page(self.url)

        for skipped_domain in self.domains_to_skip:
            if parsed_link == skipped_domain:
                return False
        return True

    def skip_page(self):
        parsed_link = obtain_domain_with_subdomain_for_page(self.url)

        for skipped_domain in self.domains_to_skip:
            if parsed_link == skipped_domain:
                return True

        for segment_to_skip in URL_SEGMENTS_TO_SKIP:
            if segment_to_skip in self.url:
                return True

        return False

    def _process_hardcoded_url(self, href_link):
        if href_link.startswith(u'http://') or href_link.startswith(u'https://'):
            link_info = extract(href_link)
            parsed_link = u"{}.{}.{}".format(link_info.subdomain, link_info.domain, link_info.suffix)
            if 'all' in HARD_CODED_LINKS:
                self.hardcoded_urls.add(href_link)
            else:
                if parsed_link in HARD_CODED_LINKS:
                    for hard_coded_exclusion in HARD_CODED_LINK_EXCLUSIONS:
                        if not hard_coded_exclusion in href_link:
                            self.hardcoded_urls.add(href_link)

    def process(self, spider):
        raise NotImplementedError("implement client specific process")

    def finalize_process(self, spider):
        # logger.debug("Called Finalize process for {} ...".format(self.encoded_url))
        spider.process_web_page(self)

    def __hash__(self):
        url = self.url
        url = url[:-1] if url.endswith('/') else url
        return hash(url.replace("https", 'http'))

    def __eq__(self, other):
        url = self.url
        url = url[:-1] if url.endswith('/') else url

        other_url = other.url
        other_url = other_url[:-1] if other_url.endswith('/') else other_url

        return url.replace("https", 'http') == other_url.replace("https", 'http')

    def __str__(self):
        return "Url: {}," \
               "\tResponse Code : {}" \
               "\tParent : {}" \
               "\tInternal : {}" \
               "\tVisited : {}" \
               "\tErrors : {} " \
            .format(self.url, self.response_code,
                    self.parent.url if self.parent is not None else '',
                    self.is_page_internal(), self.visited, self.errors)
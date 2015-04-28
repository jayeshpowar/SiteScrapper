import logging

from lxml import html
from tldextract import extract
from tornado import gen
from tornado.gen import Return
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from config import PAGE_TIMEOUT, DOMAINS_TO_BE_SKIPPED, DEFAULT_LOGGER_LEVEL
from page_util import is_url_hardcoded, is_page_to_be_skipped, sanitize_url_link, is_page_internal
from util import decode_to_unicode, obtain_domain_with_subdomain_for_page


logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOGGER_LEVEL)
logger.addHandler(logging.FileHandler('page.log', mode='w'))

HEADER_DICT = {
    "User-Agent":
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.1  (KHTML, like Gecko) Chrome/13.0.782.220 Safari/535.1"}


class Page:
    def __init__(self, url, parent_page=None, base_domain=None):
        self.response_code = -1
        self.failure_message = ''
        self.base_domain = base_domain
        self.content_type = ''

        link_info = extract(url)
        if link_info.subdomain == '':
            revised_url = url.replace('://', '://www.')
            self.url = revised_url
        elif link_info.subdomain == 'www-origin':
            revised_url = url.replace(link_info.subdomain, 'www')
            self.url = revised_url
        else:
            revised_url = url

        self.url = revised_url
        self.encoded_url = decode_to_unicode(self.url)
        self.parent_page = parent_page

        self.child_pages = set()
        self.hardcoded_child_pages = set()
        self.external_child_pages = set()
        self.errors = []

        self.redirection_url = self.url

        self.external = not is_page_internal(self.url if not self.redirection_url else self.redirection_url,
                                             self.base_domain)
        self.to_be_skipped = is_page_to_be_skipped(self.url)
        self.hardcoded = is_url_hardcoded(self.url)

        # parents having the current page as child page
        self.parents = set() if not parent_page else set([parent_page])

    @gen.coroutine
    def make_head_request(self):
        try:
            response = yield self._make_request('HEAD')
        except Exception as ex:
            logger.debug(u"Returned exception while making head request")
            raise Return(None)
        raise Return(response)

    @gen.coroutine
    def make_get_request(self):
        try:
            response = yield self._make_request('GET')
        except Exception as ex:
            logger.debug(u"Returned exception while making head request")
            raise Return(None)
        raise Return(response)

    @gen.coroutine
    def _make_request(self, method):
        request = HTTPRequest(method=method, url=self.url, request_timeout=PAGE_TIMEOUT, follow_redirects=True,
                              headers=HEADER_DICT,
                              max_redirects=10)
        AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")
        try:
            logger.debug("About to make %s request to  %s  " % (method, request.url))
            response = yield AsyncHTTPClient().fetch(request)
        except HTTPError as error:
            error_response = error.response
            self.response_code = error.response.code
            self.failure_message = decode_to_unicode(error.response.reason)
            logger.debug(
                u"Error processing %s request for : %s with error : %s [CODE: %s]  "
                % (method, self.encoded_url, str(error_response.reason), str(error_response.code)))
            raise Return(None)
        except Exception as ex:
            logger.debug(
                u"Other Error processing %s request for : %s with error : %s  "
                % (method, self.encoded_url, str(ex)))
            self.failure_message = decode_to_unicode(str(ex))
            raise Return(None)

        raise Return(response)

    def add_child_pages(self, get_response):
        child_pages_links_set = self._extract_links_from_response_for_url(get_response)

        for child_page in child_pages_links_set:
            if not child_page.external:
                self.child_pages.add(child_page)
            else:
                self.external_child_pages.add(child_page)

            if child_page.hardcoded:
                self.hardcoded_child_pages.add(child_page)

    def _extract_links_from_response_for_url(self, response):
        child_page_links = set()
        # logger.debug(u"Called {} for {} ".format('extract_child_pages', self.encoded_url))

        if not response.error:
            html_source = response.body
            html_source = decode_to_unicode(html_source)
            dom = html.fromstring(html_source)

            for href_value in dom.xpath('//a/@href'):
                href_value = decode_to_unicode(href_value)
                link = sanitize_url_link(self.url, href_value)

                if link:
                    parsed_link = obtain_domain_with_subdomain_for_page(link)
                    if parsed_link not in DOMAINS_TO_BE_SKIPPED:
                        child_page = Page(link, self, self.base_domain)
                        child_page.hardcoded = is_url_hardcoded(href_value)
                        child_page_links.add(child_page)

        return child_page_links

    def __hash__(self):
        url = self.url
        url = url.replace("https", "http")
        url = url[:-1] if url.endswith('/') else url

        link_info = extract(url)
        if not link_info.subdomain:
            url = url.replace('://', '://www.')

        if link_info.subdomain == 'www-origin':
            url = url.replace('://www-origin', '://www')

        hash_value = hash(url)

        return hash_value

    def __eq__(self, other):
        url = self.url
        url = url.replace("https", "http")
        url = url[:-1] if url.endswith('/') else url

        other_url = other.url
        other_url = other_url.replace("https", "http")
        other_url = other_url[:-1] if other_url.endswith('/') else other_url

        link_info = extract(url)
        other_link_info = extract(other_url)

        return (link_info.domain == other_link_info.domain and
                link_info.suffix == other_link_info.suffix) and \
               ((link_info.subdomain in ['www', 'www-origin', ''] and
                 other_link_info.subdomain in ['www', 'www-origin', '']) or
                (link_info.subdomain == other_link_info.subdomain))

    def __str__(self):
        return "Url: {}," \
               "\tRedirection URL : {}" \
               "\tResponse Code : {}" \
               "\tParent : {}" \
               "\tExternal : {}" \
               "\tHardcoded : {} " \
               "\tErrors : {} " \
               "\tContent-Type : {} " \
            .format(self.url, self.url, self.response_code,
                    self.parent_page.url if self.parent_page is not None else '',
                    self.external, self.hardcoded, self.errors, self.content_type)


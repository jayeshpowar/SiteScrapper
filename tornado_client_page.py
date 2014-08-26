import logging
import urlparse

from lxml import html
from tornado.gen import coroutine, Return
from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from config import PAGE_TIMEOUT
from util import decode_to_unicode, obtain_domain_with_subdomain_for_page
from web_page import WebPage


__author__ = 'jayesh'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.FileHandler('page.log', mode='w'))

tornado_logger = logging.getLogger('tornado.general')
tornado_logger.setLevel(logging.DEBUG)
tornado_logger.addHandler(logging.FileHandler('tornado-requests.log', mode='w'))


class TornadoClientPage(WebPage):
    def process(self, spider):
        logger.debug("Called {} for {}".format('process', self.encoded_url))
        self.spider = spider

    @coroutine
    def make_head_request(self):
        logger.debug("Called %s for %s " % ('make_head_request', self.encoded_url))
        request = HTTPRequest(method='HEAD', url=self.url, request_timeout=PAGE_TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.1 "
                                                     "(KHTML, like Gecko) Chrome/13.0.782.220 Safari/535.1"},
                              max_redirects=10)
        try:
            response = yield AsyncHTTPClient().fetch(request)

        except HTTPError as ex:
            logger.debug(
                u"Error processing head request for : %s with error : %s  " % (self.encoded_url, str(ex.message)))
            self.response_code = ex.code
            self.failure_message = decode_to_unicode(ex.message)
            self.finalize_process(self.spider)
            raise Return(None)

        raise Return(response)

    @coroutine
    def _process_head_response(self, response):
        if response:
            logger.debug(u"Called {} for {} ".format('_process_head_response', self.encoded_url))

            self.response_code = response.code
            self.content_type = u"".join(response.headers.get('Content-Type', ''))
            effective_url = response.effective_url if response.effective_url else self.url
            if self.is_page_internal(effective_url) and u'text/html' in self.content_type:
                get_response = yield self._make_get_request()
                raise Return(get_response)
            else:
                self.finalize_process(self.spider)

        raise Return(None)


    @coroutine
    def _make_get_request(self):
        logger.debug(u"Called {} for {} ".format('_make_get_request', self.encoded_url))

        request = HTTPRequest(method='GET', url=self.url, request_timeout=PAGE_TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.1 "
                                                     "(KHTML, like Gecko) Chrome/13.0.782.220 Safari/535.1"},
                              max_redirects=10)
        try:
            response = yield AsyncHTTPClient().fetch(request)
        except Exception as ex:
            logger.debug(
                u"Error processing get request for : %s with error : %s  " % (self.encoded_url, str(ex.message)))
            self.response_code = ex.code
            self.failure_message = decode_to_unicode(ex.message)
            self.finalize_process(self.spider)
            raise Return(None)

        raise Return(response)

    def process_get_response(self, response):
        logger.debug(u"Called {} for {} ".format('process_get_response', self.encoded_url))

        if response.error:
            logger.debug(u"Error processing  get request: {} with error : {}  ( {} )"
                         % (self.encoded_url, response.error, response.reason))
            self.failure_message = response.reason
        else:
            html_source = response.body
            html_source = decode_to_unicode(html_source)
            if self.is_page_internal():
                dom = html.fromstring(html_source)
                # logger.debug("obtained dom object for {}".format(encoded_url))

                link_count = 0
                for href_value in dom.xpath('//a/@href'):
                    href_value = decode_to_unicode(href_value)
                    logger.debug(u"Entering for loop for for {} with href {}".format(self.encoded_url, href_value))
                    self._process_hardcoded_url(href_value)
                    link = self._format_link(href_value)
                    logger.debug(u"obtained link  object{} for {}".format(link, self.encoded_url))

                    if link:
                        parsed_link = obtain_domain_with_subdomain_for_page(link)

                        if parsed_link not in self.domains_to_skip:
                            link_page = TornadoClientPage(link, self, self.base_site, self.base_domain,
                                                          self.domains_to_skip)
                            self.links.add(link_page)
                            link_page.parent = self
                            link_count += 1
        self.finalize_process(self.spider)

    def _format_link(self, href_value):
        href_value = decode_to_unicode(href_value.strip())
        if href_value.startswith('#'):
            link = self.url
        else:
            href_value = href_value.replace("..", "") if href_value.startswith("..") else href_value
            link = urlparse.urljoin(self.url, href_value, allow_fragments=False)
            link = link if 'javascript:void' not in href_value and not href_value.startswith('mailto') else None
        return decode_to_unicode(link)

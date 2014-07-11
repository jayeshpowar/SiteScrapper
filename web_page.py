import urlparse
import logging
import subprocess

import lxml.html
from selenium import webdriver
from twisted.internet import reactor
from twisted.internet.defer import Deferred, maybeDeferred, succeed
from twisted.internet.ssl import ClientContextFactory
from twisted.python import log
from twisted.web.client import Agent, getPage, WebClientContextFactory, \
    BrowserLikeRedirectAgent
from tldextract import extract

from config import PAGE_TIMEOUT, DEFAULT_LOGGER_LEVEL, HARD_CODED_LINKS, ERROR_CODES


logging.basicConfig(filemode='w', filename='page.log', level=DEFAULT_LOGGER_LEVEL)
logger = logging.getLogger(__name__)


def extract_base_site(url):
    extracted = extract(url)
    if extracted.domain.endswith("."):
        return extracted.domain[:-1]
    site = "http://{}.{}.{}".format(extracted.subdomain, extracted.domain,
                                    extracted.tld)
    return site


def extract_domain(url):
    extracted = extract(url)
    domain = "{}.{}".format(extracted.domain, extracted.tld)
    if domain.endswith("."):
        return domain[:-1]
    return domain


class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)


class WebPage:
    def __init__(self, url, parent, base_site, base_domain, domains_to_skip):
        self.url = '' if url is None else url
        # self.url = unicode(self.url).encode('utf-8')
        self.encoded_url = self.url.encode('utf-8')
        self.base_domain = base_domain
        self.response_code = -1
        self.external_url = self.base_domain not in extract_domain(self.url)
        self.errors = []
        self.links = set()
        self.visited = False
        self.parent = parent
        self.base_site = base_site
        self.content_type = "text/html"
        self.domains_to_skip = domains_to_skip
        self.redirect_location = ''
        self.hardcoded_urls = set()


    def is_redirected_to_external_site(self):
        encoded_url = self.url.encode('utf8')
        logger.debug("Redirected location is {} for {}".format(self.redirect_location, encoded_url))
        redirected_domain = extract_domain(self.redirect_location)
        logger.debug("Redirected domain is {} for {}".format(redirected_domain, encoded_url))
        return self.base_domain in extract_domain(redirected_domain)

    def process_head_response(self, response):
        logger.debug("Called {} for {} ".format('process_head_response', self.url))
        self.response_code = response.code
        self.content_type = "".join(
            response.headers.getRawHeaders('Content-Type', ''))

        if response.previousResponse is not None:
            headers = response.previousResponse.headers.getRawHeaders("location")
            self.redirect_location = headers[0] if headers else ''

        if response.code in ERROR_CODES:
            raise Exception(
                'Failed with error code {}'.format(response.code))

        return response.code


    def process_head_failure(self, failure):
        logger.info("Called {} for {} due to {} ".format('process_head_failure',
                                                         self.url.encode(
                                                             'utf8'),
                                                         failure.value))
        self.content_type = 'UNKNOWN'
        raise Exception(failure.value)

    def process_hardcoded_url(self, href_link):
        if href_link.startswith('http://') or href_link.startswith('https://'):
            link_info = extract(href_link)
            parsed_link = "{}.{}.{}".format(link_info.subdomain, link_info.domain, link_info.suffix)
            if 'all' in HARD_CODED_LINKS:
                self.hardcoded_urls.add(href_link)
            else:
                if parsed_link in HARD_CODED_LINKS:
                    self.hardcoded_urls.add(href_link)

    def format_link(self, href_value):
        href_value = href_value.strip()
        if href_value.startswith('#'):
            link = self.url
        else:
            href_value = href_value.replace("..", "") \
                if href_value.startswith("..") else href_value
            link = urlparse.urljoin(self.url, href_value, allow_fragments=False)
            link = link if 'javascript:void' not in href_value \
                           and not href_value.startswith('mailto') else None
        return link

    def process_get_response(self, response):
        encoded_url = self.url.encode('utf8')
        logger.debug(
            "Called {} for {} ".format('process_get_response', encoded_url))
        if not self.external_url:
            html_source = response
            # html_source, errs = tidy_document(html_source)

            # soup = BeautifulSoup(html_source, parse_only=SoupStrainer('a'))
            # link_elements = soup.find_all("a")
            dom = lxml.html.fromstring(html_source)
            logger.debug("obtained dom object for {}".format(encoded_url))

            # for link in dom.xpath('//a/@href'): # select the url in href for all a tags(links)
            # print link

            link_count = 0
            for href_value in dom.xpath('//a/@href'):
                logger.debug("Entering for loop for for {} with href {}".format(self.encoded_url, href_value))
                self.process_hardcoded_url(href_value)
                # link = None
                # if link_tag.has_attr('href'):
                # href_value = link_tag['href']
                # link = self.format_link(href_value)
                # else:
                #     continue
                link = self.format_link(href_value)
                logger.debug("obtained link  object{} for {}".format(link, encoded_url))

                if link:
                    link_info = extract(link)
                    parsed_link = "{}.{}.{}".format(link_info.subdomain,
                                                    link_info.domain,
                                                    link_info.suffix)
                    if parsed_link not in self.domains_to_skip:
                        link_page = WebPage(link, self, self.base_site,
                                            self.base_domain,
                                            self.domains_to_skip)
                        self.links.add(link_page)
                        link_page.parent = self
                        link_count += 1

    def process_get_failure(self, response):
        logger.info("Called {} for {} with {} ".format('process_get_failure',
                                                       self.url.encode('utf8'),
                                                       response.value))
        self.content_type = 'UNKNOWN'

    def make_head_request(self):
        agent = BrowserLikeRedirectAgent(Agent(reactor))
        if 'https' in self.url:
            context_factory = WebClientContextFactory()
            agent = BrowserLikeRedirectAgent(Agent(reactor, context_factory))
        deferred = agent.request('HEAD', bytes(self.url.encode('utf8')))
        return deferred

    def make_get_request(self, status):
        encoded_url = self.url.encode('utf8')
        logger.debug("Called {} for {}  ".format('make_get_request', encoded_url))
        d = Deferred()
        logger.debug("defer created for {}".format(encoded_url))
        logger.debug("content type {} for {}".format(self.content_type, encoded_url))
        logger.debug("external url {} for {}".format(self.external_url, encoded_url))
        logger.debug("external url {} for {}".format(self.external_url, encoded_url))
        if 'text/html' in self.content_type and not self.external_url and not self.is_redirected_to_external_site():
            logger.debug("About to get page for for {}".format(encoded_url))
            d = getPage(bytes(self.url.encode('utf8')), timeout=PAGE_TIMEOUT)
        else:
            logger.debug("Page not containing html at {}".format(encoded_url))
            d.callback("No html content")
        return d

    def process(self):
        logger.debug("Called {}".format('process'))
        deferred = self.make_head_request()
        deferred.addCallback(self.process_head_response)
        deferred.addErrback(self.process_head_failure)
        deferred.addCallback(self.make_get_request)
        deferred.addCallback(self.process_get_response)
        deferred.addErrback(self.process_get_failure)
        deferred.addErrback(log.err)
        return deferred

    def obtain_driver(self):
        browser_profile = webdriver.FirefoxProfile()
        browser_profile.add_extension('JSErrorCollector.xpi')
        driver = webdriver.Firefox(firefox_profile=browser_profile)

        return succeed(driver)

    def browse_page(self):
        d = maybeDeferred(self.obtain_driver)
        d.addCallback(self.identify_javascript_errors)
        return d

    def identify_javascript_errors(self, driver):
        result = subprocess.check_output(
            ["phantomjs", "visitor.js", self.url]).split('\n')
        self.errors = result

        """driver.get(self.url)
        WebDriverWait(driver, 20).until(lambda d: d.execute_script(
            'return document.readyState') == 'complete')
        try:
            error_messages = driver.execute_script(
                bytes("return window.JSErrorCollector_errors.pump()"))
            self.errors = list(map(lambda x: x['errorMessage'], error_messages))
        except Exception as e:
            logger.error("Encountered error while collecting data from "
                         "jscollector plugin , defaulting to the basic "
                         "mechanism for error collection")
            log_messages = (driver.get_log('browser'))
            for error_entry in log_messages:
                if "Error" in error_entry["message"] and "SEVERE" in \
                        error_entry[
                            'level']:
                    self.errors.append(error_entry)
        driver.quit()"""

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url.replace("https", 'http') == \
               other.url.replace("https", 'http')

    def __str__(self):
        return "Url: {}," \
               "\tResponse Code : {}" \
               "\tParent : {}" \
               "\tExternal : {}" \
               "\tVisited : {}" \
               "\tErrors : {} " \
            .format(self.url, self.response_code,
                    self.parent.url if self.parent is not None else '',
                    self.external_url, self.visited, self.errors)
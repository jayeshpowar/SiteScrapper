import re
import logging

from tldextract import extract
import requests
from bs4 import BeautifulSoup


class WebPage:
    def __init__(self, url, base_domain, base_site, driver, parent=None):
        self.url = '' if url is None else url
        self.base_domain = base_domain
        self.response_code = -1
        self.external_url = self.base_domain not in extract_domain(self.url)
        self.errors = []
        self.links = set()
        self.visited = False
        self.driver = driver
        self.parent = parent
        self.base_site = base_site

    def add_errors(self, errors):
        """
        Utility method to add js errors fetched from the page. Note that this is useful only if the logging has been
        added to the selenium firefox driver.
        """
        for error_entry in errors:
            if "Error" in error_entry["message"] and "SEVERE" in error_entry['level']:
                self.errors.append(error_entry)

    def browse(self, visited_pages, non_visited_pages):
        """
        Function to browse the web page .The steps followed are as listed :
         1.Validate the web url for proper format , if a valid url exist then proceed further .
         2.Fetch the response code and content type for the url .
         3.If it is a document with "text/html" content type and is a page from internal domain ,open the page in
          firefox using selenium and fetch all the links from the page .
         4.Add all the unique links to the web page currently being visited .
         5.Add all the javascript errors for the page being visited .

        """

        if self.is_valid_web_page():
            response_code, content_type = self.fetch_url()
            link_count = 0
            if not self.external_url:
                if 'text/html' in content_type:
                    self.driver.get(self.url)
                    html_source = self.driver.page_source
                    soup = BeautifulSoup(html_source)
                    link_elements = soup.find_all("a")

                    for a_link in link_elements:
                        link = None
                        if a_link.has_attr('href'):
                            if a_link['href'].startswith('/'):
                                link = self.base_site + a_link['href']
                            else:
                                link = a_link['href']
                        else:
                            continue

                        if link is not None:
                            link_page = WebPage(link, self.base_domain, self.base_site, self.driver)
                            if link_page not in visited_pages \
                                    and link_page not in non_visited_pages \
                                    and link is not None \
                                    and self.is_valid_web_page():
                                self.links.add(link_page)
                                link_page.parent = self
                            link_count += 1

                '''An undetermined hack to get js errors , need to be tested before putting this in '''
                # self.add_errors(self.driver.get_log('browser'))

                errors = self.driver.execute_script("return window.JSErrorCollector_errors.pump()")
                error_messages = list(map(lambda x: x['errorMessage'], errors))
                self.errors = error_messages

                self.visited = True
                self.response_code = response_code
                print("Visited ", self.url, " and added ", link_count, " links to visit ")

    def fetch_url(self):
        """
        Function to fetch the content-type and response code for a url .
        """
        response_code = -1
        content_type = ''
        if self.is_valid_web_page():
            try:
                response = requests.head(self.url, verify=False)
                response_code = response.status_code
                content_type = response.headers.get('Content-Type', '')
            except requests.exceptions.RequestException:
                logging.exception("Error parsing ", self.url)
        return response_code, content_type

    def is_valid_web_page(self):
        regex = "^(https?)://.+$"
        return re.match(regex, self.url)

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url.replace("https", 'http') == other.url.replace("https", 'http')

    def __str__(self):
        return "\nurl: {}" \
               "\n\tResponse Code : {}" \
               "\n\tParent : {}" \
               "\n\tExternal : {}" \
               "\n\tVisited : {}" \
               "\n\tErrors : {}" \
            .format(self.url, self.response_code, self.parent.url if self.parent is not None else '',
                    self.external_url, self.visited, self.errors)


def extract_base_site(url):
    """
    Function to extract the base site url . This is used to form proper working links for the relative links on the
    page.
    """
    extracted = extract(url)
    if extracted.domain.endswith("."):
        return extracted.domain[:-1]
    site = "http://{}.{}.{}".format(extracted.subdomain, extracted.domain, extracted.tld)
    return site


def extract_domain(url):
    """
    Function to obtain the domain name of the web page . This is used for distinguishing pages from within domain from
    pages outside of domain .
    """
    extracted = extract(url)
    domain = "{}.{}".format(extracted.domain, extracted.tld)
    if domain.endswith("."):
        return domain[:-1]
    return domain




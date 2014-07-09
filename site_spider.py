import argparse
import json
import multiprocessing
import tempfile
from threading import Lock
import subprocess
import logging
import sys

from lxml import objectify
import requests

from twisted.internet import task
from twisted.internet.defer import DeferredList, Deferred
from twisted.internet import reactor

from config import DOMAINS_TO_BE_SKIPPED, START_URL, \
    MAX_CONCURRENT_REQUESTS_PER_SERVER, PHANTOM_JS_LOCATION, IDLE_PING_COUNT, \
    ERROR_CODES, DEFAULT_LOGGER_LEVEL
from web_page import extract_domain, extract_base_site, WebPage


logging.basicConfig(filemode='w', level=DEFAULT_LOGGER_LEVEL)
handler = logging.FileHandler('scrapper.log')
logger = logging.getLogger(__name__)
logger.addHandler(handler)

RESOURCES_STATE = dict()
universal_messages = []


class Resource:
    def __init__(self, parent=''):
        self.parent = parent
        self.error = list()
        self.resource_issues = list()

    def add_error(self, error):
        self.error.append(error)
        return self

    def add_resource(self, resource):
        self.resource_issues.append(resource)
        return self

    def __str__(self):
        str = '\n\n%s' % self.parent.encode('utf8')
        errors = ("\nJavascript Errors : \n" + "\n".join(self.error)) if self.error else ""
        resources = ("\nBroken Resources : \n" + "\n".join(self.resource_issues)) if self.resource_issues else ""
        str += errors.encode('utf8')
        str += resources.encode('utf8')
        return str


def print_pages_to_file(file_name, identify_external, page_set,
                        filter_function=None):
    if not filter_function:
        filter_function = lambda wp: wp.external_url == identify_external \
                                     and wp.response_code not in ERROR_CODES \
                                     and 'text/html' in wp.content_type
    list_to_print = sorted(filter(filter_function, page_set))
    with open(file_name, 'w') as output_file:
        for page in list_to_print:
            output_file.write("{}\n".format(page.url))


def print_pages_with_errors(is_external_page, page_set, file_name):
    with open(file_name, 'w') as output_file:
        for error_code in ERROR_CODES:
            pages = sorted(filter((lambda wp: wp.external_url == is_external_page and wp.response_code == error_code), page_set))
            pages.sort(key=lambda x: x.parent)
            parent_page = ''
            for page in pages:
                if parent_page != page.parent.url:
                    parent_page = page.parent.url
                    code = str(error_code)
                    if error_code == -1:
                        code = '-1 (unknown)'
                    output_file.write("\nExamined {} : \nPages with response Code {} : \n".format(parent_page.encode('utf8'), code))
                    print("\nExamined {} : \nPages with response Code {} :".format(parent_page.encode('utf8'), code))
                output_file.write("{} \n".format(page.url.encode('utf8')))
                print("{}".format(page.url.encode('utf8')))


class SiteSpider:
    def __init__(self, start_url, sitemap_url=None):
        self.visited_urls = set()
        self.intermediate_urls = set()
        self.logger = logging.getLogger(__name__)
        self.base_domain = extract_domain(start_url)
        self.base_site = extract_base_site(start_url)
        self.non_visited_urls = {WebPage(start_url, None, start_url, self.base_domain, DOMAINS_TO_BE_SKIPPED)}
        self.added_count = 1
        self.idle_ping = 0
        self.coop = task.Cooperator()
        self.start_idle_counter = False
        self.sitemap_url = '{}/sitemap.xml'.format(self.base_site) if not sitemap_url else sitemap_url

    def filter_visited_links(self, page):
        return page not in self.visited_urls and page not in self.non_visited_urls \
               and page not in self.intermediate_urls

    def add_sitemap_urls(self):
        logger.debug("Adding sitemap urls as well for processing")
        response = requests.get(self.sitemap_url)
        val = bytes(response.text)
        root = objectify.fromstring(val)

        for url in root.url:
            page = WebPage(bytes(url.loc), self.base_site, self.base_site, self.base_domain, DOMAINS_TO_BE_SKIPPED)
            if page not in self.visited_urls and page not in self.non_visited_urls and page not in self.intermediate_urls:
                print("Added {}".format(url.loc))
                self.non_visited_urls.add(page)
                self.added_count += 1

    def get_unique_non_visited_links(self, page):
        l = Lock()
        l.acquire()
        filtered_links = set(filter(self.filter_visited_links, page.links))
        l.release()
        return filtered_links

    def process_web_page(self, resp, web_page):
        logger.debug("Called {} for {}".format('process_web_page', unicode(web_page.url).encode("utf-8")))
        self.visited_urls.add(web_page)
        self.intermediate_urls.discard(web_page)
        unique_links = self.get_unique_non_visited_links(web_page)
        self.non_visited_urls = self.non_visited_urls.union(unique_links)
        self.added_count += len(unique_links)
        self.start_idle_counter = True

    def generate_urls_to_visit(self):
        processed_site_map_url = 0
        while processed_site_map_url < 2:
            while self.idle_ping < IDLE_PING_COUNT:
                print "Total urls added :  {} , Total urls visited : {} , Total urls in process : {}  \r".format(
                    self.added_count, len(self.visited_urls),
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
                    if self.idle_ping == IDLE_PING_COUNT:
                        break
                else:
                    d = Deferred()
                    reactor.callLater(0.1, d.callback, None)
                    yield d

            if sitemap_url:
                self.add_sitemap_urls()
            processed_site_map_url += 1
            self.idle_ping = 0
        raise StopIteration

    def crawl(self):
        logger.debug("Called {}".format('crawl'))
        deferred_list = []
        coop = task.Cooperator()
        work = self.generate_urls_to_visit()
        for i in xrange(MAX_CONCURRENT_REQUESTS_PER_SERVER):
            d = coop.coiterate(work)
            deferred_list.append(d)
        dl = DeferredList(deferred_list)
        dl.addCallback(self.wrap_up)

    def wrap_up(self, resp):
        self.print_stats()
        reactor.stop()

    def print_stats(self):
        """
        Function to print the stats viz: pages with js errors , pages with 404
        error , external and internal pages .
        """
        print_pages_with_errors(True, self.visited_urls, "broken_external_links.txt")
        print_pages_with_errors(False, self.visited_urls, "broken_internal_links.txt")

        print("\nTotal pages visited : {}\n".format(len(self.visited_urls)))

        print_pages_to_file("all_internal_pages.txt", False, self.visited_urls)
        print_pages_to_file("all_external_pages.txt", True, self.visited_urls)


def process_parameters():
    parser = argparse.ArgumentParser(description='A Simple website scrapper')
    parser.add_argument("--url", help="the start url , defaults to the config.ini url", default=START_URL)
    parser.add_argument("--sitemap-url", dest="sitemap_url", help="the sitemap url ")
    parser.add_argument("--url-file", dest="url_file", help="File containing list of urls ", action="store")
    parser.add_argument('--jserrors', dest='testjs', action='store_true')
    parser.add_argument('--no-jserrors', dest='testjs', action='store_false')
    parser.add_argument('--process-exisitng-urls', dest='process_file', action='store')
    parser.set_defaults(testjs=False)
    return parser.parse_args()


def invoke_url_in_browser(file_name):
    resources_state = dict()
    print("\n\nIdentifying the javascript and page loading errors for {}\n\n".format(file_name))
    SCRIPT = 'single_url_invoker.js'
    params = [PHANTOM_JS_LOCATION, SCRIPT, file_name]

    p = subprocess.Popen(params, stdout=subprocess.PIPE, bufsize=1)

    for line in iter(p.stdout.readline, b''):
        print("%s" % line)
        if "parent" in line and ("error" in line or "broken-resource" in line):
            universal_messages.append(line)

            data = json.loads(line)
            parent = data.get('parent')
            error = data.get('error', '')
            broken_resource = data.get('broken-resource', '')
            if not resources_state.get(parent):
                resources_state[parent] = Resource(parent)
            if 'error' in line:
                resource = resources_state[parent].add_error(error)
                resources_state[parent] = resource
            else:
                resources_state[parent] = resources_state[parent].add_resource(broken_resource)
                # else:
                # print("%s" % line)


    p.communicate()
    print("\n\nWrapping for {}\n\n".format(file_name))
    return resources_state


def detect_js_and_resource_issues(file_name):
    try:
        with open(file_name) as f:
            content = f.readlines()

        pool_size = 3 if multiprocessing.cpu_count() * 2 > 3 else multiprocessing.cpu_count() * 2
        print("Breaking original url list file into {} files".format(pool_size))

        prev_count = 0
        offset = len(content) / pool_size
        file_list = []
        file_handles = []
        for index in range(pool_size):
            init_count = prev_count
            prev_count += offset
            list_to_print = content[init_count:prev_count]
            temp = tempfile.NamedTemporaryFile(mode='w+t')
            temp.writelines(list_to_print)
            temp.seek(0)
            file_list.append(temp.name)
            file_handles.append(temp)
            if prev_count >= len(content):
                break

        pool = multiprocessing.Pool(processes=pool_size)
        result = pool.map(invoke_url_in_browser, sorted(file_list))

        with open("js_and_broken_resources.txt", 'w') as output_file:
            for resource_dict in result:
                for parent, resource in resource_dict.iteritems():
                    # print('{}\nErrors : \n{}\nBroken-Resources : \n{}'.format(parent, "\n".join(resource.error), "\n".join(resource.resource_issues)))
                    # output_file.write('{}\nErrors : \n{}\nBroken-Resources : \n{}'.format(parent, "\n".join(resource.error), "\n".join(resource.resource_issues)))
                    print(resource)
                    output_file.write(str(resource))

    finally:
        [file_handle.close() for file_handle in file_handles]


if __name__ == "__main__":

    args = process_parameters()
    base_url = args.url
    sitemap_url = args.sitemap_url
    enable_js_tests = args.testjs
    process_existing_urls = args.process_file
    url_list_file = args.url_file

    if process_existing_urls:
        if not url_list_file:
            print("Missing file containing  url list, please provide one with --url-file parameter")
            sys.exit(1)
        detect_js_and_resource_issues(url_list_file)
        sys.exit(0)

    scrapper = SiteSpider(base_url, sitemap_url)
    reactor.callLater(2, scrapper.crawl)
    reactor.run()

    if enable_js_tests:
        detect_js_and_resource_issues("all_internal_pages.txt")

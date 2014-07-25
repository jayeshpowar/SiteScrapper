import logging

from tldextract import extract

from config import ERROR_CODES


__author__ = 'jayesh'

logger = logging.getLogger(__name__)


def is_url_redirected_to_external_site(url, redirect_location, base_domain):
    url = decode_to_unicode(url)
    redirect_location = decode_to_unicode(redirect_location)
    base_domain = decode_to_unicode(base_domain)
    logger.debug(u"Redirected location is {} for {}", (redirect_location, url))
    redirected_domain = extract_domain(redirect_location)
    logger.debug(u"Redirected domain is {} for {}".format(redirected_domain, url))
    return base_domain in extract_domain(redirected_domain)


def extract_base_site(url):
    extracted = extract(url)
    if extracted.domain.endswith("."):
        return extracted.domain[:-1]
    site = u"http://{}.{}.{}".format(extracted.subdomain, extracted.domain, extracted.tld)
    return site


def extract_domain(url):
    extracted = extract(url)
    domain = u'{}.{}'.format(extracted.domain, extracted.tld)
    if domain.endswith("."):
        return decode_to_unicode(domain[:-1])
    return domain


def print_pages_to_file(file_name, identify_external, page_set, filter_function=None):
    if not filter_function:
        filter_function = lambda wp: wp.is_page_internal() != identify_external \
                                     and wp.response_code not in ERROR_CODES \
                                     and 'text/html' in wp.content_type
    list_to_print = sorted(filter(filter_function, page_set))
    with open(file_name, 'w') as output_file:
        for page in list_to_print:
            output_file.write("{}\n".format(page.url))


def print_pages_with_errors(is_external_page, page_set, file_name):
    with open(file_name, 'w') as output_file:
        for error_code in ERROR_CODES:
            pages = sorted(
                filter((lambda wp: wp.is_page_internal() != is_external_page and wp.response_code == error_code),
                       page_set))
            pages.sort(key=lambda x: x.parent)
            parent_page = ''
            for page in pages:
                failure_message_format = ''
                if not page.parent:
                    continue
                if parent_page != page.parent.url:
                    parent_page = page.parent.url
                    code = str(error_code)
                    if error_code == -1:
                        code = '-1 (unknown)'
                        failure_message_format = '[{}]'
                    output_file.write(
                        "\nExamined {} : \nPages with response Code {} : \n".format(parent_page.encode('utf8'),
                                                                                    code))
                    print(
                    "\nExamined {} : \nPages with response Code {} :".format(parent_page.encode('utf8'), code))
                failure_message = failure_message_format.format(
                    page.failure_message) if failure_message_format else ''
                output_file.write("{} {} \n".format(page.url.encode('utf8'), failure_message))
                print("{} {} ".format(page.url.encode('utf8'), failure_message))


def print_pages_with_hardcoded_links(page_set, file_name):
    with open(file_name, 'w') as output_file:
        for page in page_set:
            if page.hardcoded_urls:
                output_file.write(
                    "\nExamined {} : \nHardcoded links found : {}\n".format(page.url.encode('utf8'),
                                                                            len(page.hardcoded_urls)))
                print("\nExamined {} : \nHardcoded links found : {}\n".format(page.url.encode('utf8'),
                                                                              len(page.hardcoded_urls)))
                for url in page.hardcoded_urls:
                    output_file.write("{} \n".format(url.encode('utf8')))
                    print("{}".format(url.encode('utf8')))


def decode_to_unicode(value):
    if value is None:
        return None
    return value if isinstance(value, unicode) else value.decode('utf-8')


def obtain_domain_with_subdomain_for_page(url):
    link_info = extract(url)
    parsed_link = u"{}.{}.{}".format(link_info.subdomain, link_info.domain, link_info.suffix)
    if not link_info.subdomain:
        parsed_link = u"{}.{}".format(link_info.domain, link_info.suffix)

    return parsed_link
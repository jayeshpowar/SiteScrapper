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


def print_pages_to_file(file_name, identify_external, page_set, filter_function=None,
                        print_parents=False):
    if not filter_function:
        filter_function = lambda wp: wp.external == identify_external \
                                     and wp.response_code not in ERROR_CODES \
                                     and 'text/html' in wp.content_type
    list_to_print = sorted(filter(filter_function, page_set))

    if list_to_print:
        print("Pages to be written %s" % str(len(list_to_print)))
        with open(file_name, 'w') as output_file:
            for page in list_to_print:
                __write_line_to_file(output_file, page, print_parents=print_parents)


def print_pages_with_errors(is_external_page, page_set, file_name):
    with open(file_name, 'w') as output_file:
        for error_code in ERROR_CODES:
            pages = sorted(
                filter((lambda wp: wp.external == is_external_page and wp.response_code == error_code),
                       page_set))
            pages.sort(key=lambda x: x.parent_page.url if x.parent_page else x.url)
            parent_page = ''
            for page in pages:
                failure_message_format = ''
                if not page.parent_page:
                    continue

                if parent_page != page.parent_page.url:
                    parent_page = page.parent_page.url
                    code = str(error_code)
                    if error_code == -1:
                        code = '-1 (unknown)'
                        failure_message_format = '[{}]'
                    line = "\nExamined {} : \nPages with response Code {} : \n".format(parent_page.encode('utf8'), code)
                    __write_line_to_file(output_file, line_to_write=line)
                    # print(
                    # "\nExamined {} : \nPages with response Code {} :".format(parent_page.encode('utf8'), code))
                failure_message = failure_message_format.format(page.failure_message) if failure_message_format else ''

                __write_line_to_file(output_file,
                                     line_to_write="{} {} \n".format(page.url.encode('utf8'), failure_message))


def print_pages_with_hardcoded_links(page_set, file_name):
    with open(file_name, 'w') as output_file:
        for page in page_set:
            if len(page.hardcoded_child_pages) > 0:
                line = "\nExamined {} : \nHardcoded links found : {}\n".format(page.encoded_url,
                                                                               len(page.hardcoded_child_pages))

                __write_line_to_file(output_file, line_to_write=line)
                for hard_coded_page in page.hardcoded_child_pages:
                    __write_line_to_file(output_file, hard_coded_page)


def __write_line_to_file(output_file, page=None, line_to_write=None, print_parents=False):
    try:
        line = page.encoded_url if not line_to_write and page else line_to_write
        # Needed for making the links searchable in the entire list.
        if "debug" in output_file.name:
            output_file.write("{}\n".format(line))
        else:
            output_file.write("{}\n".format(line))
        if page:
            if print_parents and page.parents:
                output_file.write("Referenced By :\n")
                for parent in page.parents:
                    output_file.write("\t\t{}\n".format(parent.url))
    except Exception as e:
        logger.error("Error printing url", e)


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


import urlparse

from tldextract import extract

from config import HARD_CODED_LINKS, HARD_CODED_LINK_EXCLUSIONS, DOMAINS_TO_BE_SKIPPED, URL_SEGMENTS_TO_SKIP
from util import obtain_domain_with_subdomain_for_page, decode_to_unicode, extract_domain


def is_url_hardcoded(url):
    if url:
        if url.startswith(u'http://') or url.startswith(u'https://'):
            link_info = extract(url)
            parsed_link = u"{}.{}.{}".format(link_info.subdomain, link_info.domain, link_info.suffix)

            if 'all' in HARD_CODED_LINKS:
                return True
            else:
                if parsed_link in HARD_CODED_LINKS:
                    for hard_coded_exclusion in HARD_CODED_LINK_EXCLUSIONS:
                        if not hard_coded_exclusion in url:
                            return True
    return False


def is_page_to_be_skipped(url):
    parsed_link = obtain_domain_with_subdomain_for_page(url)
    if parsed_link in DOMAINS_TO_BE_SKIPPED:
        return True

    for segment_to_skip in URL_SEGMENTS_TO_SKIP:
            if segment_to_skip in url:
                return True

    return False


def is_page_internal(url, base_domain):
        url_domain = extract_domain(url)
        if base_domain not in url_domain:
            return False
        return True


def sanitize_url_link(url, href_value):
    href_value = decode_to_unicode(href_value.strip())
    if href_value.startswith('#'):
        return None
    else:
        href_value = href_value.replace("..", "") if href_value.startswith("..") else href_value
        link = urlparse.urljoin(url, href_value, allow_fragments=False)
        link = link if 'javascript:void' not in href_value and not href_value.startswith('mailto') else None
    return None if link == url else decode_to_unicode(link)

import logging

__author__ = 'jayesh'

START_URL = 'http://www.appdynamics.com/'
MAX_CONCURRENT_REQUESTS_PER_SERVER = 50
IDLE_PING_COUNT = 300
# In case to skip a domain of format "http://example.com" give the domain name to skip as '.example.com'
DOMAINS_TO_BE_SKIPPED = ['community.appdynamics.com',
                         'docs.appdynamics.com',
                         'appsphere.appdynamics.com',
                         'liteforums.appdynamics.com',
                         'litedocs.appdynamics.com', 'www.appdynamics.fr',
                         'www.appdynamics.jp', 'appdynamics.com',
                         'www.appdynamics.es', 'www.appdynamics.hk',
                         'www.appdynamics.il', 'www.appdynamics.de',
                         'www.appdynamics.it', 'www.appdynamics.com']
PHANTOM_JS_LOCATION = '/usr/bin/phantomjs'

PAGE_TIMEOUT = 30
ERROR_CODES = [-1, 404, 500, 403]
BROWSER_PROCESS_COUNT = 4
DEFAULT_LOGGER_LEVEL = logging.DEBUG

# Hard code link settings
HARD_CODED_LINKS = ['www.appdynamics.com', 'appdynamics.com']
HARD_CODED_LINK_EXCLUSIONS = ['www.appdynamics.com/info']

# Client implementation
IMPLEMENTATION_CLIENT = 'tornado'
# {'TORNADO':'tornado','TWISTED':'twisted'}

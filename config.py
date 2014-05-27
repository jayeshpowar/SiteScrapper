__author__ = 'jayesh'

START_URL = 'http://www.appdynamics.com/'
MAX_CONCURRENT_REQUESTS_PER_SERVER = 50
IDLE_PING_COUNT = 300
DOMAINS_TO_BE_SKIPPED = ['community.appdynamics.com',
                         'docs.appdynamics.com',
                         'appsphere.appdynamics.com',
                         'liteforums.appdynamics.com',
                         'litedocs.appdynamics.com', 'www.appdynamics.fr',
                         'www.appdynamics.jp',
                         'www.appdynamics.es', 'www.appdynamics.hk',
                         'www.appdynamics.il', 'www.appdynamics.de',
                         'www.appdynamics.it']
PHANTOM_JS_LOCATION = '/usr/bin/phantomjs'

PAGE_TIMEOUT = 30
ERROR_CODES = [404, 500, 403]
import json
import logging
import multiprocessing
import subprocess
import tempfile
from threading import Timer

from config import PHANTOM_JS_LOCATION


logger = logging.getLogger(__name__)


class Resource:
    def __init__(self, parent=''):
        self.parent = parent
        self.error = set()
        self.resource_issues = set()

    def add_error(self, error):
        self.error.add(error)
        return self

    def add_resource(self, resource):
        self.resource_issues.add(resource)
        return self

    def __str__(self):
        str = '\n\nExamined %s' % self.parent.encode('utf8')
        errors = ("\nJavascript Errors : \n" + "\n".join(self.error)) if self.error else ""
        resources = ("\nBroken Resources : \n" + "\n".join(self.resource_issues)) if self.resource_issues else ""
        str += errors.encode('utf8')
        str += resources.encode('utf8')
        return str


def invoke_url_in_browser(file_name):
    resources_state = dict()
    print("\n\nIdentifying the javascript and page loading errors for {}\n\n".format(file_name))
    SCRIPT = 'single_url_invoker.js'
    params = [PHANTOM_JS_LOCATION, SCRIPT, file_name]

    p = subprocess.Popen(params, stdout=subprocess.PIPE, bufsize=1)
    timeout = {"value": False}
    timer = Timer(900, kill_phantom, [p, timeout])
    timer.start()

    for line in iter(p.stdout.readline, b''):
        print("%s" % line)
        if "parent" in line and ("error" in line or "broken-resource" in line):
            data = get_proper_data_from_stream(line)
            if data:
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
    timer.cancel()

    print("\n\nWrapping for {} due to timeout ? {} \n\n".format(file_name, timeout['value']))
    return resources_state


def get_proper_data_from_stream(strieamed_line):
    try:
        return json.loads(strieamed_line)
    except Exception as json_error:
        logger.debug("Skipped line {} for resource processing due to {} ".format(strieamed_line, json_error))
        return None


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


def kill_phantom(proc, timeout):
    timeout["value"] = True
    proc.kill()

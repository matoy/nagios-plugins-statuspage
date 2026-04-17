#!/usr/bin/env python3
#
# Author: Isaac J. Galvan
# Date: 2018-12-04
#
# https://github.com/

import argparse
import datetime
import json
import re
import requests
import urllib3
from json.decoder import JSONDecodeError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Nagios return codes
OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

# Statuspage.io statuses
OPERATIONAL = 'operational'
DEGRADED_PERFORMANCE = 'degraded_performance'
PARTIAL_OUTAGE = 'partial_outage'
MAJOR_OUTAGE = 'major_outage'
UNDER_MAINTENANCE = 'under_maintenance'


class CheckResult():
    def __init__(self):
        self._exitcode = UNKNOWN
        self._message = ''
        self._longmessage = ''
    
    def set_code(self, code):
        self._exitcode = code
    
    def set_message(self, message):
        self._message = message

    def set_longmessage(self, longmessage):
        self._longmessage = longmessage

    def send(self):
        # print the status description message
        print(self._message)

        # print the multi-line long message
        if len(self._longmessage) > 0:
            print(self._longmessage)

        # exit process
        raise SystemExit(self._exitcode)

class ComponentsList():
    def __init__(self, page_id, api_key=None):
        self._url = 'https://{0}.statuspage.io/api/v2/components.json'.format(page_id)
        self._api_key = api_key
    
    def load(self):
        # request the json from statuspage
        params = {}
        if self._api_key:
            params['api_key'] = self._api_key
        r = requests.get(self._url, params=params, verify=False)
        components_json = r.text
        
        self._data = json.loads(components_json)


    def get_component(self, id):
        component_list = self._data.get('components')
        # print(component_list)
        for c in component_list:
            if c.get('id') == id:
                if c.get('group_id'):
                    parent = self.get_component(c.get('group_id'))
                    parent_name = parent.get('name')
                    full_name = '{0} - {1}'.format(parent_name, c.get('name'))
                    c['name'] = full_name

                return c

    def get_all_components(self):
        return self._data.get('components', [])

def main(args):
    #create the result
    result = CheckResult()

    # load the components json
    page_id = args.get('page_id')
    api_key = args.get('api_key')
    components = ComponentsList(page_id, api_key=api_key)
    try:
        components.load()
    except JSONDecodeError:
        message = 'UNKNOWN: page {0} not found'.format(page_id)
        result.set_message(message)
        result.set_code(UNKNOWN)
        result.send()

    # find the component
    component_id = args.get('component_id')

    if component_id:
        component = components.get_component(component_id)
        
        # return unknown if component not found
        if component is None:
            message = 'UNKNOWN: component {0} not found'.format(component_id)
            result.set_message(message)
            result.set_code(UNKNOWN)
            result.send()
            
        # perform check logic
        status = component.get('status')
        name = component.get('name')

        if status == OPERATIONAL:
            message = 'OK: {0} is {1}'.format(name, status)
            result.set_message(message)
            result.set_code(OK)
        elif status == DEGRADED_PERFORMANCE:
            message = 'WARNING: {0} is {1}'.format(name, status)
            result.set_message(message)
            result.set_code(WARNING)
        elif status == PARTIAL_OUTAGE or status == MAJOR_OUTAGE:
            message = 'CRITICAL: {0} is {1}'.format(name, status)
            result.set_message(message)
            result.set_code(CRITICAL)
        else:
            message = 'UNKNOWN: {0} is {1}'.format(name, status)
            result.set_message(message)
            result.set_code(UNKNOWN)
    else:
        # check all components and report worst status
        all_components = components.get_all_components()

        # apply optional regexp filter on component name
        filter_pattern = args.get('filter')
        if filter_pattern:
            try:
                all_components = [c for c in all_components if re.search(filter_pattern, c.get('name', ''))]
            except re.error as e:
                message = 'UNKNOWN: invalid filter regexp: {0}'.format(e)
                result.set_message(message)
                result.set_code(UNKNOWN)
                result.send()

        worst_code = OK
        non_operational = []

        for c in all_components:
            status = c.get('status')
            name = c.get('name')
            if status == MAJOR_OUTAGE or status == PARTIAL_OUTAGE:
                worst_code = CRITICAL
                non_operational.append('{0}: {1}'.format(name, status))
            elif status == DEGRADED_PERFORMANCE:
                if worst_code < WARNING:
                    worst_code = WARNING
                non_operational.append('{0}: {1}'.format(name, status))
            elif status != OPERATIONAL:
                non_operational.append('{0}: {1}'.format(name, status))

        if worst_code == OK:
            result.set_message('OK: All components are operational')
        elif worst_code == WARNING:
            result.set_message('WARNING: {0} component(s) are not fully operational'.format(len(non_operational)))
        else:
            result.set_message('CRITICAL: {0} component(s) are not fully operational'.format(len(non_operational)))

        if args.get('details'):
            all_lines = ['{0}: {1}'.format(c.get('name'), c.get('status')) for c in all_components]
            result.set_longmessage('\n'.join(all_lines))
        elif non_operational:
            result.set_longmessage('\n'.join(non_operational))
        result.set_code(worst_code)

    if component_id and args.get('details') and component:
        details_lines = []
        description = component.get('description') or ''
        if description:
            details_lines.append('Description: {0}'.format(description))
        updated_at = component.get('updated_at') or ''
        if updated_at:
            details_lines.append('Last updated: {0}'.format(updated_at))
        if details_lines:
            result.set_longmessage('\n'.join(details_lines))

    result.send()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='statuspage.io nagios check')
    parser.add_argument('page_id', help='statuspage.io page id')
    parser.add_argument('component_id', nargs='?', default=None, help='component id (optional; checks all components if omitted)')
    parser.add_argument('--api-key', dest='api_key', default=None, help='API key for authentication')
    parser.add_argument('--details', action='store_true', default=False, help='show detailed output for each component')
    parser.add_argument('--filter', dest='filter', default=None, help='regexp pattern to filter components by name (applies when no component_id is given)')

    # args = {}
    args = parser.parse_args()
    main(vars(args))

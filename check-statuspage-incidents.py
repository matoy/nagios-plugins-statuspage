#!/usr/bin/env python3
#
# Author: Isaac J. Galvan
# Date: 2018-12-04
#
# https://github.com/

import argparse
import datetime
import json
import requests
from json.decoder import JSONDecodeError

# Nagios return codes
OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

# Statuspage.io unresolved incident statuses
INVESTIGATING = 'investigating'
IDENTIFIED = 'identified'
MONITORING = 'monitoring'

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

class IncidentList():
    def __init__(self, page_id, api_key=None):
        self._url = 'https://{0}.statuspage.io/api/v2/incidents/unresolved.json'.format(page_id)
        self._api_key = api_key
        self._load()

    def _load(self):
        #request the json from statuspage
        params = {}
        if self._api_key:
            params['api_key'] = self._api_key
        r = requests.get(self._url, params=params)
        incidents_json = r.text
        self._data = json.loads(incidents_json)

    def get_incidents(self, component=None, min_impact=None):
        impact_order = ['none', 'minor', 'major', 'critical']
        incidents = self._data.get('incidents', [])
        filtered = []
        for i in incidents:
            if component:
                affected = [c.get('name', '') for c in i.get('components', [])]
                affected_ids = [c.get('id', '') for c in i.get('components', [])]
                if component not in affected and component not in affected_ids:
                    continue
            if min_impact:
                impact = i.get('impact', 'none')
                if impact_order.index(impact) < impact_order.index(min_impact):
                    continue
            filtered.append(i)
        return filtered

    def get_incident_summary(self, incidents):
        summary = ''
        for i in incidents:
            summary += '{2}: {1} ({0})\n'.format(i.get('shortlink'), i.get('name'), i.get('status').capitalize())
        return summary

def main(args):
    # create the result
    result = CheckResult()

    # load the unresolved incidents json
    page_id = args.get('page_id')
    api_key = args.get('api_key')
    component = args.get('component')
    min_impact = args.get('impact')
    try:
        incidents = IncidentList(page_id, api_key=api_key)
    except:
        result.set_code(UNKNOWN)
        result.set_message('UNKNOWN: Could not load incidents for page {0}'.format(page_id))
        result.send()

    # perform check logic
    filtered = incidents.get_incidents(component=component, min_impact=min_impact)
    count = len(filtered)
    if count == 0:
        result.set_code(OK)
        result.set_message('OK: No unresolved incidents')
    elif count > 0:
        result.set_code(CRITICAL)
        result.set_message('CRITICAL: {0} unresolved incidents(s) reported'.format(count))
        result.set_longmessage(incidents.get_incident_summary(filtered))
    result.send()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='statuspage.io nagios check')
    parser.add_argument('page_id', help='statuspage.io page id')
    parser.add_argument('--api-key', dest='api_key', default=None, help='API key for authentication')
    parser.add_argument('--component', dest='component', default=None, help='filter incidents by affected component name or id')
    parser.add_argument('--impact', dest='impact', default=None, choices=['none', 'minor', 'major', 'critical'],
                        help='minimum impact level to report (none/minor/major/critical)')

    args = parser.parse_args()
    main(vars(args))
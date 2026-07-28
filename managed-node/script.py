# Copyright (c) 2014 Museum Victoria
# Modifications (c) 2019-2026 ACMI
# This software is released under the MIT license.

"""Balena device controls managed by the balena-nodel image."""

from __future__ import print_function

import os
import time

try:
    from urllib import quote
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.parse import quote
    from urllib.request import Request, urlopen


CONTENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content')
SCREENSHOT_FILE = os.path.join(CONTENT_DIR, 'screenshot.png')
SCREENSHOT_URL = os.environ.get(
    'BROWSER_SCREENSHOT_URL',
    'http://127.0.0.1:5011/screenshot',
)


local_event_ScreenshotURL = LocalEvent({
    'title': 'Screenshot URL',
    'desc': 'URL of the most recently captured browser screenshot.',
    'group': 'Display',
    'schema': {'type': 'string'},
})


def supervisor_request(endpoint):
    address = os.environ.get('BALENA_SUPERVISOR_ADDRESS')
    api_key = os.environ.get('BALENA_SUPERVISOR_API_KEY')
    if not address or not api_key:
        raise RuntimeError(
            'Balena Supervisor API is unavailable. Add the '
            'io.balena.features.supervisor-api service label.'
        )

    url = '%s/v1/%s?apikey=%s' % (
        address.rstrip('/'),
        endpoint,
        quote(api_key, safe=''),
    )
    request = Request(url, data=b'{}')
    request.add_header('Content-Type', 'application/json')
    response = urlopen(request, timeout=15)
    try:
        return response.read()
    finally:
        response.close()


def local_action_Reboot(arg=None):
    """{"title":"Reboot","desc":"Reboots this Balena device.","group":"Power","caution":"The device and all of its services will be restarted."}"""
    print('Reboot requested')
    supervisor_request('reboot')
    return 'Reboot requested'


def local_action_Shutdown(arg=None):
    """{"title":"Shutdown","desc":"Shuts down this Balena device.","group":"Power","caution":"The device will remain off until it is powered on again."}"""
    print('Shutdown requested')
    supervisor_request('shutdown')
    return 'Shutdown requested'


def local_action_Screenshot(arg=None):
    """{"title":"Screenshot","desc":"Captures the current Balena browser display.","group":"Display"}"""
    print('Screenshot requested from %s' % SCREENSHOT_URL)
    response = urlopen(SCREENSHOT_URL, timeout=30)
    try:
        image = response.read()
        content_type = response.info().getheader('Content-Type', '')
    finally:
        response.close()

    if not image:
        raise RuntimeError('Browser returned an empty screenshot')
    if content_type and 'image/png' not in content_type.lower():
        raise RuntimeError(
            'Browser returned %s instead of image/png' % content_type
        )

    if not os.path.isdir(CONTENT_DIR):
        os.makedirs(CONTENT_DIR)
    temporary_file = SCREENSHOT_FILE + '.tmp'
    screenshot = open(temporary_file, 'wb')
    try:
        screenshot.write(image)
    finally:
        screenshot.close()
    os.rename(temporary_file, SCREENSHOT_FILE)

    node_name = os.environ.get('NODEL_MANAGED_NODE_NAME', '')
    result_url = '/nodes/%s/content/screenshot.png?ts=%d' % (
        quote(node_name, safe=''),
        int(time.time()),
    )
    local_event_ScreenshotURL.emit(result_url)
    return result_url


def main(arg=None):
    print('Balena device controls started')

# Copyright (c) 2014 Museum Victoria
# Modifications (c) 2019-2026 ACMI
# This software is released under the MIT license.

"""Balena device controls managed by the balena-nodel image."""

from __future__ import print_function

import os
import socket
import sys
import time

try:
    from urllib import quote
    from urllib2 import HTTPError, Request, urlopen
except ImportError:
    from urllib.parse import quote
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

try:
    from org.nodel.discovery import TopologyWatcher
except ImportError:
    TopologyWatcher = None


try:
    NODE_ROOT = str(_node.getRoot().getAbsolutePath())
except NameError:
    # Allows the recipe's pure-Python unit tests to run outside Nodel.
    NODE_ROOT = os.path.dirname(os.path.abspath(__file__))

CONTENT_DIR = os.path.join(NODE_ROOT, 'content')
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


def open_url(request, timeout):
    """Open a URL on CPython and Nodel's older Jython urllib implementation."""
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return urlopen(request)
    finally:
        socket.setdefaulttimeout(previous_timeout)


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
    try:
        response = open_url(request, 15)
    except HTTPError:
        error = sys.exc_info()[1]
        if 200 <= error.code < 300:
            response = error
        else:
            raise
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
    response = open_url(SCREENSHOT_URL, 30)
    try:
        image = response.read()
        response_info = response.info()
        if hasattr(response_info, 'getheader'):
            content_type = response_info.getheader('Content-Type', '')
        else:
            content_type = response_info.get('Content-Type', '')
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


def emit_mac_addresses():
    """Publish this device's interfaces for configuring a remote WOL node."""
    try:
        mac_addresses = TopologyWatcher.shared().getMACAddresses() or []
        for index, mac_address in enumerate(mac_addresses):
            name = 'MAC Address %s' % (index + 1)
            event = lookup_local_event(name)
            if event is None:
                event = create_local_event(name, {
                    'group': 'Network Info',
                    'order': next_seq(),
                    'schema': {
                        'type': 'string',
                        'desc': 'Use the appropriate address for Wake-on-LAN.',
                    },
                })
            event.emit(mac_address)
    except Exception:
        # A scheduled tick can coincide with a node reload or shutdown.
        error = sys.exc_info()[1]
        print('emit_mac_addresses skipped: %s' % error)


if TopologyWatcher is not None:
    mac_emitter = Timer(emit_mac_addresses, 60, 10)


def main(arg=None):
    print('Balena device controls started')

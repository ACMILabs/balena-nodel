# Copyright (c) 2014 Museum Victoria
# Modifications copyright (c) 2019 ACMI
# This software is released under the MIT license (see license.txt for details)

"""This node provides raspberry pi controls."""

import os
import urllib2

BALENA_SUPERVISOR_ADDRESS = javaos.getenv('BALENA_SUPERVISOR_ADDRESS')
BALENA_SUPERVISOR_API_KEY = javaos.getenv('BALENA_SUPERVISOR_API_KEY')

def shutdown():
    url = BALENA_SUPERVISOR_ADDRESS + '/v1/shutdown?apikey=' + BALENA_SUPERVISOR_API_KEY
    print url
    request = urllib2.Request(url)
    request.add_header('Content-Type', 'application/json')
    response = urllib2.urlopen(request)

def reboot():
    url = BALENA_SUPERVISOR_ADDRESS + '/v1/reboot?apikey=' + BALENA_SUPERVISOR_API_KEY
    print url
    request = urllib2.Request(url)
    request.add_header('Content-Type', 'application/json')
    response = urllib2.urlopen(request)


# Local actions this Node provides
def local_action_TurnOff(arg=None):
    """{"title":"Turn off","desc":"Turns this computer off.","group":"Power"}"""
    print 'Action TurnOff requested'
    shutdown()


def local_action_Reboot(arg=None):
    """{"title":"Reboot","desc":"Turns this computer off.","group":"Power","caution":"Ensure hardware is in a state to be rebooted."}"""
    print 'Action Reboot requested'
    reboot()


def main(arg=None):
    # Start your script here.
    print 'Nodel script started.'

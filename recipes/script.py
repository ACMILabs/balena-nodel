# Copyright (c) 2014 Museum Victoria
# Modifications (c) 2019 ACMI
# This software is released under the MIT license (see license.txt for details)

"""This node provides raspberry pi controls."""

import subprocess
import os


def shutdown():
    returncode = subprocess.call('shutdown -h now', shell=True)


def reboot():
    returncode = subprocess.call('reboot now', shell=True)


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

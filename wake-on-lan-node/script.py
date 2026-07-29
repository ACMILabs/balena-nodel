# Adapted from an ACMI Intel computer control recipe.
# This software is released under the MIT license.

"""Wake a remote computer by sending a Wake-on-LAN magic packet."""

from __future__ import print_function

import binascii
import re


DEFAULT_BROADCAST_ADDRESS = '255.255.255.255'
DEFAULT_PORT = 9999
DEFAULT_PACKET_COUNT = 3


param_macAddress = Parameter({
    'title': 'MAC Address',
    'group': 'Wake-on-LAN',
    'schema': {
        'type': 'string',
        'hint': 'AA:BB:CC:DD:EE:FF',
    },
})

param_broadcastAddress = Parameter({
    'title': 'Broadcast Address',
    'group': 'Wake-on-LAN',
    'value': DEFAULT_BROADCAST_ADDRESS,
    'schema': {
        'type': 'string',
        'hint': DEFAULT_BROADCAST_ADDRESS,
    },
})

param_port = Parameter({
    'title': 'UDP Port',
    'group': 'Wake-on-LAN',
    'value': DEFAULT_PORT,
    'schema': {
        'type': 'integer',
        'hint': DEFAULT_PORT,
    },
})

param_packetCount = Parameter({
    'title': 'Packet Count',
    'desc': 'Number of identical magic packets sent by each action.',
    'group': 'Wake-on-LAN',
    'value': DEFAULT_PACKET_COUNT,
    'schema': {
        'type': 'integer',
        'hint': DEFAULT_PACKET_COUNT,
        'minimum': 1,
        'maximum': 10,
    },
})


local_event_LastWakeMACAddress = LocalEvent({
    'title': 'Last Wake MAC Address',
    'desc': 'MAC address used by the most recent Wake-on-LAN action.',
    'group': 'Wake-on-LAN',
    'schema': {'type': 'string'},
})


wol = UDP()


def parameter_text(parameter, default=''):
    if parameter is None:
        return default
    value = str(parameter).strip()
    return value if value else default


def normalize_mac_address(mac_address):
    normalized = re.sub(r'[:-]', '', mac_address.strip()).lower()
    if not re.match(r'^[0-9a-f]{12}$', normalized):
        raise ValueError(
            'MAC address must contain 12 hexadecimal digits, for example '
            'AA:BB:CC:DD:EE:FF'
        )
    return normalized


def build_magic_packet(mac_address):
    mac_bytes = binascii.unhexlify(normalize_mac_address(mac_address))
    header = binascii.unhexlify('ff' * 6)
    return header + mac_bytes * 16


def local_action_SendWakeOnLAN(arg=None):
    """{"title":"Send Wake-on-LAN","desc":"Wakes the configured remote computer.","group":"Wake-on-LAN"}"""
    mac_address = parameter_text(param_macAddress)
    if not mac_address:
        raise RuntimeError('Configure the MAC Address parameter before waking')

    broadcast_address = parameter_text(
        param_broadcastAddress,
        DEFAULT_BROADCAST_ADDRESS,
    )
    port = int(parameter_text(param_port, str(DEFAULT_PORT)))
    packet_count = int(parameter_text(
        param_packetCount,
        str(DEFAULT_PACKET_COUNT),
    ))
    if port < 1 or port > 65535:
        raise ValueError('UDP Port must be between 1 and 65535')
    if packet_count < 1 or packet_count > 10:
        raise ValueError('Packet Count must be between 1 and 10')

    destination = '%s:%d' % (broadcast_address, port)
    packet = build_magic_packet(mac_address)
    wol.setDest(destination)
    for unused in range(packet_count):
        wol.send(packet)

    normalized_mac = normalize_mac_address(mac_address).upper()
    display_mac = ':'.join(
        normalized_mac[index:index + 2]
        for index in range(0, 12, 2)
    )
    local_event_LastWakeMACAddress.emit(display_mac)
    print(
        'Sent %d Wake-on-LAN packet(s) for %s to %s'
        % (packet_count, display_mac, destination)
    )
    return 'Wake-on-LAN packets sent to %s' % display_mac


def main(arg=None):
    print('Wake-on-LAN controls started')

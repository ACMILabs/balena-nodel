#!/usr/bin/env python3
"""Synchronise per-device Nodel names in balenaCloud from a MAC inventory."""

import argparse
import concurrent.futures
import dataclasses
import json
import os
import re
import subprocess
import sys


VARIABLE_NAME = 'NODEL_NODE_NAME'
MAC_PATTERN = re.compile(
    r'(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}'
    r'(?![0-9A-Fa-f])'
)
DEFAULT_INVENTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'inventory',
    'nodel-node-names.tsv',
)


@dataclasses.dataclass(frozen=True)
class InventoryEntry:
    fleet: str
    mac: str
    name: str


@dataclasses.dataclass(frozen=True)
class Device:
    fleet: str
    uuid: str
    current_device_name: str
    macs: tuple


@dataclasses.dataclass(frozen=True)
class Assignment:
    entry: InventoryEntry
    device: Device
    current_value: str = None


class SyncError(RuntimeError):
    pass


def normalize_mac(value):
    normalized = re.sub(r'[:-]', '', value.strip()).upper()
    if not re.match(r'^[0-9A-F]{12}$', normalized):
        raise ValueError('Invalid MAC address: %s' % value)
    return normalized


def display_mac(value):
    normalized = normalize_mac(value)
    return ':'.join(
        normalized[index:index + 2]
        for index in range(0, 12, 2)
    )


def extract_macs(value):
    return tuple(
        normalize_mac(match.group(0))
        for match in MAC_PATTERN.finditer(value or '')
    )


def load_inventory(path):
    entries = []
    seen_macs = {}
    with open(path, 'r', encoding='utf-8') as inventory:
        for line_number, raw_line in enumerate(inventory, 1):
            line = raw_line.rstrip('\r\n')
            if not line or line.lstrip().startswith('#'):
                continue

            parts = line.split('\t', 2)
            if len(parts) != 3:
                raise SyncError(
                    '%s:%d must contain fleet, MAC and name separated by tabs'
                    % (path, line_number)
                )
            fleet, raw_mac, name = (part.strip() for part in parts)
            if not fleet or not name:
                raise SyncError(
                    '%s:%d contains an empty fleet or node name'
                    % (path, line_number)
                )
            try:
                mac = normalize_mac(raw_mac)
            except ValueError as error:
                raise SyncError('%s:%d: %s' % (path, line_number, error))
            if mac in seen_macs:
                raise SyncError(
                    '%s:%d duplicates MAC %s from line %d'
                    % (path, line_number, display_mac(mac), seen_macs[mac])
                )
            seen_macs[mac] = line_number
            entries.append(InventoryEntry(fleet=fleet, mac=mac, name=name))

    if not entries:
        raise SyncError('%s contains no inventory entries' % path)
    return entries


class BalenaCLI:
    def __init__(self, command='balena'):
        self.command = command

    def run(self, arguments, expect_json=False):
        command = [self.command] + list(arguments)
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise SyncError(
                'Command failed (%s): %s'
                % (' '.join(command), detail)
            )
        if not expect_json:
            return result.stdout
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise SyncError(
                'Command returned invalid JSON (%s): %s'
                % (' '.join(command), error)
            )

    def list_devices(self, fleet):
        devices = self.run(
            ['device', 'list', '--fleet', fleet, '--json'],
            expect_json=True,
        )
        return [
            item
            for item in devices
            if item.get('uuid')
        ]

    def get_device(self, uuid):
        detail = self.run(
            ['device', uuid, '--json'],
            expect_json=True,
        )
        return Device(
            fleet=detail.get('fleet') or '',
            uuid=detail['uuid'],
            current_device_name=detail.get('device_name') or '',
            macs=extract_macs(detail.get('mac_address')),
        )

    def get_node_name(self, uuid, service=None):
        arguments = ['env', 'list', '--device', uuid, '--json']
        expected_service = '*'
        if service:
            arguments.extend(['--service', service])
            expected_service = service
        variables = self.run(arguments, expect_json=True)
        matches = [
            variable
            for variable in variables
            if (
                variable.get('name') == VARIABLE_NAME
                and variable.get('deviceUUID') == uuid
                and variable.get('serviceName') == expected_service
            )
        ]
        if len(matches) > 1:
            raise SyncError(
                'Device %s has multiple %s variables in the selected scope'
                % (uuid, VARIABLE_NAME)
            )
        return matches[0].get('value') if matches else None

    def set_node_name(self, uuid, value, service=None):
        arguments = [
            'env',
            'set',
            VARIABLE_NAME,
            value,
            '--device',
            uuid,
        ]
        if service:
            arguments.extend(['--service', service])
        self.run(arguments)


def discover_devices(entries, cli, workers):
    summaries = {}
    for fleet in sorted(set(entry.fleet for entry in entries)):
        for summary in cli.list_devices(fleet):
            summaries[summary['uuid']] = summary

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers,
    ) as executor:
        return list(executor.map(
            cli.get_device,
            sorted(summaries),
        ))


def match_inventory(entries, devices):
    devices_by_fleet_mac = {}
    for device in devices:
        for mac in device.macs:
            devices_by_fleet_mac.setdefault(
                (device.fleet, mac),
                [],
            ).append(device)

    assignments = []
    errors = []
    assigned_devices = {}
    for entry in entries:
        matches = devices_by_fleet_mac.get((entry.fleet, entry.mac), [])
        if not matches:
            errors.append(
                '%s (%s) was not found in %s'
                % (entry.name, display_mac(entry.mac), entry.fleet)
            )
            continue
        if len(matches) > 1:
            errors.append(
                '%s (%s) matched multiple devices in %s: %s'
                % (
                    entry.name,
                    display_mac(entry.mac),
                    entry.fleet,
                    ', '.join(device.uuid for device in matches),
                )
            )
            continue

        device = matches[0]
        previous_entry = assigned_devices.get(device.uuid)
        if previous_entry:
            errors.append(
                'Device %s matched both %s and %s'
                % (device.uuid, previous_entry.name, entry.name)
            )
            continue
        assigned_devices[device.uuid] = entry
        assignments.append(Assignment(entry=entry, device=device))

    if errors:
        raise SyncError('\n'.join(errors))
    return assignments


def add_current_values(assignments, cli, service, workers):
    def with_current_value(assignment):
        return dataclasses.replace(
            assignment,
            current_value=cli.get_node_name(
                assignment.device.uuid,
                service=service,
            ),
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers,
    ) as executor:
        return list(executor.map(with_current_value, assignments))


def print_plan(assignments, service):
    scope = 'service %s' % service if service else 'device-wide'
    print('Scope: %s %s variable' % (scope, VARIABLE_NAME))
    print()
    for assignment in assignments:
        status = (
            'UNCHANGED'
            if assignment.current_value == assignment.entry.name
            else 'UPDATE'
        )
        current = assignment.current_value or '<unset>'
        print(
            '%-9s %s  %s  %s'
            % (
                status,
                display_mac(assignment.entry.mac),
                assignment.device.uuid[:7],
                assignment.entry.name,
            )
        )
        if status == 'UPDATE':
            print(
                '          fleet: %s; current: %s; Balena name: %s'
                % (
                    assignment.entry.fleet,
                    current,
                    assignment.device.current_device_name,
                )
            )


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            'Match a fleet/MAC/name inventory to balenaCloud devices and '
            'synchronise their NODEL_NODE_NAME variable. The default is a '
            'read-only dry run.'
        ),
    )
    parser.add_argument(
        '--inventory',
        default=DEFAULT_INVENTORY,
        help='TSV inventory path (default: %(default)s)',
    )
    parser.add_argument(
        '--service',
        help=(
            'set a service-specific variable, normally "nodel"; omit to set '
            'a device-wide variable before the first Nodel deployment'
        ),
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='apply validated changes; without this flag nothing is changed',
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='maximum concurrent Balena reads (default: %(default)s)',
    )
    parser.add_argument(
        '--balena-command',
        default='balena',
        help=argparse.SUPPRESS,
    )
    return parser


def main(arguments=None):
    options = build_parser().parse_args(arguments)
    if options.workers < 1:
        print('--workers must be at least 1', file=sys.stderr)
        return 2

    try:
        entries = load_inventory(options.inventory)
        cli = BalenaCLI(options.balena_command)
        devices = discover_devices(entries, cli, options.workers)
        assignments = match_inventory(entries, devices)
        assignments = add_current_values(
            assignments,
            cli,
            options.service,
            options.workers,
        )
        print_plan(assignments, options.service)

        changes = [
            assignment
            for assignment in assignments
            if assignment.current_value != assignment.entry.name
        ]
        print()
        if not options.apply:
            print(
                'Dry run: %d change(s) would be applied. '
                'Re-run with --apply after reviewing this plan.'
                % len(changes)
            )
            return 0

        for assignment in changes:
            cli.set_node_name(
                assignment.device.uuid,
                assignment.entry.name,
                service=options.service,
            )
            print(
                'Applied %s to %s'
                % (assignment.entry.name, assignment.device.uuid[:7])
            )
        print('Applied %d change(s).' % len(changes))
        return 0
    except (OSError, SyncError) as error:
        print('ERROR: %s' % error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

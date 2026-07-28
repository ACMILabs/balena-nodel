import builtins
import importlib.util
import os
import unittest
from unittest import mock


class FakeParameter:
    def __init__(self, metadata):
        self.metadata = metadata
        self.value = metadata.get('value', '')

    def __str__(self):
        return str(self.value)


class FakeEvent:
    def __init__(self, metadata):
        self.metadata = metadata
        self.values = []

    def emit(self, value):
        self.values.append(value)


class FakeUDP:
    def __init__(self):
        self.destination = None
        self.packets = []

    def setDest(self, destination):
        self.destination = destination

    def send(self, packet):
        self.packets.append(packet)


def load_recipe():
    recipe_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'wake-on-lan-node',
        'script.py',
    )
    spec = importlib.util.spec_from_file_location('wake_on_lan_recipe', recipe_path)
    module = importlib.util.module_from_spec(spec)
    nodel_globals = {
        'Parameter': FakeParameter,
        'LocalEvent': FakeEvent,
        'UDP': FakeUDP,
    }
    patches = [
        mock.patch.object(builtins, name, value, create=True)
        for name, value in nodel_globals.items()
    ]
    for patch in patches:
        patch.start()
    try:
        spec.loader.exec_module(module)
    finally:
        for patch in reversed(patches):
            patch.stop()
    return module


class WakeOnLANTests(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()

    def test_magic_packet_contains_six_ff_bytes_and_sixteen_mac_addresses(self):
        packet = self.recipe.build_magic_packet('AA:bb:CC:dd:EE:ff')

        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b'\xff' * 6)
        self.assertEqual(
            packet[6:],
            bytes.fromhex('aabbccddeeff') * 16,
        )

    def test_magic_packet_accepts_hyphens_and_rejects_invalid_addresses(self):
        self.assertEqual(
            self.recipe.build_magic_packet('AA-BB-CC-DD-EE-FF'),
            self.recipe.build_magic_packet('AA:BB:CC:DD:EE:FF'),
        )
        with self.assertRaisesRegex(ValueError, '12 hexadecimal digits'):
            self.recipe.build_magic_packet('not-a-mac')

    def test_missing_mac_address_has_a_clear_configuration_error(self):
        self.recipe.param_macAddress.value = ''

        with self.assertRaisesRegex(RuntimeError, 'Configure the MAC Address'):
            self.recipe.local_action_SendWakeOnLAN()

    def test_action_sends_configured_packet_count_and_emits_mac_address(self):
        self.recipe.param_macAddress.value = '01:23:45:67:89:ab'
        self.recipe.param_broadcastAddress.value = '10.20.30.255'
        self.recipe.param_port.value = 9
        self.recipe.param_packetCount.value = 2

        result = self.recipe.local_action_SendWakeOnLAN()

        self.assertEqual(self.recipe.wol.destination, '10.20.30.255:9')
        self.assertEqual(len(self.recipe.wol.packets), 2)
        self.assertEqual(
            self.recipe.wol.packets,
            [self.recipe.build_magic_packet('01:23:45:67:89:ab')] * 2,
        )
        self.assertEqual(
            self.recipe.local_event_LastWakeMACAddress.values,
            ['01:23:45:67:89:AB'],
        )
        self.assertEqual(
            result,
            'Wake-on-LAN packets sent to 01:23:45:67:89:AB',
        )


if __name__ == '__main__':
    unittest.main()

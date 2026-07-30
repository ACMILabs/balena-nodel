import importlib.util
import os
import tempfile
import unittest


def load_module():
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'scripts',
        'sync_node_names.py',
    )
    spec = importlib.util.spec_from_file_location('sync_node_names', script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = load_module()


class InventoryTests(unittest.TestCase):
    def write_inventory(self, content):
        inventory = tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            delete=False,
        )
        self.addCleanup(os.unlink, inventory.name)
        with inventory:
            inventory.write(content)
        return inventory.name

    def test_inventory_supports_names_with_spaces_and_apostrophes(self):
        path = self.write_inventory(
            '# fleet\tMAC\tname\n'
            "org/fleet\tE8:CF:83:46:41:A7\tSecret Seekers's Miro Board\n"
        )

        entries = sync.load_inventory(path)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].fleet, 'org/fleet')
        self.assertEqual(entries[0].mac, 'E8CF834641A7')
        self.assertEqual(entries[0].name, "Secret Seekers's Miro Board")

    def test_inventory_rejects_duplicate_macs(self):
        path = self.write_inventory(
            'org/one\tE8:CF:83:46:41:A7\tFirst\n'
            'org/two\te8-cf-83-46-41-a7\tSecond\n'
        )

        with self.assertRaisesRegex(sync.SyncError, 'duplicates MAC'):
            sync.load_inventory(path)

    def test_inventory_rejects_names_rewritten_by_the_entrypoint(self):
        for node_name in ('Controls/Display', '.', '..'):
            with self.subTest(node_name=node_name):
                path = self.write_inventory(
                    'org/one\tE8:CF:83:46:41:A7\t%s\n' % node_name
                )

                with self.assertRaisesRegex(
                    sync.SyncError,
                    'Nodel cannot use as-is',
                ):
                    sync.load_inventory(path)

    def test_extract_macs_handles_balena_multi_interface_values(self):
        self.assertEqual(
            sync.extract_macs(
                'E8:CF:83:46:6A:C0 26:10:29:F5:8D:E8'
            ),
            ('E8CF83466AC0', '261029F58DE8'),
        )


class MatchingTests(unittest.TestCase):
    def test_inventory_matches_mac_within_its_expected_fleet(self):
        entries = [
            sync.InventoryEntry(
                fleet='org/map',
                mac='E8CF83466AC0',
                name='Map of Neopia',
            ),
        ]
        devices = [
            sync.Device(
                fleet='org/map',
                uuid='correct-device',
                current_device_name='Neopets Map',
                macs=('E8CF83466AC0',),
            ),
            sync.Device(
                fleet='org/other',
                uuid='wrong-fleet',
                current_device_name='Other',
                macs=('E8CF83466AC0',),
            ),
        ]

        assignments = sync.match_inventory(entries, devices)

        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].device.uuid, 'correct-device')

    def test_matching_aborts_when_a_device_is_missing(self):
        entry = sync.InventoryEntry(
            fleet='org/map',
            mac='E8CF83466AC0',
            name='Map of Neopia',
        )

        with self.assertRaisesRegex(sync.SyncError, 'was not found'):
            sync.match_inventory([entry], [])

    def test_matching_aborts_when_one_device_has_two_inventory_names(self):
        entries = [
            sync.InventoryEntry('org/map', 'E8CF83466AC0', 'First'),
            sync.InventoryEntry('org/map', '261029F58DE8', 'Second'),
        ]
        device = sync.Device(
            fleet='org/map',
            uuid='one-device',
            current_device_name='Existing',
            macs=('E8CF83466AC0', '261029F58DE8'),
        )

        with self.assertRaisesRegex(sync.SyncError, 'matched both'):
            sync.match_inventory(entries, [device])


if __name__ == '__main__':
    unittest.main()

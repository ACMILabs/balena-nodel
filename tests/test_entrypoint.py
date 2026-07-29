import os
import unittest


class EntrypointTests(unittest.TestCase):
    def test_managed_node_root_and_content_directory_receive_nodel_ownership(self):
        entrypoint_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'entrypoint.sh',
        )
        with open(entrypoint_path, 'r') as entrypoint:
            source = entrypoint.read()

        self.assertIn(
            'install -d -o nodel -g nodel "$node_dir" "$node_dir/content"',
            source,
        )


if __name__ == '__main__':
    unittest.main()

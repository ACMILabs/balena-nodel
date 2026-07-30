import os
import subprocess
import tempfile
import unittest


class EntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entrypoint_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'entrypoint.sh',
        )
        with open(cls.entrypoint_path, 'r') as entrypoint:
            cls.source = entrypoint.read()

    def run_shell(self, script, *args):
        return subprocess.run(
            ['bash', '-c', script, '_', self.entrypoint_path, *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_nodes_parent_and_managed_directories_receive_nodel_ownership(self):
        self.assertIn(
            'install -d -o nodel -g nodel "$nodes_dir"',
            self.source,
        )
        self.assertIn(
            'install -d -o nodel -g nodel "$node_dir" "$node_dir/content"',
            self.source,
        )

    def test_symlink_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            real_directory = os.path.join(temporary_directory, 'real')
            linked_directory = os.path.join(temporary_directory, 'linked')
            os.mkdir(real_directory)
            os.symlink(real_directory, linked_directory)

            result = self.run_shell(
                'source "$1"\nensure_real_directory "$2"',
                linked_directory,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Refusing to use symlink', result.stderr)

    def test_managed_node_is_moved_when_name_changes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            old_node = os.path.join(nodes_directory, 'Old name')
            new_node = os.path.join(nodes_directory, 'New name')
            state_file = os.path.join(temporary_directory, '.managed-node-name')
            os.makedirs(os.path.join(old_node, 'content'))
            with open(state_file, 'w') as state:
                state.write('Old name\n')

            result = self.run_shell(
                'source "$1"\nmigrate_managed_node "$2" "$3" "New name"',
                nodes_directory,
                state_file,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(os.path.exists(old_node))
            self.assertTrue(os.path.isdir(os.path.join(new_node, 'content')))

    def test_legacy_managed_node_is_discovered_from_its_recipe(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            old_node = os.path.join(nodes_directory, 'Old name')
            managed_recipe = os.path.join(temporary_directory, 'managed.py')
            os.makedirs(old_node)
            with open(managed_recipe, 'w') as recipe:
                recipe.write('# image-managed recipe\n')
            with open(os.path.join(old_node, 'script.py'), 'w') as recipe:
                recipe.write('# image-managed recipe\n')

            result = self.run_shell(
                'source "$1"\n'
                'discover_legacy_managed_node "$2" "New name" "$3"',
                nodes_directory,
                managed_recipe,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'Old name')

    def test_previous_managed_node_is_removed_when_new_name_exists(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            old_node = os.path.join(nodes_directory, 'Old name')
            new_node = os.path.join(nodes_directory, 'New name')
            state_file = os.path.join(temporary_directory, '.managed-node-name')
            os.makedirs(old_node)
            os.makedirs(new_node)
            with open(state_file, 'w') as state:
                state.write('Old name\n')

            result = self.run_shell(
                'source "$1"\nmigrate_managed_node "$2" "$3" "New name"',
                nodes_directory,
                state_file,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(os.path.exists(old_node))
            self.assertTrue(os.path.isdir(new_node))

    def test_root_owned_installs_are_preceded_by_symlink_checks(self):
        content_check = 'ensure_real_directory "$node_dir/content"'
        directory_install = (
            'install -d -o nodel -g nodel "$node_dir" "$node_dir/content"'
        )
        self.assertLess(
            self.source.index(content_check),
            self.source.index(directory_install),
        )
        self.assertIn(
            'ensure_safe_file_destination "$destination"',
            self.source,
        )


if __name__ == '__main__':
    unittest.main()

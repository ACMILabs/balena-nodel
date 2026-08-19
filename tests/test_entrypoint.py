import hashlib
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
                'source "$1"\n'
                'reconcile_tracked_nodes "$2" "$3" "$4" "New name" "$5" ""',
                nodes_directory,
                os.path.join(temporary_directory, '.migration'),
                state_file,
                os.path.join(temporary_directory, '.wol-node-name'),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(os.path.exists(old_node))
            self.assertTrue(os.path.isdir(os.path.join(new_node, 'content')))

    def test_legacy_node_is_discovered_from_any_known_recipe(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            old_node = os.path.join(nodes_directory, 'Old name')
            managed_recipe = os.path.join(temporary_directory, 'managed.py')
            legacy_recipe = os.path.join(temporary_directory, 'legacy.py')
            os.makedirs(old_node)
            with open(managed_recipe, 'w') as recipe:
                recipe.write('# current image-managed recipe\n')
            with open(legacy_recipe, 'w') as recipe:
                recipe.write('# old image-managed recipe\n')
            with open(os.path.join(old_node, 'script.py'), 'w') as recipe:
                recipe.write('# old image-managed recipe\n')

            result = self.run_shell(
                'source "$1"\n'
                'discover_legacy_node "$2" "New name" "$3" "$4"',
                nodes_directory,
                managed_recipe,
                legacy_recipe,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'Old name')

    def test_master_migration_recipe_is_the_pre_upgrade_recipe(self):
        recipe_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'migration',
            'master-managed-node.py',
        )
        with open(recipe_path, 'rb') as recipe:
            digest = hashlib.sha256(recipe.read()).hexdigest()

        self.assertEqual(
            digest,
            'bc912a06b6351140b64b0e3b0a8e8a60'
            'ee42a93a1a3ee1d719e3635480e90940',
        )

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
                'source "$1"\n'
                'reconcile_tracked_nodes "$2" "$3" "$4" "New name" "$5" ""',
                nodes_directory,
                os.path.join(temporary_directory, '.migration'),
                state_file,
                os.path.join(temporary_directory, '.wol-node-name'),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(os.path.exists(old_node))
            self.assertTrue(os.path.isdir(new_node))

    def test_wol_node_is_moved_when_name_changes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            old_node = os.path.join(nodes_directory, 'Old WOL')
            new_node = os.path.join(nodes_directory, 'New WOL')
            state_file = os.path.join(temporary_directory, '.wol-node-name')
            os.makedirs(old_node)
            with open(state_file, 'w') as state:
                state.write('Old WOL\n')

            result = self.run_shell(
                'source "$1"\n'
                'reconcile_tracked_nodes "$2" "$3" "$4" "Managed" '
                '"$5" "New WOL"',
                nodes_directory,
                os.path.join(temporary_directory, '.migration'),
                os.path.join(temporary_directory, '.managed-node-name'),
                state_file,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(os.path.exists(old_node))
            self.assertTrue(os.path.isdir(new_node))

    def test_wol_node_is_removed_when_disabled(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            old_node = os.path.join(nodes_directory, 'Old WOL')
            state_file = os.path.join(temporary_directory, '.wol-node-name')
            os.makedirs(old_node)
            with open(state_file, 'w') as state:
                state.write('Old WOL\n')

            result = self.run_shell(
                'source "$1"\n'
                'reconcile_tracked_nodes "$2" "$3" "$4" "Managed" "$5" ""',
                nodes_directory,
                os.path.join(temporary_directory, '.migration'),
                os.path.join(temporary_directory, '.managed-node-name'),
                state_file,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(os.path.exists(old_node))

    def test_crossed_names_preserve_both_node_directories(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            nodes_directory = os.path.join(temporary_directory, 'nodes')
            migration_directory = os.path.join(
                temporary_directory,
                '.migration',
            )
            managed_state = os.path.join(
                temporary_directory,
                '.managed-node-name',
            )
            wol_state = os.path.join(
                temporary_directory,
                '.wol-node-name',
            )
            old_managed = os.path.join(nodes_directory, 'Managed A')
            old_wol = os.path.join(nodes_directory, 'WOL B')
            new_managed = os.path.join(nodes_directory, 'Managed C')
            new_wol = os.path.join(nodes_directory, 'Managed A')
            os.makedirs(old_managed)
            os.makedirs(old_wol)
            with open(os.path.join(old_managed, 'managed-marker'), 'w'):
                pass
            with open(os.path.join(old_wol, 'wol-marker'), 'w'):
                pass
            with open(managed_state, 'w') as state:
                state.write('Managed A\n')
            with open(wol_state, 'w') as state:
                state.write('WOL B\n')

            result = self.run_shell(
                'source "$1"\n'
                'reconcile_tracked_nodes "$2" "$3" "$4" "Managed C" '
                '"$5" "Managed A"',
                nodes_directory,
                migration_directory,
                managed_state,
                wol_state,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                os.path.isfile(os.path.join(new_managed, 'managed-marker'))
            )
            self.assertTrue(
                os.path.isfile(os.path.join(new_wol, 'wol-marker'))
            )

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

import os
import unittest


class DockerContextTests(unittest.TestCase):
    def test_build_context_is_an_allowlist_without_inventory(self):
        dockerignore_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '.dockerignore',
        )
        with open(dockerignore_path, 'r') as dockerignore:
            patterns = {
                line.strip()
                for line in dockerignore
                if line.strip() and not line.lstrip().startswith('#')
            }

        self.assertEqual(
            patterns,
            {
                '**',
                '!Dockerfile',
                '!entrypoint.sh',
                '!managed-node/',
                '!managed-node/script.py',
                '!migration/',
                '!migration/master-managed-node.py',
                '!wake-on-lan-node/',
                '!wake-on-lan-node/script.py',
            },
        )


if __name__ == '__main__':
    unittest.main()

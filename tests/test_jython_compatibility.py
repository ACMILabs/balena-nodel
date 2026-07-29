import os
import re
import unittest


RECIPE_DIRECTORIES = ('managed-node', 'wake-on-lan-node')


class JythonCompatibilityTests(unittest.TestCase):
    def test_recipes_avoid_syntax_rejected_by_nodels_embedded_jython(self):
        repository_root = os.path.dirname(os.path.dirname(__file__))

        for recipe_directory in RECIPE_DIRECTORIES:
            script_path = os.path.join(
                repository_root,
                recipe_directory,
                'script.py',
            )
            with open(script_path, 'r') as script:
                source = script.read()

            self.assertNotIn(
                'from __future__ import print_function',
                source,
                script_path,
            )
            self.assertIsNone(
                re.search(r"\bb[\"']", source),
                script_path,
            )
            self.assertIsNone(
                re.search(r'except\s+[^:\n]+\s+as\s+\w+\s*:', source),
                script_path,
            )


if __name__ == '__main__':
    unittest.main()

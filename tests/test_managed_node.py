import builtins
import importlib.util
import os
import tempfile
import unittest
from unittest import mock


class FakeEvent:
    def __init__(self, metadata):
        self.metadata = metadata
        self.values = []

    def emit(self, value):
        self.values.append(value)


class FakeHeaders:
    def __init__(self, content_type):
        self.content_type = content_type

    def getheader(self, name, default=None):
        if name.lower() == 'content-type':
            return self.content_type
        return default


class FakeResponse:
    def __init__(self, body=b'', content_type='application/json'):
        self.body = body
        self.headers = FakeHeaders(content_type)
        self.closed = False

    def read(self):
        return self.body

    def info(self):
        return self.headers

    def close(self):
        self.closed = True


def load_recipe():
    recipe_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'managed-node',
        'script.py',
    )
    spec = importlib.util.spec_from_file_location('managed_node_recipe', recipe_path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(builtins, 'LocalEvent', FakeEvent, create=True):
        spec.loader.exec_module(module)
    return module


class ManagedNodeTests(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()

    def test_supervisor_request_posts_to_the_requested_endpoint(self):
        response = FakeResponse(body=b'OK')
        with mock.patch.dict(
            os.environ,
            {
                'BALENA_SUPERVISOR_ADDRESS': 'http://supervisor',
                'BALENA_SUPERVISOR_API_KEY': 'key with spaces',
            },
            clear=False,
        ), mock.patch.object(
            self.recipe,
            'urlopen',
            return_value=response,
        ) as urlopen:
            result = self.recipe.supervisor_request('reboot')

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            'http://supervisor/v1/reboot?apikey=key%20with%20spaces',
        )
        self.assertEqual(request.data, b'{}')
        self.assertEqual(result, b'OK')
        self.assertTrue(response.closed)

    def test_supervisor_request_explains_a_missing_feature_label(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'supervisor-api'):
                self.recipe.supervisor_request('shutdown')

    def test_screenshot_is_saved_and_emits_its_nodel_url(self):
        response = FakeResponse(body=b'PNG DATA', content_type='image/png')
        with tempfile.TemporaryDirectory() as directory:
            self.recipe.CONTENT_DIR = directory
            self.recipe.SCREENSHOT_FILE = os.path.join(directory, 'screenshot.png')
            with mock.patch.dict(
                os.environ,
                {'NODEL_MANAGED_NODE_NAME': 'Gallery Controls'},
                clear=False,
            ), mock.patch.object(
                self.recipe,
                'urlopen',
                return_value=response,
            ):
                result = self.recipe.local_action_Screenshot()

            with open(self.recipe.SCREENSHOT_FILE, 'rb') as screenshot:
                self.assertEqual(screenshot.read(), b'PNG DATA')

        self.assertRegex(
            result,
            r'^/nodes/Gallery%20Controls/content/screenshot\.png\?ts=\d+$',
        )
        self.assertEqual(
            self.recipe.local_event_ScreenshotURL.values,
            [result],
        )
        self.assertTrue(response.closed)


if __name__ == '__main__':
    unittest.main()

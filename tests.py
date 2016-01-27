import contextlib
import logging
import os
import json
import time
import unittest

from tornado import httputil, testing, web
import mock

import sprockets.http.mixins
import sprockets.http.runner
import examples


class RecordingHandler(logging.Handler):

    def __init__(self):
        super(RecordingHandler, self).__init__()
        self.emitted = []

    def emit(self, record):
        self.emitted.append((record, self.format(record)))


class RaisingHandler(sprockets.http.mixins.ErrorLogger,
                     sprockets.http.mixins.ErrorWriter,
                     web.RequestHandler):

    def get(self, status_code):
        raise web.HTTPError(int(status_code),
                            reason=self.get_query_argument('reason', None))


class MockHelper(unittest.TestCase):

    def setUp(self):
        super(MockHelper, self).setUp()
        self._mocks = []

    def tearDown(self):
        super(MockHelper, self).tearDown()
        for mocker in self._mocks:
            mocker.stop()
        del self._mocks[:]

    def start_mock(self, target):
        mocked = mock.patch(target)
        self._mocks.append(mocked)
        return mocked.start()


@contextlib.contextmanager
def override_environment_variable(name, value):
    stash = os.environ.pop(name, None)
    if value is not None:
        os.environ[name] = value
    try:
        yield
    finally:
        os.environ.pop(name, None)
        if stash is not None:
            os.environ[name] = stash


class ErrorLoggerTests(testing.AsyncHTTPTestCase):

    def setUp(self):
        super(ErrorLoggerTests, self).setUp()
        self.recorder = RecordingHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(self.recorder)

    def tearDown(self):
        super(ErrorLoggerTests, self).tearDown()
        logging.getLogger().removeHandler(self.recorder)

    def get_app(self):
        return web.Application([
            web.url(r'/status/(?P<status_code>\d+)', examples.StatusHandler),
            web.url(r'/fail/(?P<status_code>\d+)', RaisingHandler),
        ])

    def assert_message_logged(self, level, msg_fmt, *msg_args):
        suffix = msg_fmt.format(*msg_args)
        for record, message in self.recorder.emitted:
            if record.levelno == level and message.endswith(suffix):
                return
        self.fail('Expected message ending in "%s" to be logged in %r'
                  % (suffix, self.recorder.emitted))

    def test_that_client_error_logged_as_warning(self):
        self.fetch('/status/400')
        self.assert_message_logged(
            logging.WARNING, 'failed with 400: {}', httputil.responses[400])

    def test_that_server_error_logged_as_error(self):
        self.fetch('/status/500')
        self.assert_message_logged(
            logging.ERROR, 'failed with 500: {}', httputil.responses[500])

    def test_that_custom_status_codes_logged_as_unknown(self):
        self.fetch('/status/623')
        self.assert_message_logged(logging.ERROR, 'failed with 623: Unknown')

    def test_that_custom_reasons_are_supported(self):
        self.fetch('/status/456?reason=oops')
        self.assert_message_logged(logging.WARNING, 'failed with 456: oops')

    def test_that_status_code_extracted_from_http_errors(self):
        self.fetch('/fail/400')
        self.assert_message_logged(
            logging.WARNING, 'failed with 400: {}', httputil.responses[400])

    def test_that_reason_extracted_from_http_errors(self):
        self.fetch('/fail/400?reason=oopsie')
        self.assert_message_logged(logging.WARNING, 'failed with 400: oopsie')

    def test_that_log_message_is_honored(self):
        self.fetch('/status/400?log_message=injected%20message')
        self.assert_message_logged(logging.WARNING,
                                   'failed with 400: injected message')


class ErrorWriterTests(testing.AsyncHTTPTestCase):

    def setUp(self):
        self._application = None
        super(ErrorWriterTests, self).setUp()

    @property
    def application(self):
        if self._application is None:
            self._application = web.Application([
                web.url(r'/status/(?P<status_code>\d+)',
                        examples.StatusHandler),
                web.url(r'/fail/(?P<status_code>\d+)', RaisingHandler),
            ])
        return self._application

    def get_app(self):
        return self.application

    def _decode_response(self, response):
        content_type = response.headers['Content-Type']
        self.assertTrue(content_type.startswith('application/json'),
                        'Incorrect content type received')
        return json.loads(response.body.decode('utf-8'))

    def test_that_error_json_contains_error_type(self):
        response = self.fetch('/fail/400')
        self.assertEqual(response.code, 400)

        exc = web.HTTPError(400)
        body = self._decode_response(response)
        self.assertEqual(body['type'], exc.__class__.__name__)

    def test_that_error_json_contains_error_message(self):
        response = self.fetch('/fail/400')
        self.assertEqual(response.code, 400)

        exc = web.HTTPError(400)
        body = self._decode_response(response)
        self.assertEqual(body['message'], str(exc))

    def test_that_error_json_ignores_the_log_message(self):
        response = self.fetch('/status/500?log_message=something%20good')
        self.assertEqual(response.code, 500)

        body = self._decode_response(response)
        self.assertEqual(body['message'], httputil.responses[500])

    def test_that_error_json_contains_type_none_for_non_exceptions(self):
        response = self.fetch('/status/500')
        self.assertEqual(response.code, 500)

        body = self._decode_response(response)
        self.assertIsNone(body['type'])

    def test_that_error_json_contains_reason_for_non_exceptions(self):
        response = self.fetch('/status/500')
        self.assertEqual(response.code, 500)

        body = self._decode_response(response)
        self.assertEqual(body['message'], httputil.responses[500])

    def test_that_error_json_reason_contains_unknown_in_some_cases(self):
        response = self.fetch('/status/567')
        self.assertEqual(response.code, 567)

        body = self._decode_response(response)
        self.assertEqual(body['message'], 'Unknown')

    def test_that_error_json_honors_serve_traceback(self):
        self.application.settings['serve_traceback'] = True

        response = self.fetch('/fail/400')
        self.assertEqual(response.code, 400)

        body = self._decode_response(response)
        self.assertGreater(len(body['traceback']), 0)

    def test_that_mediatype_mixin_is_honored(self):
        send_response = mock.Mock()
        setattr(examples.StatusHandler, 'send_response', send_response)
        response = self.fetch('/status/500')
        self.assertEqual(response.code, 500)
        send_response.assert_called_once_with({
            'type': None,
            'message': 'Internal Server Error',
            'traceback': None
        })
        delattr(examples.StatusHandler, 'send_response')


class RunTests(MockHelper, unittest.TestCase):

    def setUp(self):
        super(RunTests, self).setUp()
        self.runner_cls = self.start_mock('sprockets.http.runner.Runner')
        self.get_logging_config = self.start_mock(
            'sprockets.http._get_logging_config')
        self.get_logging_config.return_value = {'version': 1}
        self.logging_dict_config = self.start_mock(
            'sprockets.http.logging.config').dictConfig

    @property
    def runner_instance(self):
        return self.runner_cls.return_value

    def test_that_runner_run_called_with_created_application(self):
        create_app = mock.Mock()
        sprockets.http.run(create_app)
        self.assertEqual(create_app.call_count, 1)
        self.runner_cls.assert_called_once_with(create_app.return_value)

    def test_that_debug_envvar_enables_debug_flag(self):
        create_app = mock.Mock()
        with override_environment_variable('DEBUG', '1'):
            sprockets.http.run(create_app)
            create_app.assert_called_once_with(debug=True)
            self.get_logging_config.assert_called_once_with(True)

    def test_that_false_debug_envvar_disables_debug_flag(self):
        create_app = mock.Mock()
        with override_environment_variable('DEBUG', '0'):
            sprockets.http.run(create_app)
            create_app.assert_called_once_with(debug=False)
            self.get_logging_config.assert_called_once_with(False)

    def test_that_unset_debug_envvar_disables_debug_flag(self):
        create_app = mock.Mock()
        with override_environment_variable('DEBUG', None):
            sprockets.http.run(create_app)
            create_app.assert_called_once_with(debug=False)
            self.get_logging_config.assert_called_once_with(False)

    def test_that_port_defaults_to_8000(self):
        sprockets.http.run(mock.Mock())
        self.runner_instance.run.called_once_with(8000, mock.ANY)

    def test_that_port_envvar_sets_port_number(self):
        with override_environment_variable('PORT', '8888'):
            sprockets.http.run(mock.Mock())
            self.runner_instance.run.called_once_with(8888, mock.ANY)

    def test_that_port_kwarg_sets_port_number(self):
        sprockets.http.run(mock.Mock(), settings={'port': 8888})
        self.runner_instance.run.assert_called_once_with(8888, mock.ANY)

    def test_that_number_of_procs_defaults_to_zero(self):
        sprockets.http.run(mock.Mock())
        self.runner_instance.run.assert_called_once_with(mock.ANY, 0)

    def test_that_number_of_process_kwarg_sets_number_of_procs(self):
        sprockets.http.run(mock.Mock(), settings={'number_of_procs': 1})
        self.runner_instance.run.assert_called_once_with(mock.ANY, 1)

    def test_that_logging_dict_config_is_called_appropriately(self):
        sprockets.http.run(mock.Mock())
        self.logging_dict_config.assert_called_once_with(
            self.get_logging_config.return_value)

    def test_that_logconfig_override_is_used(self):
        sprockets.http.run(mock.Mock(), log_config=mock.sentinel.config)
        self.logging_dict_config.assert_called_once_with(
            mock.sentinel.config)


class CallbackTests(unittest.TestCase):

    def setUp(self):
        super(CallbackTests, self).setUp()
        self.application = mock.Mock()
        self.shutdown_callback = mock.Mock()

    def make_application(self, **settings):
        self.application.settings = settings.copy()
        self.application.runner_callbacks = {
            'shutdown': [self.shutdown_callback],
        }
        return self.application

    def test_that_shutdown_callback_invoked(self):
        with mock.patch('sprockets.http.runner.ioloop') as ioloop:
            iol = mock.Mock(_callbacks=[], _timeouts=[])
            iol.time.side_effect = time.time
            ioloop.IOLoop.instance.return_value = iol
            with mock.patch('sprockets.http.runner.httpserver'):
                runner = sprockets.http.runner.Runner(self.make_application())
                runner.run(8080)
                runner._shutdown()
        self.shutdown_callback.assert_called_once_with(self.application)

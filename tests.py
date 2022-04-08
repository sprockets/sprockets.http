from unittest import mock
import contextlib
import datetime
import distutils.dist
import distutils.errors
import json
import logging
import os
import re
import time
import unittest
import uuid
import warnings

from tornado import concurrent, httpserver, httputil, ioloop, log, testing, web

import sprockets.http.app
import sprockets.http.mixins
import sprockets.http.runner
import sprockets.http.testing
import examples


class RecordingHandler(logging.Handler):

    def __init__(self):
        super().__init__()
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
        super().setUp()
        self._mocks = []

    def tearDown(self):
        super().tearDown()
        for mocker in self._mocks:
            mocker.stop()
        del self._mocks[:]

    def start_mock(self, target, existing_mock=None):
        target_mock = mock.Mock() if existing_mock is None else existing_mock
        mocked = mock.patch(target, target_mock)
        self._mocks.append(mocked)
        return mocked.start()


@contextlib.contextmanager
def override_environment_variable(**env_vars):
    stash = {}
    for name, value in env_vars.items():
        stash[name] = os.environ.pop(name, None)
        if value is not None:
            os.environ[name] = value
    try:
        yield
    finally:
        for name, value in stash.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value


class ErrorLoggerTests(testing.AsyncHTTPTestCase):

    def setUp(self):
        super().setUp()
        self.recorder = RecordingHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(self.recorder)

    def tearDown(self):
        super().tearDown()
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
        super().setUp()

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
        super().setUp()
        self.runner_cls = self.start_mock('sprockets.http.runner.Runner')
        self.get_logging_config = self.start_mock(
            'sprockets.http._get_logging_config')
        self.get_logging_config.return_value = {'version': 1}
        self.logging_dict_config = self.start_mock(
            'sprockets.http.logging.config').dictConfig

        self.app = mock.Mock()
        self.app.settings = {}
        self.create_app = mock.Mock(return_value=self.app)

    @property
    def runner_instance(self):
        return self.runner_cls.return_value

    def test_that_runner_run_called_with_created_application(self):
        sprockets.http.run(self.create_app)
        self.assertEqual(self.create_app.call_count, 1)
        self.runner_cls.assert_called_once_with(self.create_app.return_value)

    def test_that_debug_envvar_enables_debug_flag(self):
        with override_environment_variable(DEBUG='1'):
            sprockets.http.run(self.create_app)
            self.create_app.assert_called_once_with(debug=True)
            self.get_logging_config.assert_called_once_with(True)

    def test_that_false_debug_envvar_disables_debug_flag(self):
        with override_environment_variable(DEBUG='0'):
            sprockets.http.run(self.create_app)
            self.create_app.assert_called_once_with(debug=False)
            self.get_logging_config.assert_called_once_with(False)

    def test_that_unset_debug_envvar_disables_debug_flag(self):
        with override_environment_variable(DEBUG=None):
            sprockets.http.run(self.create_app)
            self.create_app.assert_called_once_with(debug=False)
            self.get_logging_config.assert_called_once_with(False)

    def test_that_port_defaults_to_8000(self):
        sprockets.http.run(self.create_app)
        self.runner_instance.run.assert_called_once_with(8000, mock.ANY)

    def test_that_port_envvar_sets_port_number(self):
        with override_environment_variable(PORT='8888'):
            sprockets.http.run(self.create_app)
            self.runner_instance.run.assert_called_once_with(8888, mock.ANY)

    def test_that_port_kwarg_sets_port_number(self):
        sprockets.http.run(self.create_app, settings={'port': 8888})
        self.runner_instance.run.assert_called_once_with(8888, mock.ANY)

    def test_that_number_of_procs_defaults_to_one(self):
        sprockets.http.run(self.create_app)
        self.runner_instance.run.assert_called_once_with(mock.ANY, 1)

    def test_that_number_of_process_kwarg_sets_number_of_procs(self):
        sprockets.http.run(self.create_app, settings={'number_of_procs': 2})
        self.runner_instance.run.assert_called_once_with(mock.ANY, 2)

    def test_that_logging_dict_config_is_called_appropriately(self):
        sprockets.http.run(self.create_app)
        self.logging_dict_config.assert_called_once_with(
            self.get_logging_config.return_value)

    def test_that_logconfig_override_is_used(self):
        sprockets.http.run(self.create_app, log_config=mock.sentinel.config)
        self.logging_dict_config.assert_called_once_with(
            mock.sentinel.config)

    def test_that_not_specifying_logging_config_is_deprecated(self):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            sprockets.http.run(self.create_app)

        self.assertEqual(len(captured), 1)
        self.assertTrue(issubclass(captured[0].category, DeprecationWarning))

    @mock.patch('sentry_sdk.init')
    def test_that_sentry_is_initialized_with_implied_overrides(
            self, mock_sentry_init):
        self.app.settings = {
            'environment': 'whatever',
            'version': 'a.b.c',
        }
        sprockets.http.run(self.create_app)
        mock_sentry_init.assert_called_once_with(
            integrations=sprockets.http._sentry_integrations,
            release='a.b.c',
            environment='whatever',
        )

    @mock.patch('sentry_sdk.init')
    def test_that_sentry_is_initialized_with_explicit_overrides(
            self, mock_sentry_init):
        self.app.settings = {
            'sentry_sdk_init': {
                'before_send': mock.sentinel.before_send,
                'integrations': mock.sentinel.integrations,
                'environment': mock.sentinel.environment,
                'release': mock.sentinel.release,
            },
            'environment': 'whatever',
            'version': 'a.b.c',
        }
        sprockets.http.run(self.create_app)
        mock_sentry_init.assert_called_once_with(
            integrations=mock.sentinel.integrations,
            before_send=mock.sentinel.before_send,
            release=mock.sentinel.release,
            environment=mock.sentinel.environment,
        )

    @mock.patch('sentry_sdk.init')
    def test_that_sentry_is_initialized_with_defaults(self, mock_sentry_init):
        self.app.settings = {}
        sprockets.http.run(self.create_app)
        mock_sentry_init.assert_called_once_with(
            integrations=sprockets.http._sentry_integrations,
            release=None,
            environment=None,
        )


class CallbackTests(MockHelper, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.shutdown_callback = mock.Mock()
        self.before_run_callback = mock.Mock()
        self.application = self.make_application()

        self.io_loop = mock.Mock(_callbacks=[], _timeouts=[])
        self.io_loop.time.side_effect = time.time
        ioloop_module = self.start_mock('sprockets.http.runner.ioloop')
        ioloop_module.IOLoop.instance.return_value = self.io_loop

        self.start_mock('sprockets.http.runner.httpserver')

    def make_application(self, **settings):
        application = mock.Mock()
        application.settings = settings.copy()
        application.runner_callbacks = {
            'before_run': [self.before_run_callback],
            'shutdown': [self.shutdown_callback],
        }
        return application

    def test_that_shutdown_callback_invoked(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8080)
        runner._shutdown()
        self.shutdown_callback.assert_called_once_with(self.application)

    def test_that_exceptions_from_shutdown_callbacks_are_ignored(self):
        another_callback = mock.Mock()
        self.application.runner_callbacks['shutdown'].append(another_callback)
        self.shutdown_callback.side_effect = Exception

        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8080)
        runner._shutdown()
        self.shutdown_callback.assert_called_once_with(self.application)
        another_callback.assert_called_once_with(self.application)

    def test_that_before_run_callback_invoked(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8080)
        self.before_run_callback.assert_called_once_with(self.application,
                                                         self.io_loop)

    def test_that_exceptions_from_before_run_callbacks_are_terminal(self):
        another_callback = mock.Mock()
        self.application.runner_callbacks['before_run'].append(
            another_callback)
        self.before_run_callback.side_effect = Exception

        sys_exit = mock.Mock()
        sys_exit.side_effect = SystemExit
        with mock.patch('sprockets.http.runner.sys') as sys_module:
            sys_module.exit = sys_exit
            with self.assertRaises(SystemExit):
                runner = sprockets.http.runner.Runner(self.application)
                runner.run(8080)

        self.before_run_callback.assert_called_once_with(self.application,
                                                         self.io_loop)
        another_callback.assert_not_called()
        self.shutdown_callback.assert_called_once_with(self.application)
        sys_exit.assert_called_once_with(70)


class RunnerTests(MockHelper, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.application = mock.Mock()
        self.application.settings = {
            'xheaders': True,
            'max_body_size': 2048,
            'max_buffer_size': 1024
        }
        self.application.runner_callbacks = {}

        self.io_loop = mock.Mock()
        self.io_loop._callbacks = []
        self.io_loop._timeouts = []
        self.io_loop.time = time.time
        ioloop_module = self.start_mock('sprockets.http.runner.ioloop')
        ioloop_module.IOLoop.instance.return_value = self.io_loop

        self.http_server = mock.Mock(spec=httpserver.HTTPServer)
        self.httpserver_module = \
            self.start_mock('sprockets.http.runner.httpserver')
        self.httpserver_module.HTTPServer.return_value = self.http_server

    def test_that_run_starts_ioloop(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        self.io_loop.start.assert_called_once_with()

    def test_that_http_server_settings_are_used(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        self.httpserver_module.HTTPServer.assert_called_once_with(
            self.application, **self.application.settings)

    def test_that_production_run_starts_in_single_process_mode(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)

        self.assertTrue(self.http_server.bind.called)
        args, kwargs = self.http_server.bind.call_args_list[0]
        self.assertEqual(args, (8000, ))

        self.http_server.start.assert_called_once_with(1)

    def test_that_production_enables_reuse_port(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)

        self.assertTrue(self.http_server.bind.called)
        args, kwargs = self.http_server.bind.call_args_list[0]
        self.assertEqual(args, (8000, ))
        self.assertEqual(kwargs['reuse_port'], True)

    def test_that_debug_run_starts_in_singleprocess_mode(self):
        self.application.settings['debug'] = True
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        self.http_server.listen.assert_called_once_with(8000)
        self.http_server.start.assert_not_called()

    def test_that_initializer_creates_runner_callbacks_dict(self):
        application = web.Application()
        sprockets.http.runner.Runner(application)
        self.assertEqual(application.runner_callbacks['before_run'], [])
        self.assertEqual(application.runner_callbacks['on_start'], [])
        self.assertEqual(application.runner_callbacks['shutdown'], [])

    def test_that_signal_handler_invokes_shutdown(self):
        with mock.patch('sprockets.http.runner.signal') as signal_module:
            runner = sprockets.http.runner.Runner(self.application)
            runner.run(8000)

            signal_module.signal.assert_any_call(signal_module.SIGINT,
                                                 runner._on_signal)
            signal_module.signal.assert_any_call(signal_module.SIGTERM,
                                                 runner._on_signal)
            runner._on_signal(signal_module.SIGINT, mock.Mock())
            self.io_loop.add_callback_from_signal.assert_called_once_with(
                runner._shutdown)

    def test_that_shutdown_stops_after_timelimit(self):
        def add_timeout(_, callback):
            time.sleep(0.1)
            callback()
        self.io_loop.add_timeout = mock.Mock(side_effect=add_timeout)

        self.io_loop._timeouts = [mock.Mock()]
        runner = sprockets.http.runner.Runner(self.application)
        runner.shutdown_limit = 0.25
        runner.wait_timeout = 0.05
        runner.run(8000)
        runner._shutdown()
        self.io_loop.stop.assert_called_once_with()
        self.assertNotEqual(self.io_loop._timeouts, [])

    def test_that_calling_with_non_sprockets_application_is_deprecated(self):
        with warnings.catch_warnings(record=True) as captured:
            warnings.filterwarnings(action='always', module='sprockets')
            sprockets.http.runner.Runner(web.Application())
        for warning in captured:
            if 'sprockets.app.Application' in str(warning.message):
                break
        else:
            self.fail('expected deprecation warning from runnr.Runner')

        with warnings.catch_warnings(record=True) as captured:
            warnings.filterwarnings(action='always', module='sprockets')
            sprockets.http.runner.Runner(sprockets.http.app.Application())
        self.assertEqual(len(captured), 0)


class AsyncRunTests(unittest.TestCase):

    def test_that_on_start_callbacks_are_invoked(self):
        future = concurrent.Future()

        def on_started(*args, **kwargs):
            with mock.patch('sprockets.http.runner.Runner.stop_server'):
                runner._shutdown()
                future.set_result(True)

        application = web.Application()
        with mock.patch('sprockets.http.runner.Runner.start_server'):
            runner = sprockets.http.runner.Runner(application,
                                                  on_start=[on_started])
            runner.run(8000)
        self.assertTrue(future.result())

    def test_that_shutdown_futures_are_waited_on(self):
        future = concurrent.Future()

        def on_started(*args, **kwargs):
            with mock.patch('sprockets.http.runner.Runner.stop_server'):
                runner._shutdown()

        def on_shutdown(*args, **kwargs):
            def shutdown_complete():
                future.set_result(True)

            ioloop.IOLoop.current().add_timeout(1, shutdown_complete)
            return future

        application = web.Application()
        with mock.patch('sprockets.http.runner.Runner.start_server'):
            runner = sprockets.http.runner.Runner(application,
                                                  on_start=[on_started],
                                                  shutdown=[on_shutdown])
            runner.run(8000)

        self.assertTrue(future.result())


class RunCommandTests(MockHelper, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.distribution = mock.Mock(spec=distutils.dist.Distribution,
                                      verbose=3)

    def test_that_environment_file_is_processed(self):
        os_module = self.start_mock('sprockets.http.runner.os')
        os_module.environ = {'SHOULD_BE': 'REMOVED'}
        os_module.path.exists.return_value = True

        open_mock = mock.mock_open(read_data='\n'.join([
            'export SIMPLE=1',
            'NOT_EXPORTED=2  # with comment too!',
            'export DQUOTED="value with space"',
            "export SQUOTED='value with space'",
            'BAD LINE',
            '# commented line',
            'SHOULD_BE=',
        ]))
        self.start_mock('builtins.open', open_mock)

        command = sprockets.http.runner.RunCommand(self.distribution)
        command.dry_run = True
        command._find_callable = mock.Mock()
        command.env_file = 'name.conf'
        command.application = 'required.to:exist'

        command.ensure_finalized()
        command.run()

        os_module.path.exists.assert_called_once_with('name.conf')
        self.assertEqual(
            sorted(list(os_module.environ.keys())),
            sorted(['SIMPLE', 'NOT_EXPORTED', 'DQUOTED', 'SQUOTED']))
        self.assertEqual(os_module.environ['SIMPLE'], '1')
        self.assertEqual(os_module.environ['NOT_EXPORTED'], '2')
        self.assertEqual(os_module.environ['DQUOTED'], 'value with space')
        self.assertEqual(os_module.environ['SQUOTED'], 'value with space')

    def test_that_port_option_sets_environment_variable(self):
        os_module = self.start_mock('sprockets.http.runner.os')
        os_module.environ = {}
        os_module.path.exists.return_value = True

        open_mock = mock.mock_open(read_data='PORT=2')
        self.start_mock('builtins.open', open_mock)

        command = sprockets.http.runner.RunCommand(self.distribution)
        command.dry_run = True
        command._find_callable = mock.Mock()
        command.env_file = 'name.conf'
        command.application = 'required.to:exist'
        command.port = '3'

        command.ensure_finalized()
        command.run()

        self.assertEqual(os_module.environ['PORT'], '3')

    def test_that_application_callable_is_created(self):
        # this is somewhat less hacky than patching __import__ ...
        # just add a "recorder" around the _find_callable method
        # in a not so hacky way
        command = sprockets.http.runner.RunCommand(self.distribution)

        result_closure = {'real_method': command._find_callable}

        def patched():
            result_closure['result'] = result_closure['real_method']()
            return result_closure['result']

        command.dry_run = True
        command.application = 'sprockets.http.runner:Runner'
        command._find_callable = patched

        command.ensure_finalized()
        command.run()
        self.assertEqual(result_closure['result'],
                         sprockets.http.runner.Runner)

    def test_that_finalize_options_requires_application_option(self):
        command = sprockets.http.runner.RunCommand(self.distribution)
        command.env_file = 'not used here'
        with self.assertRaises(distutils.errors.DistutilsArgError):
            command.ensure_finalized()

    def test_that_finalize_options_with_nonexistant_env_file_fails(self):
        os_module = self.start_mock('sprockets.http.runner.os')
        os_module.path.exists.return_value = False

        command = sprockets.http.runner.RunCommand(self.distribution)
        command.application = examples.Application
        command.env_file = 'file.conf'
        with self.assertRaises(distutils.errors.DistutilsArgError):
            command.ensure_finalized()
        os_module.path.exists.assert_called_once_with('file.conf')

    def test_that_sprockets_http_run_is_called_appropriately(self):
        # yes this god awful path is actually correct :/
        run_function = self.start_mock(
            'sprockets.http.runner.sprockets.http.run')

        command = sprockets.http.runner.RunCommand(self.distribution)

        result_closure = {'real_method': command._find_callable}

        def patched():
            result_closure['result'] = result_closure['real_method']()
            return result_closure['result']

        command.application = 'examples:Application'
        command.dry_run = False
        command._find_callable = patched

        command.ensure_finalized()
        command.run()

        run_function.assert_called_once_with(result_closure['result'])


class TestCaseTests(unittest.TestCase):

    class FakeTest(sprockets.http.testing.SprocketsHttpTestCase):
        def get_app(self):
            self.app = mock.Mock()
            return self.app

        def runTest(self):
            pass

    def test_that_setup_calls_start(self):
        test_case = self.FakeTest()
        test_case.setUp()
        test_case.app.start.assert_called_once_with(test_case.io_loop)

    def test_that_teardown_calls_stop(self):
        test_case = self.FakeTest()
        test_case.setUp()
        test_case.io_loop = mock.Mock()
        test_case.tearDown()
        test_case.app.stop.assert_called_once_with(
            test_case.io_loop, test_case.shutdown_limit,
            test_case.wait_timeout)


class CorrelationFilterTests(unittest.TestCase):
    def setUp(self):
        super(CorrelationFilterTests, self).setUp()
        self.logger = logging.getLogger()
        self.record = self.logger.makeRecord(
            'name', logging.INFO, 'functionName', 42, 'hello %s',
            tuple(['world']), (None, None, None))
        self.filter = sprockets.http._CorrelationFilter()

    def test_that_correlation_filter_adds_correlation_id(self):
        self.filter.filter(self.record)
        self.assertTrue(hasattr(self.record, 'correlation-id'))

    def test_that_correlation_filter_does_not_overwrite_correlation_id(self):
        some_value = str(uuid.uuid4())
        setattr(self.record, 'correlation-id', some_value)
        self.filter.filter(self.record)
        self.assertEqual(getattr(self.record, 'correlation-id'), some_value)


class LoggingConfigurationTests(unittest.TestCase):
    def test_that_debug_sets_log_level_to_debug(self):
        config = sprockets.http._get_logging_config(True)
        self.assertEqual(config['root']['level'], 'DEBUG')

    def test_that_not_debug_sets_log_level_to_info(self):
        config = sprockets.http._get_logging_config(False)
        self.assertEqual(config['root']['level'], 'INFO')

    def test_that_format_includes_sd_when_service_and_env_are_set(self):
        with override_environment_variable(SERVICE='service',
                                           ENVIRONMENT='whatever'):
            config = sprockets.http._get_logging_config(False)
        fmt_name = list(config['formatters'].keys())[0]
        self.assertIn('service="service" environment="whatever"',
                      config['formatters'][fmt_name]['format'])


class ShutdownHandlerTests(unittest.TestCase):
    def setUp(self):
        super(ShutdownHandlerTests, self).setUp()
        self.io_loop = ioloop.IOLoop.current()

    def test_that_on_future_complete_logs_exceptions_from_future(self):
        future = concurrent.Future()
        future.set_exception(Exception('Injected Failure'))
        handler = sprockets.http.app._ShutdownHandler(self.io_loop, 0.2, 0.05)
        with self.assertLogs(handler.logger, 'WARNING') as cm:
            handler.on_shutdown_future_complete(future)
        self.assertEqual(len(cm.output), 1)
        self.assertIn('Injected Failure', cm.output[0])

    def test_that_on_future_complete_logs_active_exceptions(self):
        future = concurrent.Future()
        future.set_exception(Exception('Injected Failure'))
        handler = sprockets.http.app._ShutdownHandler(self.io_loop, 0.2, 0.05)
        with self.assertLogs(handler.logger, 'WARNING') as cm:
            try:
                future.result()
            except Exception:
                handler.on_shutdown_future_complete(future)
        self.assertEqual(len(cm.output), 1)
        self.assertIn('Injected Failure', cm.output[0])

    def test_that_maybe_stop_retries_until_tasks_are_complete(self):
        fake_loop = unittest.mock.Mock()
        fake_loop.time.return_value = 10

        wait_timeout = 1.0
        handler = sprockets.http.app._ShutdownHandler(
            fake_loop, 5.0, wait_timeout)

        handler._all_tasks = unittest.mock.Mock()
        handler._all_tasks.return_value = ['does-not-matter']

        # on_shutdown_ready should schedule the callback since there
        # are outstanding tasks
        handler.on_shutdown_ready()
        fake_loop.add_timeout.assert_called_once_with(
            fake_loop.time.return_value + wait_timeout,
            handler._maybe_stop)
        fake_loop.add_timeout.reset_mock()

        # the callback should re-schedule since there are still
        # outstanding tasks
        handler._maybe_stop()
        fake_loop.add_timeout.assert_called_once_with(
            fake_loop.time.return_value + wait_timeout,
            handler._maybe_stop)
        fake_loop.add_timeout.reset_mock()

        # when all of the tasks are finished, the loop is stopped
        handler._all_tasks.return_value = []
        handler._maybe_stop()
        fake_loop.stop.assert_called_once_with()

    def test_that_maybe_stop_terminates_when_deadline_reached(self):
        fake_loop = unittest.mock.Mock()

        shutdown_limit = 10
        ticks = range(0, shutdown_limit)
        handler = sprockets.http.app._ShutdownHandler(
            fake_loop, shutdown_limit, 1.0)

        handler._all_tasks = unittest.mock.Mock()
        handler._all_tasks.return_value = ['does-not-matter']

        fake_loop.time.return_value = 0.0
        handler.on_shutdown_ready()  # sets deadline to 0 + shutdown_limit
        for time_value in ticks:  # tick down
            fake_loop.time.return_value = float(time_value)
            handler._maybe_stop()
            fake_loop.stop.assert_not_called()

        fake_loop.time.return_value = float(shutdown_limit)
        handler._maybe_stop()
        fake_loop.stop.assert_called_once_with()


class AccessLogTests(sprockets.http.testing.SprocketsHttpTestCase):

    def get_app(self):
        self.app = sprockets.http.app.Application([])
        return self.app

    def test_that_log_request_uses_expected_format(self):
        request = httputil.HTTPServerRequest('GET', '/search?q=42')
        request.remote_ip = '1.1.1.1'
        request._start_time = time.time()
        request.connection = unittest.mock.Mock()

        handler = web.RequestHandler(self.app, request)

        with self.assertLogs(log.access_log) as context:
            self.app.log_request(handler)

        when = datetime.datetime.fromtimestamp(request._start_time,
                                               datetime.timezone.utc)
        expected_message = re.compile(
            r'^%s - - %s "%s %s %s" %d "%s" - "-" "-" \(secs:([^)]*)\)' %
            (request.remote_ip,
             re.escape(
                 when.strftime('[%d/%b/%Y:%H:%M:%S %z]')), request.method,
             re.escape(request.uri), request.version, handler.get_status(),
             handler._reason))
        message = context.records[0].getMessage()
        match = expected_message.match(message)
        if match is None:
            self.fail(f'"{message}" did not match "{expected_message}"')
        try:
            float(match.group(1))
        except ValueError:
            self.fail(f'Expected {match.group(1)} to be a float')

    def test_that_log_request_uses_correct_log_level(self):
        expectations = {
            200: logging.INFO,
            303: logging.INFO,
            400: logging.WARNING,
            404: logging.WARNING,
            500: logging.ERROR,
            599: logging.ERROR,
        }

        request = httputil.HTTPServerRequest('GET', '/search?q=42')
        request.remote_ip = '1.1.1.1'
        request._start_time = time.time()
        request.connection = unittest.mock.Mock()

        for status, log_level in expectations.items():
            handler = web.RequestHandler(self.app, request)
            handler.set_status(status)
            with self.assertLogs(log.access_log, log_level) as context:
                self.app.log_request(handler)
            self.assertEqual(context.records[0].levelno, log_level)

    def test_that_log_request_uses_correct_log_level_with_only_failures(self):
        expectations = {
            200: logging.DEBUG,
            303: logging.DEBUG,
            400: logging.WARNING,
            404: logging.WARNING,
            500: logging.ERROR,
            599: logging.ERROR,
        }

        request = httputil.HTTPServerRequest('GET', '/search?q=42')
        request.remote_ip = '1.1.1.1'
        request._start_time = time.time()
        request.connection = unittest.mock.Mock()

        for status, log_level in expectations.items():
            handler = web.RequestHandler(self.app, request)
            handler.access_log_failures_only = True
            handler.set_status(status)
            with self.assertLogs(log.access_log, log_level) as context:
                self.app.log_request(handler)
            self.assertEqual(context.records[0].levelno, log_level)

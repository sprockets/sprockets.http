import contextlib
import distutils.dist
import distutils.errors
import logging
import os
import json
import time
import unittest

try:
    from unittest import mock
    open_name = 'builtins.open'
except ImportError:
    import mock
    open_name = '__builtin__.open'

from tornado import concurrent, httputil, ioloop, testing, web

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

    def start_mock(self, target, existing_mock=None):
        target_mock = mock.Mock() if existing_mock is None else existing_mock
        mocked = mock.patch(target, target_mock)
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
        self.runner_instance.run.assert_called_once_with(8000, mock.ANY)

    def test_that_port_envvar_sets_port_number(self):
        with override_environment_variable('PORT', '8888'):
            sprockets.http.run(mock.Mock())
            self.runner_instance.run.assert_called_once_with(8888, mock.ANY)

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


class CallbackTests(MockHelper, unittest.TestCase):

    def setUp(self):
        super(CallbackTests, self).setUp()
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
        super(RunnerTests, self).setUp()
        self.application = mock.Mock()
        self.application.settings = {}
        self.application.runner_callbacks = {}

        self.io_loop = mock.Mock()
        self.io_loop._callbacks = []
        self.io_loop._timeouts = []
        self.io_loop.time = time.time
        ioloop_module = self.start_mock('sprockets.http.runner.ioloop')
        ioloop_module.IOLoop.instance.return_value = self.io_loop

        self.http_server = mock.Mock()
        httpserver_module = self.start_mock('sprockets.http.runner.httpserver')
        httpserver_module.HTTPServer.return_value = self.http_server

    def test_that_run_starts_ioloop(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        self.io_loop.start.assert_called_once_with()

    def test_that_production_run_starts_in_multiprocess_mode(self):
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        self.http_server.bind.assert_called_once_with(8000)
        self.http_server.start.assert_called_once_with(0)

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

    def test_that_shutdown_waits_for_callbacks(self):
        def add_timeout(_, callback):
            self.io_loop._callbacks.pop()
            callback()
        self.io_loop.add_timeout = mock.Mock(side_effect=add_timeout)

        self.io_loop._callbacks = [mock.Mock(), mock.Mock()]
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        runner._shutdown()
        self.io_loop.stop.assert_called_once_with()
        self.assertEqual(self.io_loop.add_timeout.call_count, 2)

    def test_that_shutdown_waits_for_timeouts(self):
        def add_timeout(_, callback):
            self.io_loop._timeouts.pop()
            callback()
        self.io_loop.add_timeout = mock.Mock(side_effect=add_timeout)

        self.io_loop._timeouts = [mock.Mock(), mock.Mock()]
        runner = sprockets.http.runner.Runner(self.application)
        runner.run(8000)
        runner._shutdown()
        self.io_loop.stop.assert_called_once_with()
        self.assertEqual(self.io_loop.add_timeout.call_count, 2)

    def test_that_shutdown_stops_after_timelimit(self):
        def add_timeout(_, callback):
            time.sleep(0.1)
            callback()
        self.io_loop.add_timeout = mock.Mock(side_effect=add_timeout)

        self.io_loop._timeouts = [mock.Mock()]
        runner = sprockets.http.runner.Runner(self.application)
        runner.shutdown_limit = 0.25
        runner.run(8000)
        runner._shutdown()
        self.io_loop.stop.assert_called_once_with()
        self.assertNotEqual(self.io_loop._timeouts, [])


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
        super(RunCommandTests, self).setUp()
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
        self.start_mock(open_name, open_mock)

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
        self.start_mock(open_name, open_mock)

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

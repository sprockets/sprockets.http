import logging
import json
import mock

from tornado import httputil, testing, web

from sprockets.http import mixins
import examples


class RecordingHandler(logging.Handler):

    def __init__(self):
        super(RecordingHandler, self).__init__()
        self.emitted = []

    def emit(self, record):
        self.emitted.append((record, self.format(record)))


class RaisingHandler(mixins.ErrorLogger, mixins.ErrorWriter,
                     web.RequestHandler):

    def get(self, status_code):
        raise web.HTTPError(int(status_code),
                            reason=self.get_query_argument('reason', None))


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

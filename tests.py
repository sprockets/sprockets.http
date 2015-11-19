import logging

from tornado import httputil, testing, web

from sprockets.http import mixins
import examples


class RecordingHandler(logging.Handler):

    def __init__(self):
        super(RecordingHandler, self).__init__()
        self.emitted = []

    def emit(self, record):
        self.emitted.append((record, self.format(record)))


class RaisingHandler(mixins.ErrorLogger, web.RequestHandler):

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

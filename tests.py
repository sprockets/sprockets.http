import logging

from tornado import httputil, testing

import examples


class RecordingHandler(logging.Handler):

    def __init__(self):
        super(RecordingHandler, self).__init__()
        self.emitted = []

    def emit(self, record):
        self.emitted.append((record, self.format(record)))


class ErrorWriterTests(testing.AsyncHTTPTestCase):

    def setUp(self):
        super(ErrorWriterTests, self).setUp()
        self.access_log = logging.getLogger('tornado.access')
        self.app_log = logging.getLogger('tornado.application')
        self.gen_log = logging.getLogger('tornado.general')
        self.handler_log = logging.getLogger('StatusHandler')
        for logger in (self.access_log, self.app_log, self.gen_log,
                       self.handler_log):
            logger.disabled = False

        self.recorder = RecordingHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(self.recorder)

    def tearDown(self):
        super(ErrorWriterTests, self).tearDown()
        logging.getLogger().removeHandler(self.recorder)

    def get_app(self):
        return examples.make_app()

    def assert_message_logged(self, level, msg_fmt, *msg_args):
        suffix = msg_fmt.format(*msg_args)
        for record, message in self.recorder.emitted:
            if record.name == self.handler_log.name:
                self.assertEqual(record.levelno, level)
                self.assertTrue(
                    message.endswith(suffix),
                    'Expected "{}" to end with "{}"'.format(message, suffix))
                break
        else:
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

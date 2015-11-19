"""
HTTP related utility mixins.

- :class:`LoggingHandler`: adds ``self.logger``
- :class:`ErrorLogger`: extends ``send_error`` to log useful information

"""
import logging

from tornado import httputil


class LoggingHandler(object):
    """
    Add ``self.logger``.

    Mix this into your inheritance chain to add a ``logger``
    attribute unless one already exists.

    .. attribute:: logger

       Instance of :class:`logging.Logger` with the same name as
       the class.

    """

    def initialize(self):
        super(LoggingHandler, self).initialize()
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(self.__class__.__name__)


class ErrorLogger(LoggingHandler, object):
    """
    Log a message in ``send_error``.

    Mix this class into your inheritance chain to ensure that
    errors sent via :meth:`tornado.web.RequestHandler.send_error`
    and :meth:`tornado.web.RequestHandler.write_error` are written
    to the log.

    """

    def send_error(self, status_code=500, **kwargs):
        if kwargs.get('reason', None) is None:
            # so... ReqehstHandler._handle_request_exception explicitly
            # discards the exc.reason in the case of web.HTTPError...
            _, exc, _ = kwargs.get('exc_info', (None, None, None))
            if getattr(exc, 'reason', None):
                kwargs['reason'] = exc.reason
            else:
                # Oh, and make non-standard HTTP status codes NOT explode!
                kwargs['reason'] = httputil.responses.get(status_code,
                                                          'Unknown')
        super(ErrorLogger, self).send_error(status_code, **kwargs)

    def write_error(self, status_code, **kwargs):
        log_function = self.logger.debug
        if 400 <= status_code < 500:
            log_function = self.logger.warning
        else:
            log_function = self.logger.error

        # N.B. kwargs[reason] is set up by send_error
        log_function('%s %s failed with %s: %s', self.request.method,
                     self.request.uri, status_code, kwargs['reason'])
        super(ErrorLogger, self).write_error(status_code, **kwargs)

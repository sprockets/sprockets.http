"""
HTTP related utility mixins.

- :class:`LoggingHandler`: adds ``self.logger``
- :class:`ErrorLogger`: extends ``send_error`` to log useful information
- :class:`ErrorWriter`: implements ``send_error`` to write a useful response

"""
import logging
import json
import traceback

from tornado import httputil


def _get_http_reason(status_code):
    return httputil.responses.get(status_code, 'Unknown')


class LoggingHandler:
    """
    Add ``self.logger``.

    Mix this into your inheritance chain to add a ``logger``
    attribute unless one already exists.

    .. attribute:: logger

       Instance of :class:`logging.Logger` with the same name as
       the class.

    """

    def initialize(self):
        super().initialize()
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(self.__class__.__name__)


class ErrorLogger(LoggingHandler):
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
                kwargs['reason'] = _get_http_reason(status_code)
        super().send_error(status_code, **kwargs)

    def write_error(self, status_code, **kwargs):
        log_function = self.logger.debug
        if 400 <= status_code < 500:
            log_function = self.logger.warning
        else:
            log_function = self.logger.error

        # N.B. kwargs[reason] is set up by send_error
        log_function('%s %s failed with %s: %s', self.request.method,
                     self.request.uri, status_code,
                     kwargs.get('log_message', kwargs['reason']))
        super().write_error(status_code, **kwargs)


class ErrorWriter:
    """
    Write error bodies out consistently.

    Mix this class in to your inheritance chain to include error bodies in a
    machine-readable document format.

    If :class:`~sprockets.mixins.mediatype.ContentMixin` is also in use, it
    will send the error response with it, otherwise the response is sent as
    a JSON document.

    The error document has three simple properties:

    **type**
        This is the type of exception that occurred or ``null``.
        It is only set when :meth:`.write_error` is invoked with
        a non-empty ``exc_info`` parameter.  In that case, it is
        set to the name of the first value in the :class:`tuple`;
        IOW, ``exc_type.__name__``.

    **message**
        This is a description of the error.  If exception info is
        present, then the stringified exception value is used as
        the message (e.g., ``str(exc_value)``); otherwise, the HTTP
        ``reason`` will be used.  If a custom ``reason`` is not
        present, then the standard HTTP reason phrase is used.  In
        the final case of a non-standard HTTP status code with
        neither an exception nor a custom reason, the string ``Unknown``
        will be used.

    **traceback**
        If the application is configured to serve tracebacks and the
        error was caused by an exception (based on ``exc_info`` kwarg),
        then this is the formatted traceback as an array of strings
        returned from :func:`traceback.format_exception`.  Otherwise,
        this property is set to ``null``.

    """

    def write_error(self, status_code, **kwargs):
        error_body = {'type': None, 'traceback': None}
        exc_type, exc_value, _ = kwargs.get('exc_info', (None, None, None))
        if exc_type and exc_value:
            error_body['type'] = exc_type.__name__
            error_body.setdefault('message', str(exc_value))
            if self.settings.get('serve_traceback', False):
                error_body['traceback'] = traceback.format_exception(
                    *kwargs['exc_info'])
        else:
            reason = kwargs.get('reason', _get_http_reason(status_code))
            error_body.setdefault('message', reason)

        # If sprockets.mixins.media_type is being used, use it
        if hasattr(self, 'send_response'):
            self.send_response(error_body)
        else:
            self.set_header('Content-Type', 'application/json; charset=utf-8')
            self.write(json.dumps(error_body).encode('utf-8'))

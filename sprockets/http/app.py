import logging
import sys

from tornado import concurrent, httputil, web
try:
    from tornado import locks
except ImportError:  # pragma: no cover
    import toro as locks


class _ShutdownHandler(object):
    """Keeps track of the application state during shutdown."""

    def __init__(self, io_loop):
        self.io_loop = io_loop
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pending_callbacks = 0
        self.shutdown_limit = 5
        self.__deadline = None

    def add_future(self, future):
        self.pending_callbacks += 1
        self.io_loop.add_future(future, self.on_shutdown_future_complete)

    def on_shutdown_future_complete(self, future):
        self.pending_callbacks -= 1
        if future.exception():
            if any(sys.exc_info()):
                self.logger.exception('shutdown callback raised exception')
            else:
                self.logger.warning('shutdown callback raised exception: %r',
                                    exc_info=(None, future.exception(), None))
        else:
            self.logger.debug('shutdown future completed: %r, %d pending',
                              future.result(), self.pending_callbacks)

        if not self.pending_callbacks:
            self.on_shutdown_ready()

    def on_shutdown_ready(self):
        self.logger.info('starting IOLoop shutdown process')
        self.__deadline = self.io_loop.time() + self.shutdown_limit
        self._maybe_stop()

    def _maybe_stop(self):
        now = self.io_loop.time()
        if (now < self.__deadline and
                (self.io_loop._callbacks or self.io_loop._timeouts)):
            self.io_loop.add_timeout(now + 1, self._maybe_stop)
        else:
            self.io_loop.stop()
            self.logger.info('stopped IOLoop')


class _NotReadyDelegate(httputil.HTTPMessageDelegate):
    """
    Implementation of ``HTTPMessageDelegate`` that always fails.

    :param tornado.httputil.HTTPConnection request_conn: the request
        connection to send a response to.

    This implementation of :class:`tornado.httputil.HTTPMessageDelegate`
    always finishes a request by writing a :http:status:`503` response.
    A new instance is created by :method:`.Application.start_request`
    when the application is not ready yet.

    """

    def __init__(self, request_conn):
        super(_NotReadyDelegate, self).__init__()
        self.request_conn = request_conn

    def finish(self):
        def on_written(*args):
            self.request_conn.finish()

        response_line = httputil.ResponseStartLine('HTTP/1.0', 503,
                                                   'Application Not Ready')
        headers = httputil.HTTPHeaders({'Content-Length': '0'})
        future = self.request_conn.write_headers(response_line, headers,
                                                 callback=on_written)
        return future


class _Application(object):

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.before_run_callbacks = []
        self.on_start_callbacks = []
        self.on_shutdown_callbacks = []

        self.before_run_callbacks.extend(kwargs.pop('before_run', []))
        self.on_start_callbacks.extend(kwargs.pop('on_start', []))
        self.on_shutdown_callbacks.extend(kwargs.pop('on_shutdown', []))

        super(_Application, self).__init__(*args, **kwargs)
        self.ready_to_serve = locks.Event()

    @property
    def tornado_application(self):  # pragma: no cover
        """
        Return the :class:`tornado.web.Application` instance.

        :rtype: tornado.web.Application

        """
        raise NotImplementedError

    def start(self, io_loop):
        """
        Run the ``before_run`` callbacks and queue to ``on_start`` callbacks.

        :param tornado.ioloop.IOLoop io_loop: loop to start the app on.

        """
        for callback in self.before_run_callbacks:
            try:
                callback(self.tornado_application, io_loop)
            except Exception:
                self.logger.error('before_run callback %r cancelled start',
                                  callback, exc_info=1)
                self.stop(io_loop)
                raise

        for callback in self.on_start_callbacks:
            io_loop.spawn_callback(callback, self.tornado_application, io_loop)
        if not self.on_start_callbacks:
            self.ready_to_serve.set()

    def stop(self, io_loop):
        """
        Asynchronously stop the application.

        :param tornado.ioloop.IOLoop io_loop: loop to run until all
            callbacks, timeouts, and queued calls are complete

        Call this method to start the application shutdown process.
        The IOLoop will be stopped once the application is completely
        shut down.

        """
        self.ready_to_serve.clear()
        running_async = False
        shutdown = _ShutdownHandler(io_loop)
        for callback in self.on_shutdown_callbacks:
            try:
                maybe_future = callback(self.tornado_application)
                if concurrent.is_future(maybe_future):
                    shutdown.add_future(maybe_future)
                    running_async = True
            except Exception as error:
                self.logger.warning('exception raised from shutdown '
                                    'callback %r ignored: %s',
                                    callback, error, exc_info=1)

        if not running_async:
            shutdown.on_shutdown_ready()


class Application(_Application, web.Application):
    """
    Callback-aware version of :class:`tornado.web.Application`.

    Using this class instead of the vanilla Tornado ``Application``
    class provides a clean way to customize application-level
    constructs such as connection pools.  You can customize your
    application by sub-classing this class or simply passing
    parameters.

    :keyword list before_run: optional kwarg that specifies a list of
        callbacks to add to :attr:`.before_run_callbacks`
    :keyword list on_start: optional kwarg that specifies a list of
        callbacks to add to :attr:`.on_start_callbacks`
    :keyword list on_shutdown: optional kwarg that specifies a list of
        callbacks to add to :attr:`.on_shutdown_callbacks`

    Additional positional and keyword parameters are passed to the
    :class:`tornado.web.Application` initializer as-is.

    .. attribute:: ready_to_serve

       A flag that signals whether the application is ready to service
       requests or not.  This is a :class:`tornado.locks.Event` instance
       that needs to be set before the application will process a request.

    .. attribute:: before_run_callbacks

       The callbacks in this :class:`list` are called after tornado
       forks sub-processes and after the IOLoop is created but before
       it is started.  This means that callbacks can freely interact
       with the ioloop.  The callbacks are run "in-line" and the
       application will exit if a callback raises an exception.

       **Signature**: ``callback(application, io_loop)``

    .. attribute:: on_start_callbacks

       The callbacks in this :class:`list` are spawned after the
       callbacks in :attr:`before_run_callbacks` have completed and
       before the IOLoop is started.  The callbacks are run asynchronously
       by calling :meth:`tornado.ioloop.IOLoop.spawn_callback` which
       schedules them to run as soon as the IOLoop is started.

       **Signature**: ``callback(application, io_loop)``

    .. attribute:: on_shutdown_callbacks

       The callbacks in this :class:`list` are spawned after the
       application receives a stop signal.  It first stops the HTTP
       server.  Then it calls each callbacks in this list with the
       running IOLoop as a parameter.  If the callback returns a
       :class:`tornado.concurrent.Future` instance, then the future is
       added to the IOLoop.

       The IOLoop is stopped after all callbacks and timers are finished.

       **Signature**: ``callback(application)``

    """

    @property
    def tornado_application(self):
        return self

    def start_request(self, *args):
        """
        Extends ``start_request`` to handle "not ready" conditions.

        :param server_conn: opaque representation of the low-level
            TCP connection
        :param tornado.httputil.HTTPConnection request_conn:
            the connection associated with the new request
        :rtype: tornado.httputil.HTTPMessageDelegate

        If the :attr:`ready_to_serve` is not set, then an instance of
        :class:`._NotReadyDelegate` is returned.  It will ensure that
        the application responds with a 503.

        """
        if not self.ready_to_serve.is_set():
            return _NotReadyDelegate(args[-1])
        return super(Application, self).start_request(*args)


class _ApplicationAdapter(_Application):
    """
    Simple adapter for a :class:`tornado.web.Application` instance.

    This class adapts/wraps a :class:`~tornado.web.Application` instance
    and adds callback management in a backwards compatible manner.

    .. warning::

       Do not use this class directly.  Either switch to using
       :class:`.Application` explicitly or call :func:`.wrap_application`
       to wrap your current ``Application`` instance.

    """

    def __init__(self, application):
        runner_callbacks = getattr(application, 'runner_callbacks', {})
        super(_ApplicationAdapter, self).__init__(
            before_run=runner_callbacks.get('before_run', []),
            on_start=runner_callbacks.get('on_start', []),
            on_shutdown=runner_callbacks.get('shutdown', []))

        self._application = application
        self.settings = self.tornado_application.settings
        setattr(application, 'runner_callbacks',
                {'before_run': self.before_run_callbacks,
                 'on_start': self.on_start_callbacks,
                 'shutdown': self.on_shutdown_callbacks})

    @property
    def tornado_application(self):
        return self._application


def wrap_application(application, before_run, on_start, shutdown):
    """
    Wrap a tornado application in a callback-aware wrapper.

    :param tornado.web.Application application: application to wrap.
    :param list|NoneType before_run: optional list of callbacks
        to invoke before the IOLoop is started.
    :param list|NoneType on_start: optional list of callbacks to
        register with :meth:`~tornado.IOLoop.spawn_callback`.
    :param list|NoneType shutdown: optional list of callbacks to
        invoke before stopping the IOLoop

    :return: a wrapped application object
    :rtype: sprockets.http.app.Application

    """

    before_run = [] if before_run is None else before_run
    on_start = [] if on_start is None else on_start
    shutdown = [] if shutdown is None else shutdown

    if not isinstance(application, Application):
        application = _ApplicationAdapter(application)

    application.before_run_callbacks.extend(before_run)
    application.on_start_callbacks.extend(on_start)
    application.on_shutdown_callbacks.extend(shutdown)

    return application

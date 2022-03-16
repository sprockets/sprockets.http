import asyncio
import datetime
import logging
import sys
import warnings

from tornado import concurrent, log, web


class _ShutdownHandler:
    """Keeps track of the application state during shutdown."""

    def __init__(self, io_loop, shutdown_limit, wait_timeout):
        self.io_loop = io_loop
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pending_callbacks = 0
        self.shutdown_limit = shutdown_limit
        self.wait_timeout = wait_timeout
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
        all_tasks = self._all_tasks()
        now = self.io_loop.time()
        if now < self.__deadline and all_tasks:
            self.io_loop.add_timeout(now + self.wait_timeout, self._maybe_stop)
        else:
            self.io_loop.stop()
            self.logger.info('stopped IOLoop')

    def _all_tasks(self):
        if hasattr(asyncio, 'all_tasks'):
            return asyncio.all_tasks(self.io_loop.asyncio_loop)
        return asyncio.Task.all_tasks(self.io_loop.asyncio_loop)


class CallbackManager:
    """
    Application state management.

    This is where the core of the application wrapper actually lives.
    It is responsible for managing and calling the various application
    callbacks.  Sub-classes are responsible for gluing in the actual
    :class:`tornado.web.Application` object and the
    :mod:`sprockets.http.runner` module is responsible for starting up
    the HTTP stack and calling the :meth:`.start` and :meth:`.stop`
    methods.

    .. attribute:: runner_callbacks

       :class:`dict` of lists of callback functions to call at
       certain points in the application lifecycle.  See
       :attr:`.before_run_callbacks`, :attr:`.on_start_callbacks`,
       and :attr:`on_shutdown_callbacks`.

       .. deprecated:: 1.4

          Use the property callbacks instead of this dictionary.  It
          will be going away in a future release.

    """

    def __init__(self, tornado_application, *args, **kwargs):
        self.runner_callbacks = kwargs.pop('runner_callbacks', {})
        super().__init__(*args, **kwargs)

        self._tornado_application = tornado_application
        self.logger = logging.getLogger(self.__class__.__name__)
        self.runner_callbacks.setdefault('before_run', [])
        self.runner_callbacks.setdefault('on_start', [])
        self.runner_callbacks.setdefault('shutdown', [])

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

    def stop(self, io_loop, shutdown_limit=5.0, wait_timeout=1.0):
        """
        Asynchronously stop the application.

        :param tornado.ioloop.IOLoop io_loop: loop to run until all
            callbacks, timeouts, and queued calls are complete
        :param float shutdown_limit: maximum number of seconds to wait
            before terminating
        :param float wait_timeout: number of seconds to wait between checks
            for pending callbacks & timers

        Call this method to start the application shutdown process.
        The IOLoop will be stopped once the application is completely
        shut down or after `shutdown_limit` seconds.

        """
        running_async = False
        shutdown = _ShutdownHandler(io_loop, shutdown_limit, wait_timeout)
        for callback in self.on_shutdown_callbacks:
            try:
                maybe_future = callback(self.tornado_application)

                if asyncio.iscoroutine(maybe_future):
                    maybe_future = io_loop.asyncio_loop.create_task(
                        maybe_future)

                if concurrent.is_future(maybe_future):
                    shutdown.add_future(maybe_future)
                    running_async = True
            except Exception as error:
                self.logger.warning('exception raised from shutdown '
                                    'callback %r, ignored: %s',
                                    callback, error, exc_info=1)

        if not running_async:
            shutdown.on_shutdown_ready()

    @property
    def before_run_callbacks(self):
        """
        List of synchronous functions called before the IOLoop is started.

        The *before_run* callbacks are called after the IOLoop is created
        and before it is started.  The callbacks are run synchronously and
        the application will exit if a callback raises an exception.

        **Signature**: callback(application, io_loop)

        """
        return self.runner_callbacks['before_run']

    @property
    def on_start_callbacks(self):
        """
        List of asynchronous functions spawned before the IOLoop is started.

        The *on_start* callbacks are spawned after the IOLoop is created
        and before it is started.  The callbacks are run asynchronously
        via :meth:`tornado.ioloop.IOLoop.spawn_callback` as soon as the
        IOLoop is started.

        **Signature**: callback(application, io_loop)

        """
        return self.runner_callbacks['on_start']

    @property
    def on_shutdown_callbacks(self):
        """
        List of functions when the application is shutting down.

        The *on_shutdown* callbacks are called after the HTTP server has
        been stopped.  If a callback returns a
        :class:`tornado.concurrent.Future` instance, then the future is
        added to the IOLoop.

        **Signature**: callback(application)

        """
        return self.runner_callbacks['shutdown']

    @property
    def tornado_application(self):
        """The underlying :class:`tornado.web.Application` instance."""
        return self._tornado_application


class Application(CallbackManager, web.Application):
    """
    Callback-aware version of :class:`tornado.web.Application`.

    Using this class instead of the vanilla Tornado ``Application``
    class provides a clean way to customize application-level
    constructs such as connection pools.

    Note that much of the functionality is implemented in
    :class:`.CallbackManager`.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

    def log_request(self, handler):
        """Customized access log function.

        :param tornado.web.RequestHandler handler:

        """
        status = handler.get_status()

        if status < 400:
            if getattr(handler, 'access_log_failures_only', False):
                log_level = logging.DEBUG
            else:
                log_level = logging.INFO
        elif status < 500:
            log_level = logging.WARNING
        else:
            log_level = logging.ERROR

        started_at = datetime.datetime.fromtimestamp(
            handler.request._start_time, datetime.timezone.utc)
        try:
            bytes_written = handler.response_bytes_written
        except AttributeError:
            bytes_written = '-'

        log.access_log.log(
            log_level,
            '%s %s %s [%s] "%s %s %s" %d "%s" %s "%s" "%s" (secs:%.03f)',
            handler.request.remote_ip,
            '-',  # RFC-1413 user identifier
            handler.get_current_user() or '-',
            started_at.strftime('%d/%b/%Y:%H:%M:%S %z'),
            handler.request.method,
            handler.request.uri,
            handler.request.version,
            status,
            handler._reason or '-',
            bytes_written,
            handler.request.headers.get('Referer', '-'),
            handler.request.headers.get('User-Agent', '-'),
            handler.request.request_time(),
        )


class _ApplicationAdapter(CallbackManager):
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
        self._application = application
        self.settings = self._application.settings
        super().__init__(
            self._application,
            runner_callbacks=getattr(application, 'runner_callbacks', {}))
        setattr(self._application, 'runner_callbacks', self.runner_callbacks)


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
        warnings.warn(
            'sprockets.http.run is only going to accept '
            'sprockets.app.Application instances in 3.0, '
            'was called with {}'.format(type(application).__name__),
            category=DeprecationWarning)
        application = _ApplicationAdapter(application)

    application.before_run_callbacks.extend(before_run)
    application.on_start_callbacks.extend(on_start)
    application.on_shutdown_callbacks.extend(shutdown)

    return application

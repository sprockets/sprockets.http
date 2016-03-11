"""
Run a Tornado HTTP service.

- :func:`.run`: calls a ``make_app`` *callable*, configures the
  environment intelligently, and runs the application.
- :class:`.Runner`: encapsulates the running of the application

"""
import logging
import signal
import sys

from tornado import concurrent, httpserver, ioloop

import sprockets.logging


class Runner(object):
    """
    HTTP service runner.

    :param tornado.web.Application application: the application to serve

    This class implements the logic necessary to safely run a
    Tornado HTTP service inside of a docker container.

    .. rubric:: Usage Example

    .. code-block:: python

       def make_app():
           return web.Application(...)

       def run():
           server = runner.Runner(make_app())
           server.start_server()
           ioloop.IOLoop.instance().start()

    The :meth:`.start_server` method sets up the necessary signal handling
    to ensure that we have a clean shutdown in the face of signals.

    """

    def __init__(self, application, before_run=None, on_start=None,
                 shutdown=None):
        """Create a new instance of the runner.

        :param application: The application instance to run
        :type application: tornado.web.Application
        :param list before_run: Callbacks to invoke before starting
        :param list on_start: Callbacks to invoke after starting the IOLoop
        :param list shutdown: Callbacks to invoke on shutdown

        """
        self.application = application
        self.logger = logging.getLogger('Runner')
        self.server = None
        self.shutdown_limit = 5
        self._pending_callbacks = 0
        try:
            self.application.runner_callbacks.setdefault('before_run',
                                                         before_run or [])
            self.application.runner_callbacks.setdefault('on_start',
                                                         on_start or [])
            self.application.runner_callbacks.setdefault('shutdown',
                                                         shutdown or [])
        except AttributeError:
            setattr(self.application, 'runner_callbacks', {
                'before_run': before_run or [],
                'on_start': on_start or [],
                'shutdown': shutdown or []
            })

    def start_server(self, port_number, number_of_procs=0):
        """
        Create a HTTP server and start it.

        :param int port_number: the port number to bind the server to
        :param int number_of_procs: number of processes to pass to
            Tornado's ``httpserver.HTTPServer.start``.

        If the application's ``debug`` setting is ``True``, then we are
        going to run in a single-process mode; otherwise, we'll let
        tornado decide how many sub-processes to spawn.

        """
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        xheaders = self.application.settings.get('xheaders', False)

        self.server = httpserver.HTTPServer(self.application, xheaders=xheaders)
        if self.application.settings.get('debug', False):
            self.logger.info('starting 1 process on port %d', port_number)
            self.server.listen(port_number)
        else:
            self.application.settings.setdefault(
                'log_function', sprockets.logging.tornado_log_function)
            self.logger.info('starting processes on port %d', port_number)
            self.server.bind(port_number)
            self.server.start(number_of_procs)

    def stop_server(self):
        """Stop the HTTP Server"""
        self.server.stop()

    def run(self, port_number, number_of_procs=0):
        """
        Create the server and run the IOLoop.

        :param int port_number: the port number to bind the server to
        :param int number_of_procs: number of processes to pass to
            Tornado's ``httpserver.HTTPServer.start``.

        If the application's ``debug`` setting is ``True``, then we are
        going to run in a single-process mode; otherwise, we'll let
        tornado decide how many sub-processes to spawn.  In any case, the
        applications *before_run* callbacks are invoked.  If a callback
        raises an exception, then the application is terminated by calling
        :func:`sys.exit`.

        If any ``on_start`` callbacks are registered, they will be added to
        the Tornado IOLoop for execution after the IOLoop is started.

        """
        self.start_server(port_number, number_of_procs)
        iol = ioloop.IOLoop.instance()

        for callback in self.application.runner_callbacks['before_run']:
            try:
                callback(self.application, iol)
            except Exception:
                self.logger.error('before_run callback %r cancelled start',
                                  callback, exc_info=1)
                self._shutdown()
                sys.exit(70)

        # Add any on start callbacks
        for callback in self.application.runner_callbacks['on_start']:
            iol.spawn_callback(callback, self.application, iol)

        # Start the IOLoop and block
        iol.start()

    def _on_signal(self, signo, frame):
        self.logger.info('signal %s received, stopping', signo)
        ioloop.IOLoop.instance().add_callback_from_signal(self._shutdown)

    def _on_shutdown_future_complete(self, response):
        self._pending_callbacks -= 1
        if response.exception():
                self.logger.warning('shutdown callback raised an exception',
                                    response.exception, exc_info=1)
        else:
            self.logger.debug('Future callback result: %r', response.result())
        if not self._pending_callbacks:
            self._on_shutdown_ready()

    def _on_shutdown_ready(self):
        self.logger.debug('Stopping IOLoop')
        iol = ioloop.IOLoop.instance()
        deadline = iol.time() + self.shutdown_limit

        def maybe_stop():
            now = iol.time()
            if now < deadline and (iol._callbacks or iol._timeouts):
                return iol.add_timeout(now + 1, maybe_stop)
            iol.stop()
            self.logger.info('stopped')

        self.logger.info('stopping within %s seconds', self.shutdown_limit)
        maybe_stop()

    def _shutdown(self):
        self.logger.debug('Shutting down')

        # Ensure the HTTP server is stopped
        self.stop_server()

        iol = ioloop.IOLoop.instance()

        # Iterate through the callbacks, dealing with futures when returned
        for callback in self.application.runner_callbacks['shutdown']:
            try:
                response = callback(self.application)
                if concurrent.is_future(response):
                    self._pending_callbacks += 1
                    iol.add_future(response, self._on_shutdown_future_complete)
            except Exception:
                self.logger.warning('shutdown callback %r raised an exception',
                                    callback, exc_info=1)

        # If no futures were return, invoke on shutdown ready
        if not self._pending_callbacks:
            self._on_shutdown_ready()

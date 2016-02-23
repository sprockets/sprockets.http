"""
Run a Tornado HTTP service.

- :func:`.run`: calls a ``make_app`` *callable*, configures the
  environment intelligently, and runs the application.
- :class:`.Runner`: encapsulates the running of the application

"""
import logging
import signal
import sys

from tornado import httpserver, ioloop

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

    def __init__(self, application):
        self.application = application
        self.logger = logging.getLogger('Runner')
        self.server = None
        self.shutdown_limit = 5
        try:
            self.application.runner_callbacks.setdefault('shutdown', [])
            self.application.runner_callbacks.setdefault('before_run', [])
        except AttributeError:
            setattr(self.application, 'runner_callbacks', {
                'shutdown': [],
                'before_run': [],
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

        iol.start()

    def _on_signal(self, signo, frame):
        self.logger.info('signal %s received, stopping', signo)
        ioloop.IOLoop.instance().add_callback_from_signal(self._shutdown)

    def _shutdown(self):
        for callback in self.application.runner_callbacks['shutdown']:
            try:
                callback(self.application)
            except Exception:
                self.logger.warning('shutdown callback %r raised an exception',
                                    callback, exc_info=1)

        self.server.stop()
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

"""
Run a Tornado HTTP service.

- :class:`.Runner`: encapsulates the running of the application
- :class:`.RunCommand`: distutils command to runs an application

"""
from distutils import cmd, errors, log
import logging
import os.path
import signal
import sys

from tornado import httpserver, ioloop

import sprockets.http.app


class Runner:
    """
    HTTP service runner.

    :param tornado.web.Application app: the application to serve

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

    def __init__(self, app, before_run=None, on_start=None, shutdown=None):
        """Create a new instance of the runner.

        :param tornado.web.Application app: The application instance to run
        :param list before_run: Callbacks to invoke before starting
        :param list on_start: Callbacks to invoke after starting the IOLoop
        :param list shutdown: Callbacks to invoke on shutdown

        """
        self.application = sprockets.http.app.wrap_application(
            app, before_run, on_start, shutdown)
        self.logger = logging.getLogger('Runner')
        self.server = None
        self.shutdown_limit = 5.0
        self.wait_timeout = 1.0

    def start_server(self, port_number, number_of_procs=0):
        """
        Create a HTTP server and start it.

        :param int port_number: the port number to bind the server to
        :param int number_of_procs: number of processes to pass to
            Tornado's ``httpserver.HTTPServer.start``.

        If the application's ``debug`` setting is ``True``, then we are
        going to run in a single-process mode; otherwise, we'll let
        tornado decide how many sub-processes to spawn.

        The following additional configuration parameters can be set on the
        ``httpserver.HTTPServer`` instance by setting them in the application
        settings: ``xheaders``, ``max_body_size``, ``max_buffer_size``.

        """
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        xheaders = self.application.settings.get('xheaders', True)
        max_body_size = self.application.settings.get('max_body_size', None)
        max_buffer_size = self.application.settings.get('max_buffer_size',
                                                        None)

        self.server = httpserver.HTTPServer(
            self.application.tornado_application,
            xheaders=xheaders,
            max_body_size=max_body_size,
            max_buffer_size=max_buffer_size)
        if self.application.settings.get('debug', False):
            self.logger.info('starting 1 process on port %d', port_number)
            self.server.listen(port_number)
        else:
            self.logger.info('starting processes on port %d', port_number)
            self.server.bind(port_number, reuse_port=True)
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
        tornado decide how many sub-processes based on the value of the
        ``number_of_procs`` argument.  In any case, the application's
        *before_run* callbacks are invoked.  If a callback raises an exception,
        then the application is terminated by calling :func:`sys.exit`.

        If any ``on_start`` callbacks are registered, they will be added to
        the Tornado IOLoop for execution after the IOLoop is started.

        The following additional configuration parameters can be set on the
        ``httpserver.HTTPServer`` instance by setting them in the application
        settings: ``xheaders``, ``max_body_size``, ``max_buffer_size``.

        """
        self.start_server(port_number, number_of_procs)
        iol = ioloop.IOLoop.instance()

        try:
            self.application.start(iol)
        except Exception:
            self.logger.exception('application terminated during start, '
                                  'exiting')
            sys.exit(70)

        iol.start()

    def _on_signal(self, signo, frame):
        ioloop.IOLoop.instance().add_callback_from_signal(self._shutdown)

    def _shutdown(self):
        self.logger.debug('Shutting down')

        # Ensure the HTTP server is stopped
        self.stop_server()

        # Start the application shutdown process
        self.application.stop(ioloop.IOLoop.instance(), self.shutdown_limit,
                              self.wait_timeout)


class RunCommand(cmd.Command):
    """
    Simple distutils.Command that calls :func:`sprockets.http.run`

    This is installed as the httprun distutils command when you
    install the ``sprockets.http`` module.

    """

    description = 'Run a sprockets.http application.'
    user_options = [
        ('application=', 'a',
         'application callable in `pkg.mod:func` syntax'),
        ('env-file=', 'e', 'environment file to import'),
        ('port=', 'p', 'port for the application to listen on'),
    ]

    def initialize_options(self):
        self.application = None
        self.env_file = None
        self.port = None

    def finalize_options(self):
        if not self.application:
            raise errors.DistutilsArgError('application is required')
        if self.env_file and not os.path.exists(self.env_file):
            raise errors.DistutilsArgError(
                'environment file "{}" does not exist'.format(
                    self.env_file))

    def run(self):
        self._read_environment()
        if self.port:
            log.info('overriding port to %s', self.port)
            os.environ['PORT'] = self.port
        app_factory = self._find_callable()
        if self.dry_run:
            log.info('would run %r', app_factory)
        else:
            log.info('running %r', app_factory)
            sprockets.http.run(app_factory)

    def _read_environment(self):
        if not self.env_file:
            return

        with open(self.env_file) as env_file:
            for line in env_file.readlines():
                orig_line = line.strip()
                if '#' in line:
                    line = line[:line.index('#')]
                if line.startswith('export '):
                    line = line[7:]

                name, sep, value = line.strip().partition('=')
                if sep == '=':
                    if (value.startswith(('"', "'")) and
                            value.endswith(value[0])):
                        value = value[1:-1]
                    if value:
                        log.info('setting environment %s=%s', name, value)
                        os.environ[name] = value
                    else:
                        log.info('removing %s from environment', name)
                        os.environ.pop(name, None)
                elif line:
                    log.info('malformed environment line %r ignored',
                             orig_line)

    def _find_callable(self):
        app_module, callable_name = self.application.split(':')
        mod = __import__(app_module)
        for next_mod in app_module.split('.')[1:]:
            mod = getattr(mod, next_mod)
        return getattr(mod, callable_name)

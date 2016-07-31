API Documentation
=================

Running your Application
------------------------
This library exposes a utility function named :func:`sprockets.http.run`
for running your application.  You need to pass in a callable that accepts
keyword parameters destined for :class:`tornado.web.Application` and return
the application instance.

.. autofunction:: sprockets.http.run

.. code-block:: python
   :caption: Using sprockets.http.run

   def create_application(**settings):
      return web.Application(
         [
            # add your handlers here
         ], **settings)

   if __name__ == '__main__':
      sprockets.http.run(create_application)

In version 0.4, support for a ``runner_callbacks`` attribute was added to the
application instance.  It is a dictionary containing lists of callbacks to
invoke at certain points in the application lifecycle.  If the application
instance returned from your *make application* function defines the
attribute, then :func:`sprockets.http.run` will make sure that they are
invoked at the appropriate time.

The following example uses the callbacks to asynchronously connect to an
imaginary database and maintain a :class:`tornado.locks.Event` that can be
used to tell if the application can service requests or not.

.. code-block:: python
   :caption: Adding callbacks

   from tornado import gen, locks, web

   def _connect_to_database(app, iol):
      def _connected(future):
         if future.exception():
            coro = gen.sleep(0.5)
            iol.add_future(coro, lambda f: _connect_to_database(app, iol))
         else:
            app.ready_to_serve.set()

      future = dbconnector.connect()
      iol.add_future(future, _connected)

   def create_application(**settings):
      app = web.Application(handlers, **settings)
      callbacks = {
         'before_run': lambda app, iol: app.ready_to_serve.clear(),
         'on_start': _connect_to_database,
      }
      setattr(app, 'ready_to_serve', locks.Event())
      setattr(app, 'runner_callbacks', callbacks)
      return app

   if __name__ == '__main__':
      sprockets.http.run(create_application)

Start with version 1.3, this method was codified further with the creation
of the :class:`sprockets.http.app.Application` class.  Instead of manually
poking attributes into the application object in your *make application*
function, create a :class:`sprockets.http.app.Application` instance and set
the callback attributes that *or* sub-class
:class:`~sprockets.http.app.Application` and add customizations in the
initializer as shown below.  The sub-class approach is the recommended if you
have anything of interest in your application class.

The following snippet re-implements the previous example.

.. code-block:: python

   class Application(sprockets.http.app.Application):
      def __init__(self, **kwargs):
         super(Application, self).__init__(
            [
               # additional handlers here
            ],
            **kwargs)
         self.ready_to_serve = locks.Event()
         self.on_start_callbacks.append(self._connect_to_database)
         self.io_loop = None

      def _create_database(self, app, io_loop):
         self.io_loop = io_loop
         self._connect()

      def _connect(self, *ignored):
         coro = dbconnector.connect()
         self.io_loop.add_future(coro, self._on_connected)

      def _on_connected(self, future):
         if future.exception():
            coro = gen.sleep(0.5)
            self.io_loop.add_future(coro, self._connect)
         else:
            self.ready_to_serve.set()

   if __name__ == '__main__':
      sprockets.http.run(Application)

Before Run Callbacks
^^^^^^^^^^^^^^^^^^^^
This set of callbacks is invoked after Tornado forks sub-processes
(based on the ``number_of_procs`` setting) and before
:meth:`~tornado.ioloop.IOLoop.start` is called.  Callbacks can
safely access the :class:`~tornado.ioloop.IOLoop` without causing
the :meth:`~tornado.ioloop.IOLoop.start` method to explode.

If any callback raises an exception, then the application is
terminated **before** the IOLoop is started.

.. seealso:: :attr:`~sprockets.http.app.CallbackManager.before_run_callbacks`

On Start Callbacks
^^^^^^^^^^^^^^^^^^
This set of callbacks is invoked after Tornado forks sub-processes
(using :meth:`tornado.ioloop.IOLoop.spawn_callback`) and **after**
:meth:`~tornado.ioloop.IOLoop.start` is called.

.. seealso:: :attr:`~sprockets.http.app.CallbackManager.on_start_callbacks`

Shutdown Callbacks
^^^^^^^^^^^^^^^^^^
When the application receives a stop signal, it will run each of the
callbacks before terminating the application instance.  Exceptions
raised by the callbacks are simply logged.

.. seealso:: :attr:`~sprockets.http.app.CallbackManager.on_shutdown_callbacks`

Response Logging
----------------
Version 0.5.0 introduced the :mod:`sprockets.http.mixins` module with
two simple classes - :class:`~sprockets.http.mixins.LoggingHandler`
and :class:`~sprockets.http.mixins.ErrorLogger`.  Together they ensure
that errors emitted from your handlers will be logged in a consistent
manner.  All too often request handlers simply call ``write_error``
to report a failure to the caller with code that looks something like:

.. code-block:: python

   class MyHandler(web.RequestHandler):

      def get(self):
         try:
            do_something()
         except Failure:
            self.send_error(500, reason='Uh oh')
            return

This makes debugging an application fun since your caller generally
has more information about the failure than you do :/

By adding :class:`~sprockets.http.mixins.ErrorLogger` into the inheritance
chain, your error will be emitted to the application log as if you had
written the following instead:

.. code-block:: python

   class MyHandler(web.RequestHandler):
      def initialize(self):
         super(MyHandler, self).initialize()
         self.logger = logging.getLogger('MyHandler')

      def get(self):
         try:
            do_something()
         except Failure:
            self.logger.error('%s %s failed with %d: %s',
                              self.request.method, self.request.uri,
                              500, 'Uh oh')
            self.send_error(500, reason='Uh oh')
            return

It doesn't look like much, but the error reporting is a little more
interesting than that -- 4XX errors are reported as a warning,
exceptions will include the stack traces, etc.

.. autoclass:: sprockets.http.mixins.LoggingHandler
   :members:

.. autoclass:: sprockets.http.mixins.ErrorLogger
   :members:

Standardized Error Response Documents
-------------------------------------
Version 0.5.0 also introduced the :class:`~sprockets.http.mixins.ErrorWriter`
class which implements ``write_error`` to provide a standard machine-readable
document response instead of the default HTML response that Tornado implements.
If :class:`~sprockets.mixins.mediatype.ContentMixin` is being used as well,
``write_error`` will use
:meth:`~sprockets.mixins.mediatype.ContentMixin.send_response` to send the
document, otherwise it is sent as JSON.

.. autoclass:: sprockets.http.mixins.ErrorWriter
   :members:

Internal Interfaces
-------------------
.. automodule:: sprockets.http.runner
   :members:

.. automodule:: sprockets.http.app
   :members:

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

Since :func:`sprockets.http.run` accepts any callable, you can pass a
class instance in as well.  The :class:`sprockets.http.app.Application`
is a specialization of :class:`tornado.web.Application` that includes
state management callbacks that work together with the ``run`` function
and provide hooks for performing initialization and shutdown tasks.

The following example uses :class:`sprockets.http.app.Application` as a
base class to implement asynchronously connecting to a mythical database
when the application starts.

.. code-block:: python
   :caption: Using the Application class

   from tornado import locks, web
   from sprockets.http import app, run

   class Application(app.Application):
      def __init__(self, *args, **kwargs):
         handlers = [
            # insert your handlers here
         ]
         super().__init__(handlers, *args, **kwargs)
         self.ready_to_serve = locks.Event()
         self.ready_to_serve.clear()
         self.on_start_callbacks.append(self._connect_to_database)

      def _connect_to_database(self, _self, iol):
         def on_connected(future):
            if future.exception():
               iol.call_later(0.5, self._connect_to_database, _self, iol)
            else:
               self.ready_to_serve.set()

         future = dbconnector.connect()
         iol.add_future(future, on_connected)

   if __name__ == '__main__':
      run(Application)

Implementing a ``ready_to_serve`` event is a useful paradigm for applications
that need to asynchronously initialize before they can service requests.  We
can continue the example and add a ``/status`` endpoint that makes use of
the event:

.. code-block:: python
   :caption: Implementing health checks

   class StatusHandler(web.RequestHandler):
      @gen.coroutine
      def prepare(self):
         maybe_future = super().prepare()
         if concurrent.is_future(maybe_future):
            yield maybe_future
         if not self._finished and not self.application.ready_to_serve.is_set():
            self.set_header('Retry-After', '5')
            self.set_status(503, 'Not Ready')
            self.finish()

      def get(self):
         self.set_status(200)
         self.write(json.dumps({'status': 'ok'})

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

Testing your Application
------------------------
The :class:`~sprockets.http.testing.SprocketsHttpTestCase` class makes
it simple to test sprockets.http based applications.  It knows how to
call the appropriate callbacks at the appropriate time.  Use this as a
base class in place of :class:`~tornado.testing.AsyncHTTPTestCase` and
modify your ``get_app`` method to set ``self.app``.

.. autoclass:: sprockets.http.testing.SprocketsHttpTestCase
   :members:

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
         super().initialize()
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

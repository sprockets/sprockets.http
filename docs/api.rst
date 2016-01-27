API Documentation
=================

Application Runner
------------------
.. autofunction:: sprockets.http.run

Application Callbacks
~~~~~~~~~~~~~~~~~~~~~
Starting with version 0.4.0, :func:`sprockets.http.run` augments the
:class:`tornado.web.Application` instance with a new attribute named
``runner_callbacks`` which is a dictionary of lists of functions to
call when specific events occur.  The following events are supported:

:before_run:
   This set of callbacks is invoked after Tornado forks sub-processes
   (based on the ``number_of_procs`` setting) and before
   :meth:`~tornado.ioloop.IOLoop.start` is called.  Callbacks can
   safely access the :class:`~tornado.ioloop.IOLoop` without causing
   the :meth:`~tornado.ioloop.IOLoop.start` method to explode.

   If any callback raises an exception, then the application is
   terminated **before** the IOLoop is started.

:shutdown:
   When the application receives a stop signal, it will run each of the
   callbacks before terminating the application instance.  Exceptions
   raised by the callbacks are simply logged.

See :func:`sprockets.http.run` for a detailed description of how to
install the runner callbacks.

Internal Interfaces
~~~~~~~~~~~~~~~~~~~
.. automodule:: sprockets.http.runner
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

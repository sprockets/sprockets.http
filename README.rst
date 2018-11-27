sprockets.http
==============

|Version| |ReadTheDocs| |Travis| |Coverage|

The goal of this library is to make it a little easier to develop great
HTTP API services using the Tornado web framework.  It concentrates on
running applications in a reliable & resilient manner and handling errors
in a clean manner.

* ``SIGTERM`` is gracefully handled with respect to outstanding timeouts
  and callbacks
* Listening port is configured by the ``PORT`` environment variable
* *"Debug mode"* is enabled by the ``DEBUG`` environment variable

  - catches ``SIGINT`` (e.g., ``Ctrl+C``)
  - application run in a single process

Running Your Application
------------------------
Running a Tornado application intelligently should be very easy.  Ideally
your application wrapping code should look something like the following.

.. code-block:: python

   from tornado import web
   import sprockets.http

   def make_app(**settings):
       return web.Application([
          # insert your handlers
       ], **settings)

   if __name__ == '__main__':
       sprockets.http.run(make_app)

That's it.  The ``sprockets.http.run`` function will set up signal
handlers and make sure that your application terminates gracefully
when it is sent either an interrupt or terminate signal.

It also takes care of configuring the standard `logging`_ module albeit
in a opinionated way.  The goal is to let you write your application
without worrying about figuring out how to run and monitor it reliably.

If you are OO-minded, then you can also make use of a custom ``Application``
class instead of writing a ``make_app`` function:

.. code-block:: python

   import sprockets.http.app

   class Application(sprockets.http.app.Application):
       def __init__(self, *args, **kwargs):
           handlers = [
               # insert your handlers
           ]
           super().__init__(handlers, *args, **kwargs)

   if __name__ == '__main__':
       sprockets.http.run(Application)

This approach is handy if you have application level state and logic that
needs to be bundled together.

From setup.py
~~~~~~~~~~~~~
If you want, you can even run your application directly from ``setup.py``::

   $ ./setup.py httprun -a mymodule:make_app

The ``httprun`` command is installed as a ``distutils.command`` when you
install the ``sprockets.http`` package.  This command accepts the following
command line parameters:

:application:
   The "callable" that returns your application.  You want to specify
   whatever you are passing to ``sprockets.http.run()`` using a syntax
   similar to a `setuptools console script`_.  Basically, this is a string
   that contains the module name to import and the callable to invoke
   separated by a colon (e.g., ``mypackage.module.submodule:function``).
   **This is the only required parameter.**

:env-file:
   Optional name of a file containing environment variable definitions
   to parse and load into the environment before running the application.
   The file is a list of environment variables formatted as ``name=value``
   with one setting on each line.  If the line starts with ``export``, then
   the export portion is removed (for the sake of convenience).  If the
   ``value`` portion is omitted, then the environment variable named will
   be removed from the environment if it is present.

:port:
   Optional port number to bind the application to.  This will set the
   ``PORT`` environment variable *before* running the application and
   *after* the environment file is read.

.. _logging: https://docs.python.org/3/library/logging.html#module-logging
.. _setuptools console script: http://python-packaging.readthedocs.io/en/
   latest/command-line-scripts.html#the-console-scripts-entry-point

Error Logging
-------------
Handling errors should be simple as well.  Tornado already does a great
job of isolating the error handling into two methods on the request
handler:

- `send_error`_ is called by a request handler to send a HTTP error code
  to the caller.  This is what you should be calling in your code.  It
  handles setting the status, reporting the error, and finishing the
  request out.

- `write_error`_ is called by ``send_error`` when it needs to send an
  error document to the caller.  This should be overridden when you need
  to provide customized error pages.  The important thing to realize is
  that ``send_error`` calls ``write_error``.

.. _send_error: http://www.tornadoweb.org/en/branch4.0/web.html#tornado.web.RequestHandler.send_error
.. _write_error: http://www.tornadoweb.org/en/branch4.0/web.html#tornado.web.RequestHandler.write_error

So your request handlers are already doing something like the following:

.. code-block:: python

   class MyHandler(web.RequestHandler):
       def get(self):
          try:
             do_something()
          except:
             self.send_error(500, reason='Uh oh!')
             return

In order for this to be really useful to you (the one that gets pinged
when a failure happens), you need to have some information in your
application logs that points to the problem.  Cool... so do something
like this then:

.. code-block:: python

   class MyHandler(web.RequestHandler):
       def get(self):
          try:
             do_something()
          except:
             LOGGER.exception('do_something exploded for %s - returning %s',
                              self.request.uri, '500 Uh oh!')
             self.send_error(500, reason='Uh oh!')
             return

Simple enough.  This works in the small, but think about how this approach
scales.  After a while your error handling might end up looking like:

.. code-block:: python

   class MyHandler(web.RequestHandler):
       def get(self):
          try:
             do_something()

          except SomethingSerious:
             LOGGER.exception('do_something exploded for %s - returning %s',
                              self.request.uri, '500 Uh oh!')
             self.send_error(500, reason='Uh oh!')
             return

          except SomethingYouDid:
             LOGGER.exception('do_something exploded for %s - returning %s',
                              self.request.uri, '400 Stop That')
             self.send_error(400, reason='Stop That')
             return

Or maybe you are raising `tornado.web.HTTPError`_ instead of calling
``send_error`` -- *send_error will be called for you in this case*.
The ``sprockets.http.mixins.ErrorLogger`` mix-in extends ``write_error``
to log the failure to the ``self.logger`` **BEFORE** calling the ``super``
implementation.  This very simple piece of functionality ensures that when
your application is calling ``send_error`` to signal errors you are writing
the failure out somewhere so you will have it later.

.. _tornado.web.HTTPError: http://www.tornadoweb.org/en/branch4.0/web.html#tornado.web.HTTPError

It is also nice enough to log 4xx status codes as warnings, 5xx codes as
errors, and include exception tracebacks if an exception is being handled.
You can go back to writing ``self.send_error`` and let someone else keep
track of what happened.

Error Response Documents
------------------------
Now that we have useful information in our log files, we should be returning
something useful as well.  By default, the Tornado provided ``send_error``
implementation writes a simple HTML file as the response body.  The
``sprockets.http.mixins.ErrorWriter`` mix-in provides an implementation of
``write_error`` that is more amenable to programmatic usage.  By default
it uses a JSON body since that is the *defacto* format these days. Let's look
at our example again:

.. code-block:: python

   class MyHandler(web.RequestHandler):
       def get(self):
          try:
             do_something()
          except:
             self.send_error(500, reason='Uh oh!')
             return

The implementation of ``tornado.web.RequestHandler.write_error`` will produce
a response that looks something like:

.. code-block:: http

   HTTP/1.1 500 Uh oh!
   Server: TornadoServer/4.2.1
   Content-Type: text/html; charset=UTF-8
   Date: Fri, 20 Nov 2015 08:10:25 GMT

   <html><title>500: Uh oh!</title><body>500: Uh oh!</body></html>

That is a lot better than nothing but not very useful when your user is
someone else's code.  By adding ``sprockets.http.mixins.ErrorWriter`` to
the handler's inheritance chain, we would get the following response
instead:

.. code-block:: http

   HTTP/1.1 500 Uh oh!
   Server: TornadoServer/4.2.1
   Content-Type: application/json
   Date: Fri, 20 Nov 2015 08:10:25 GMT

   {"message": "Uh oh!", "type": null, "traceback": null}

The ``traceback`` and ``type`` properties hint at the fact that exceptions
are handled in a manner similar to what Tornado would do -- if the call to
``send_error`` includes exception information, then the exception's type
will be included in the response.  The ``traceback`` is only included when
the standard ``serve_traceback`` Tornado option is enabled.

If the ``sprockets.mixins.mediatype.ContentMixin`` is also extended by your
base class, ``write-error`` will use the ``ContentMixin.send_response`` method
for choosing the appropriate response format and sending the error response.

.. |Coverage| image:: https://codecov.io/github/sprockets/sprockets.http/coverage.svg?branch=master
   :target: https://codecov.io/github/sprockets/sprockets.http
.. |ReadTheDocs| image:: http://readthedocs.org/projects/sprocketshttp/badge/?version=master
   :target: https://sprocketshttp.readthedocs.io/
.. |Travis| image:: https://travis-ci.org/sprockets/sprockets.http.svg
   :target: https://travis-ci.org/sprockets/sprockets.http
.. |Version| image:: https://badge.fury.io/py/sprockets.http.svg
   :target: https://pypi.python.org/pypi/sprockets.http/

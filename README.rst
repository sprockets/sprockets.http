sprockets.http
==============
This library runs Tornado HTTP server applications intelligently.

* ``SIGTERM`` is gracefully handled with respect to outstanding timeouts
  and callbacks
* Listening port is configured by the ``PORT`` environment variable
* ``logging`` layer is configured to output JSON by default
* *"Debug mode"* is enabled by the ``DEBUG`` environment variable

  - makes log out human-readable
  - catches ``SIGINT`` (e.g., ``Ctrl+C``)
  - application run in a single process

Example Usage
-------------
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

Handling errors should be simple as well.  Tornado already does a great
job of isolating the error handling into two methods on the request
handler:

- ``send_error`` called by a request handler to send a HTTP error code
  to the caller.  This is what you should be calling in your code.  It
  handles setting the status, reporting the error, and finishing the
  request out.
- ``write_error`` is called by ``send_error`` when it needs to send an
  error document to the caller.  This should be overridden when you need
  to provide customized error pages.  The important thing to realize is
  that ``send_error`` calls ``write_error``.

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

Or maybe you are raising ``tornado.web.HTTPError`` instead of calling
``send_error`` -- *send_error will be called for you in this case*.
The ``sprockets.http.mixins.ErrorLogger`` mix-in extends ``write_error``
to log the failure to the ``self.logger`` **BEFORE** calling the ``super``
implementation.  This very simple piece of functionality ensures that when
your application is calling ``send_error`` to signal errors you are writing
the failure out somewhere so you will have it later.

It is also nice enough to log 4xx status codes as warnings, 5xx codes as
errors, and include exception tracebacks if an exception is being handled.
You can go back to writing ``self.send_error`` and let someone else keep
track of what happened.

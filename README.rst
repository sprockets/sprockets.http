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

.. code-block:: python

   from tornado import web
   import sprockets.http

   
   def make_app(**settings):
       return web.Application([
          # insert your handlers
       ], **settings)


   if __name__ == '__main__':
       sprockets.http.run(make_app)


API Documentation
=================
.. automodule:: sprockets.http
   :members:

Application Callbacks
---------------------
Starting with version 0.4.0, :func:`sprockets.http.run` augments the
:class:`tornado.web.Application` instance with a new attribute named
``runner_callbacks`` which is a dictionary of lists of functions to
call when specific events occur.  The only supported event is
**shutdown**.  When the application receives a stop signal, it will
run each of the callbacks before terminating the application instance.

See :func:`sprockets.http.run` for a detailed description of how to
install the runner callbacks.

Internal Interfaces
-------------------
.. automodule:: sprockets.http.runner
   :members:

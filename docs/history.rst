.. :changelog:

Release History
===============

:compare:`Next <2.5.0...master>`
--------------------------------
- Replace setuptools with hatch_

.. _hatch: https://hatch.pypa.io/latest/

:compare:`2.5.0 <2.4.0...2.5.0>` (26 May 2022)
----------------------------------------------
- Add customization of **Server** header

:compare:`2.4.0 <2.3.0...2.4.0>` (16 Mar 2022)
----------------------------------------------
- Add support for Python 3.10
- Change the default access log format

:compare:`2.3.0 <2.2.0...2.3.0>` (03 Feb 2022)
----------------------------------------------
- Added optional Sentry integration

:compare:`2.2.0 <2.1.2...2.2.0>` (28 Sep 2020)
----------------------------------------------
- Change xheaders option to default to ``True``

:compare:`2.1.2 <2.1.1...2.1.2>` (15 Sep 2020)
----------------------------------------------
- Updated to support Python 3.9.  ``asyncio.Task.all_tasks`` was removed
  so I switched to ``asyncio.all_tasks`` if it exists.
- Deprecate calling ``sprockets.http.run`` with anything that isn't a
  ``sprockets.app.Application`` instance.

:compare:`2.1.1 <2.1.0...2.1.1>` (19 Feb 2020)
----------------------------------------------
- :meth:`sprockets.http.app.CallbackManager.stop` no longer requires the
  event loop to be running (fixes `#34`_)

.. _#34: https://github.com/sprockets/sprockets.http/issues/34

:compare:`2.1.0 <2.0.1...2.1.0>` (9 Oct 2019)
---------------------------------------------
- Make shutdown timings configurable.
- Add :class:`sprockets.http.testing.SprocketsHttpTestCase`.
- Deprecate calling :func:`sprockets.http.run` without a specified
  logging configuration.

:compare:`2.0.1 <2.0.0...2.0.1>` (5 Mar 2019)
----------------------------------------------
- Include Tornado 6 in pin

:compare:`2.0.0 <1.5.0...2.0.0>` (27 Nov 2018)
----------------------------------------------
- Add support for Tornado 5.0
- Drop support for Tornado versions earlier than 5.0
- Drop support for Python versions earlier than 3.5
- Remove logging from the signal handler.  Logger's cannot safely be used
  from within signal handlers.  See `Thread Safety`_ in the logging module
  documentation for details.

.. _Thread Safety: https://docs.python.org/3/library/logging.html#thread-safety

:compare:`1.5.0 <1.4.2...1.5.0>` (29 Jan 2018)
----------------------------------------------
- Enable port reuse for Tornado versions newer than 4.3.

:compare:`1.4.2 <1.4.1...1.4.2>` (25 Jan 2018)
----------------------------------------------
- Allow max_body_size and max_buffer_size to be specified on the http server.

:compare:`1.4.1 <1.4.0...1.4.1>` (3 Jan 2018)
---------------------------------------------
- Workaround https://bitbucket.org/birkenfeld/sphinx-contrib/issues/184/
  by pinning sphinx in the development environment.

:compare:`1.4.0 <1.3.3...1.4.0>` (29 Sep 2017)
----------------------------------------------
- Separate the concerns of running the application from the callback
  chains.  The latter has been refactored into :mod:`sprockets.http.app`.
  This change is completely invisible to the outside world.
- Officially deprecated the ``runner_callbacks`` application attribute.

:compare:`1.3.3 <1.3.2...1.3.3>` (20 Sept 2016)
-----------------------------------------------
- Include correlation-id in the structured log data when logging.

:compare:`1.3.2 <1.3.1...1.3.2>` (19 Sept 2016)
-----------------------------------------------
- Include the service and environment (if set) in the structured log data.

:compare:`1.3.1 <1.3.0...1.3.1>` (16 Sept 2016)
-----------------------------------------------
- Change the non-DEBUG log format to include structured data and a leading first byte for log level.

:compare:`1.3.0 <1.2.0...1.3.0>` (11 Mar 2016)
----------------------------------------------
- Add ``httprun`` setup.py command.
- Use ``declare_namespace`` to declare the sprockets namespace package.
- Remove ``JSONRequestFormatter`` logging when not in debug mode
- Remove sprockets.logging dependency

:compare:`1.2.0 <1.1.2...1.2.0>` (11 Mar 2016)
----------------------------------------------
- Add support for the ``on_start`` callback.
- Add support to wait for the completion of ``shutdown`` callbacks that
  return a future.
- Adds new init params to runner.Runner for the three callback types

:compare:`1.1.2 <1.1.1...1.1.2>` (23 Feb 2016)
----------------------------------------------
- Allow xheaders to be set in the application.settings.

:compare:`1.1.1 <1.1.0...1.1.1>` (15 Feb 2016)
----------------------------------------------
- Delay grabbing the ``IOLoop`` instance until after fork.

:compare:`1.1.0 <1.0.2...1.1.0>` (11 Feb 2016)
----------------------------------------------
- Add support for the ``before_run`` callback set.

:compare:`1.0.2 <1.0.1...1.0.2>` (10 Dec 2015)
----------------------------------------------
- Add ``log_config`` parameter to ``sprockets.http.run``

:compare:`1.0.1 <1.0.0...1.0.1>` (20 Nov 2015)
----------------------------------------------
- Add support for ``sprockets.mixins.mediatype`` in ``sprockets.http.mixins.ErrorWriter``

:compare:`1.0.0 <0.4.0...1.0.0>` (20 Nov 2015)
----------------------------------------------
- Add ``sprockets.http.mixins.LoggingHandler``
- Add ``sprockets.http.mixins.ErrorLogger``
- Add ``sprockets.http.mixins.ErrorWriter``

:compare:`0.4.0 <0.3.0...0.4.0>` (24 Sep 2015)
----------------------------------------------
- Run callbacks from ``application.runner_callbacks['shutdown']`` when
  the application is shutting down.
- Add ``number_of_procs`` parameter to ``sprockets.http``.

:compare:`0.3.0 <0.2.2...0.3.0>` (28 Aug 2015)
----------------------------------------------
- Install :func:`sprockets.logging.tornado_log_function` as the logging
  function when we are running in release mode

:compare:`0.2.2 <0.2.1...0.2.2>` (23 Jul 2015)
----------------------------------------------

- Fixed requirements management... why is packaging so hard?!

:compare:`0.2.1 <0.2.0...0.2.1>` (23 Jul 2015)
----------------------------------------------
- Corrected packaging metadata

:compare:`0.2.0 <0.0.0...0.2.0>` (22 Jul 2015)
----------------------------------------------
- Add :func:`sprockets.http.run`

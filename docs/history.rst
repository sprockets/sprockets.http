.. :changelog:

Release History
===============

`2.4.0`_ (16 Mar 2022)
----------------------
- Add support for Python 3.10
- Change the default access log format

`2.3.0`_ (03 Feb 2022)
----------------------
- Added optional Sentry integration

`2.2.0`_ (28 Sep 2020)
----------------------
- Change xheaders option to default to ``True``

`2.1.2`_ (15 Sep 2020)
----------------------
- Updated to support Python 3.9.  ``asyncio.Task.all_tasks`` was removed
  so I switched to ``asyncio.all_tasks`` if it exists.
- Deprecate calling ``sprockets.http.run`` with anything that isn't a
  ``sprockets.app.Application`` instance.

`2.1.1`_ (19 Feb 2020)
----------------------
- :meth:`sprockets.http.app.CallbackManager.stop` no longer requires the
  event loop to be running (fixes `#34`_)

.. _#34: https://github.com/sprockets/sprockets.http/issues/34

`2.1.0`_ (9 Oct 2019)
---------------------
- Make shutdown timings configurable.
- Add :class:`sprockets.http.testing.SprocketsHttpTestCase`.
- Deprecate calling :func:`sprockets.http.run` without a specified
  logging configuration.

`2.0.1`_ (5 Mar 2019)
----------------------
- Include Tornado 6 in pin

`2.0.0`_ (27 Nov 2018)
----------------------
- Add support for Tornado 5.0
- Drop support for Tornado versions earlier than 5.0
- Drop support for Python versions earlier than 3.5
- Remove logging from the signal handler.  Logger's cannot safely be used
  from within signal handlers.  See `Thread Safety`_ in the logging module
  documentation for details.

.. _Thread Safety: https://docs.python.org/3/library/logging.html#thread-safety

`1.5.0`_ (29 Jan 2018)
----------------------
- Enable port reuse for Tornado versions newer than 4.3.

`1.4.2`_ (25 Jan 2018)
----------------------
- Allow max_body_size and max_buffer_size to be specified on the http server.

`1.4.1`_ (3 Jan 2018)
---------------------
- Workaround https://bitbucket.org/birkenfeld/sphinx-contrib/issues/184/
  by pinning sphinx in the development environment.

`1.4.0`_ (29 Sep 2017)
----------------------
- Separate the concerns of running the application from the callback
  chains.  The latter has been refactored into :mod:`sprockets.http.app`.
  This change is completely invisible to the outside world.
- Officially deprecated the ``runner_callbacks`` application attribute.

`1.3.3`_ (20 Sept 2016)
-----------------------
- Include correlation-id in the structured log data when logging.

`1.3.2`_ (19 Sept 2016)
-----------------------
- Include the service and environment (if set) in the structured log data.

`1.3.1`_ (16 Sept 2016)
-----------------------
- Change the non-DEBUG log format to include structured data and a leading first byte for log level.

`1.3.0`_ (11 Mar 2016)
----------------------
- Add ``httprun`` setup.py command.
- Use ``declare_namespace`` to declare the sprockets namespace package.
- Remove ``JSONRequestFormatter`` logging when not in debug mode
- Remove sprockets.logging dependency

`1.2.0`_ (11 Mar 2016)
----------------------
- Add support for the ``on_start`` callback.
- Add support to wait for the completion of ``shutdown`` callbacks that
  return a future.
- Adds new init params to runner.Runner for the three callback types

`1.1.2`_ (23 Feb 2016)
----------------------
- Allow xheaders to be set in the application.settings.

`1.1.1`_ (15 Feb 2016)
----------------------
- Delay grabbing the ``IOLoop`` instance until after fork.

`1.1.0`_ (11 Feb 2016)
----------------------
- Add support for the ``before_run`` callback set.

`1.0.2`_ (10 Dec 2015)
----------------------
- Add ``log_config`` parameter to ``sprockets.http.run``

`1.0.1`_ (20 Nov 2015)
----------------------
- Add support for ``sprockets.mixins.mediatype`` in ``sprockets.http.mixins.ErrorWriter``

`1.0.0`_ (20 Nov 2015)
----------------------
- Add ``sprockets.http.mixins.LoggingHandler``
- Add ``sprockets.http.mixins.ErrorLogger``
- Add ``sprockets.http.mixins.ErrorWriter``

`0.4.0`_ (24 Sep 2015)
----------------------
- Run callbacks from ``application.runner_callbacks['shutdown']`` when
  the application is shutting down.
- Add ``number_of_procs`` parameter to ``sprockets.http``.

`0.3.0`_ (28 Aug 2015)
----------------------
- Install :func:`sprockets.logging.tornado_log_function` as the logging
  function when we are running in release mode

`0.2.2`_ (23 Jul 2015)
----------------------
- Fixed requirements management... why is packaging so hard?!

`0.2.1`_ (23 Jul 2015)
----------------------
- Corrected packaging metadata

`0.2.0`_ (22 Jul 2015)
----------------------
- Add :func:`sprockets.http.run`

.. _0.2.0: https://github.com/sprockets/sprockets.http/compare/0.0.0...0.2.0
.. _0.2.1: https://github.com/sprockets/sprockets.http/compare/0.2.0...0.2.1
.. _0.2.2: https://github.com/sprockets/sprockets.http/compare/0.2.1...0.2.2
.. _0.3.0: https://github.com/sprockets/sprockets.http/compare/0.2.2...0.3.0
.. _0.4.0: https://github.com/sprockets/sprockets.http/compare/0.3.0...0.4.0
.. _1.0.0: https://github.com/sprockets/sprockets.http/compare/0.4.0...1.0.0
.. _1.0.1: https://github.com/sprockets/sprockets.http/compare/1.0.0...1.0.1
.. _1.0.2: https://github.com/sprockets/sprockets.http/compare/1.0.1...1.0.2
.. _1.1.0: https://github.com/sprockets/sprockets.http/compare/1.0.2...1.1.0
.. _1.1.1: https://github.com/sprockets/sprockets.http/compare/1.1.0...1.1.1
.. _1.1.2: https://github.com/sprockets/sprockets.http/compare/1.1.1...1.1.2
.. _1.2.0: https://github.com/sprockets/sprockets.http/compare/1.0.2...1.2.0
.. _1.3.0: https://github.com/sprockets/sprockets.http/compare/1.2.0...1.3.0
.. _1.3.1: https://github.com/sprockets/sprockets.http/compare/1.3.0...1.3.1
.. _1.3.2: https://github.com/sprockets/sprockets.http/compare/1.3.1...1.3.2
.. _1.3.3: https://github.com/sprockets/sprockets.http/compare/1.3.2...1.3.3
.. _1.4.0: https://github.com/sprockets/sprockets.http/compare/1.3.3...1.4.0
.. _1.4.1: https://github.com/sprockets/sprockets.http/compare/1.4.0...1.4.1
.. _1.4.2: https://github.com/sprockets/sprockets.http/compare/1.4.1...1.4.2
.. _1.5.0: https://github.com/sprockets/sprockets.http/compare/1.4.2...1.5.0
.. _2.0.0: https://github.com/sprockets/sprockets.http/compare/1.5.0...2.0.0
.. _2.0.1: https://github.com/sprockets/sprockets.http/compare/2.0.0...2.0.1
.. _2.1.0: https://github.com/sprockets/sprockets.http/compare/2.0.1...2.1.0
.. _2.1.1: https://github.com/sprockets/sprockets.http/compare/2.1.0...2.1.1
.. _2.1.2: https://github.com/sprockets/sprockets.http/compare/2.1.1...2.1.2
.. _2.2.0: https://github.com/sprockets/sprockets.http/compare/2.1.2...2.2.0
.. _2.3.0: https://github.com/sprockets/sprockets.http/compare/2.2.0...2.3.0
.. _2.4.0: https://github.com/sprockets/sprockets.http/compare/2.3.0...2.4.0
.. _Next Release: https://github.com/sprockets/sprockets.http/compare/2.4.0...master

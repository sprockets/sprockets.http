.. :changelog:

Release History
===============

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
.. _0.3.0: https://github.com/sprockets/sprockets.http/compare/0.2.0...0.3.0
.. _0.4.0: https://github.com/sprockets/sprockets.http/compare/0.3.0...0.4.0

from tornado import testing


class SprocketsHttpTestCase(testing.AsyncHTTPTestCase):
    """Test case that correctly runs a sprockets.http.app.Application.

    This test case correctly starts and stops a sprockets.http Application
    by calling the :meth:`~sprockets.http.app.CallbackManager.start` and
    :meth:`~sprockets.http.app.CallbackManager.stop` methods during ``setUp``
    and ``tearDown``.

    .. attribute:: app

       You are required to set this attribute in your :meth:`.get_app`
       implementation.

    """

    shutdown_limit = 0.25
    """Maximum number of seconds to wait for the application to shut down."""

    wait_timeout = 0.05
    """Number of seconds to wait between checking for pending callbacks."""

    def setUp(self):
        """Hook method for setting up the test fixture before exercising it.

        The sprockets.http application is started by calling the
        :meth:`~sprockets.http.app.CallbackManager.start` method after the
        application is created.

        """
        self.app = None
        super(SprocketsHttpTestCase, self).setUp()
        self.app.start(self.io_loop)

    def tearDown(self):
        """Hook method for deconstructing the test fixture after exercising it.

        The sprockets.http application is fully stopped by calling the
        :meth:`~sprockets.http.app.CallbackManager.stop` and running the ioloop
        *before* stopping the ioloop.  The shutdown timing is configured using
        the :attr:`.shutdown_limit` and :attr:`.wait_timeout` variables.

        """
        self.app.stop(self.io_loop, self.shutdown_limit, self.wait_timeout)
        self.io_loop.start()
        super(SprocketsHttpTestCase, self).tearDown()

    def get_app(self):
        """Override this method to create your application.

        Make sure to set ``self.app`` before returning.

        """
        raise NotImplementedError

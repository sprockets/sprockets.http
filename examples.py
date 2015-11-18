import os

from tornado import web

from sprockets.http import mixins, run


class StatusHandler(mixins.ErrorLogger, web.RequestHandler):
    """Example that exercises the status code handling of the ErrorLogger."""

    def get(self, status_code):
        """
        Returns the requested status.

        :param int status_code: the status code to return
        :queryparam str reason: optional reason phrase

        """
        status_code = int(status_code)
        if status_code >= 400:
            if self.get_query_argument('reason', None):
                self.send_error(status_code=status_code,
                                reason=self.get_query_argument('reason'))
            else:
                self.send_error(status_code=status_code)
        else:
            self.set_status(status_code)


def make_app(**settings):
    settings['debug'] = True  # disable JSON logging
    return web.Application([
        web.url(r'/status/(?P<status_code>\d+)', StatusHandler),
    ], **settings)


if __name__ == '__main__':
    run(make_app)

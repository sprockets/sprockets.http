import logging
import logging.config
import os
import sys
import warnings

try:
    import sentry_sdk
    import sentry_sdk.integrations.logging
    import sentry_sdk.integrations.tornado

    _sentry_integrations = [
        sentry_sdk.integrations.logging.LoggingIntegration(
            event_level=logging.CRITICAL),
        sentry_sdk.integrations.tornado.TornadoIntegration(),
    ]
except ModuleNotFoundError:
    pass


version_info = (2, 4, 0)
__version__ = '.'.join(str(v) for v in version_info)

_unspecified = object()


def run(create_application, settings=None, log_config=_unspecified):
    """
    Run a Tornado create_application.

    :param create_application: function to call to create a new
        application instance
    :param dict|None settings: optional configuration dictionary
        that will be passed through to ``create_application``
        as kwargs.
    :param dict|None log_config: optional logging configuration
        dictionary to use.  By default, a reasonable logging
        configuration is generated based on settings.  If you
        need to override the configuration, then use this parameter.
        It is passed as-is to :func:`logging.config.dictConfig`.

    .. rubric:: settings['debug']

    If the `settings` parameter includes a value for the ``debug``
    key, then the application will be run in Tornado debug mode.

    If the `settings` parameter does not include a ``debug`` key,
    then debug mode will be enabled based on the :envvar:`DEBUG`
    environment variable.

    .. rubric:: settings['port']

    If the `settings` parameter includes a value for the ``port``
    key, then the application will be configured to listen on the
    specified port.  If this key is not present, then the :envvar:`PORT`
    environment variable determines which port to bind to.  The
    default port is 8000 if nothing overrides it.

    .. rubric:: settings['number_of_procs']

    If the `settings` parameter includes a value for the ``number_of_procs``
    key, then the application will be configured to run this many processes
    unless in *debug* mode.  This is passed to ``HTTPServer.start``.

    .. rubric:: settings['xheaders']

    If the `settings` parameter includes a value for the ``xheaders``
    key, then the application will be configured to use headers, like
    X-Real-IP, to get the user's IP address instead of attributing all
    traffic to the load balancer's IP address. When running behind a load
    balancer like nginx, it is recommended to pass xheaders=True. The default
    value is True if nothing overrides it.

    """
    from . import runner

    app_settings = {} if settings is None else settings.copy()
    debug_mode = bool(app_settings.get('debug',
                                       int(os.environ.get('DEBUG', 0)) != 0))
    app_settings['debug'] = debug_mode
    if log_config is _unspecified:
        warnings.warn(
            'calling sprockets.http.run without logging configuration is '
            'deprecated and will fail in the future', DeprecationWarning)
        logging.config.dictConfig(_get_logging_config(debug_mode))
        logging.warning(
            'calling sprockets.http.run without logging configuration is '
            'deprecated and will fail in the future')
    else:
        logging.config.dictConfig(log_config)

    port_number = int(app_settings.pop('port', os.environ.get('PORT', 8000)))
    num_procs = int(app_settings.pop('number_of_procs', '0'))
    app = create_application(**app_settings)

    if 'sentry_sdk' in sys.modules:
        kwargs = {
            'integrations': _sentry_integrations,
            'release': app.settings.get('version'),
            'environment': app.settings.get('environment'),
        }
        kwargs.update(app.settings.get('sentry_sdk_init') or {})
        sentry_sdk.init(**kwargs)

    server = runner.Runner(app)
    server.run(port_number, num_procs)


class _CorrelationFilter(logging.Filter):
    """Log filter that ensures that correlation_id is set on each record"""

    def filter(self, record):
        if not hasattr(record, 'correlation-id'):
            setattr(record, 'correlation-id', '')
        return 1


def _get_logging_config(debug):
    # Service and environment for logging structured data (if set)
    log_sd = ''
    if os.environ.get('SERVICE') and os.environ.get('ENVIRONMENT'):
        log_sd = ' service="{}" environment="{}"'.format(
            os.environ['SERVICE'], os.environ['ENVIRONMENT'])
    if debug:
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': False,
            'formatters': {
                'debug': {
                    'format': ('[%(asctime)s] %(levelname)-8s %(name)s: '
                               '%(message)s')
                },
            },
            'handlers': {
                'debug-console': {
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                    'level': 'DEBUG',
                    'formatter': 'debug',
                },
            },
            'root': {
                'level': 'DEBUG',
                'handlers': ['debug-console'],
            }
        }
    else:
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': False,
            'formatters': {
                'info': {
                    'format': ('%(levelname)1.1s'
                               '[sprockets@34085'
                               '{}'
                               ' correlation_id="%(correlation-id)s"'
                               ' logger="%(name)s"'
                               ' process="%(process)s"'
                               ' line="%(lineno)d"'
                               ' function="%(funcName)s"'
                               ' module="%(module)s"'
                               '] %(message)s'.format(log_sd))
                }
            },
            'filters': {
                'correlation': {
                    '()': _CorrelationFilter,
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                    'level': 'INFO',
                    'formatter': 'info',
                    'filters': ['correlation']
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['console'],
            }
        }

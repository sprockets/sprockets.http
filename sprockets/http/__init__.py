import logging
import os


version_info = (1, 0, 2)
__version__ = '.'.join(str(v) for v in version_info)


def run(create_application, settings=None, log_config=None):
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
    This setting also changes how the logging layer is configured.
    When running in "debug" mode, logs are written to standard out
    using a human-readable format instead of the standard JSON
    payload.

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

    .. rubric:: application.runner_callbacks['shutdown']

    The ``runner_callbacks`` attribute is a :class:`dict` of lists
    of functions to call when an event occurs.  The *shutdown* key
    contains functions that are invoked when a stop signal is
    received *before* the IOLoop is stopped.

    This attribute will be created **AFTER** `create_application` is
    called and **BEFORE** this function returns.  If the attribute
    exists on the instance returned from `create_application` , then
    it will be used as-is.

    """
    from . import runner

    app_settings = {} if settings is None else settings.copy()
    debug_mode = bool(app_settings.get('debug',
                                       int(os.environ.get('DEBUG', 0)) != 0))
    app_settings['debug'] = debug_mode
    logging.config.dictConfig(_get_logging_config(debug_mode)
                              if log_config is None else log_config)

    port_number = int(app_settings.pop('port', os.environ.get('PORT', 8000)))
    num_procs = int(app_settings.pop('number_of_procs', '0'))
    server = runner.Runner(create_application(**app_settings))

    server.run(port_number, num_procs)


def _get_logging_config(debug):
    if debug:
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'incremental': False,
            'formatters': {
                'debug': {
                    'format': ('[%(asctime)s] %(levelname)-8s %(process)-6s '
                               '%(name)s: %(message)s.')
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
                'json': {
                    '()': 'sprockets.logging.JSONRequestFormatter',
                },
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'json',
                },
            },
            'root': {
                'level': 'INFO',
                'handlers': ['console'],
            }
        }

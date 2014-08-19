"""
Sprockets HTTP

"""
__version__ = '0.1.0'
version = __version__

import logging

LOGGER = logging.getLogger(__name__)

def add_arguments(parser):
  LOGGER.debug('add_arguments invoked')


def main(config):
  LOGGER.debug('main invoked')

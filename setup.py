#!/usr/bin/env python
#

import pathlib

import setuptools

from sprockets import http


def read_requirements(name):
    requirements = []
    for line in pathlib.Path('requires', name).read_text().split('\n'):
        if '#' in line:
            line = line[:line.index('#')]
        line = line.strip()
        if line.startswith('-'):
            pass
        requirements.append(line)
    return requirements


setuptools.setup(
    name='sprockets.http',
    version=http.__version__,
    description='Tornado HTTP application runner',
    author='AWeber Communications',
    author_email='api@aweber.com',
    url='https://github.com/sprockets/sprockets.http',
    install_requires=read_requirements('installation.txt'),
    license='BSD',
    namespace_packages=['sprockets'],
    packages=setuptools.find_packages(),
    entry_points={
        'distutils.commands': ['httprun=sprockets.http.runner:RunCommand'],
    },
    extras_require={
        'sentry': ['sentry-sdk>=1.5.4,<2'],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'],
    tests_require=read_requirements('testing.txt'),
    python_requires='>=3.5',
    zip_safe=True,
)

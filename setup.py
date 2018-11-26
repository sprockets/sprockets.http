#!/usr/bin/env python
#
import os.path

import setuptools

from sprockets import http


def read_requirements(filename):
    requirements = []
    try:
        with open(os.path.join('requires', filename)) as req_file:
            for line in req_file:
                if '#' in line:
                    line = line[:line.index('#')]
                line = line.strip()
                if line.startswith('-'):
                    pass
                requirements.append(line)
    except IOError:
        pass
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
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'],
    test_suite='nose.collector',
    tests_require=read_requirements('testing.txt'),
    zip_safe=True
)

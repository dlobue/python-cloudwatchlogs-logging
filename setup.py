#!/usr/bin/env python

from setuptools import setup

setup(name='python-cloudwatchlogs-logging',
      version='0.0.3',
      description='''Handler for easy logging to AWS CloudWatchLogs.''',
      long_description='''Handler for easy logging to AWS CloudWatchLogs. ''',
      author="Arne Hilmann",
      author_email="arne.hilmann@gmail.com",
      license='Apache License 2.0',
      url='https://github.com/ImmobilienScout24/python-cloudwatchlogs-logging',
      packages=['cloudwatchlogs_logging'],
      py_modules=[],
      classifiers=['Development Status :: 2 - Pre-Alpha',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'Intended Audience :: System Administrators',
                   'Programming Language :: Python',
                   'Topic :: System :: Networking',
                   'Topic :: System :: Software Distribution',
                   'Topic :: System :: Systems Administration'],
      install_requires=["boto"],
      tests_require=["mock==1.0.1"],
      test_suite='test',
      zip_safe=True)


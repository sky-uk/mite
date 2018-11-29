#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='mite',
    packages=find_packages(),
    version='0.0.1a',
    install_requires=[
        'docopt',
        'msgpack-python',
        'acurl',
        'bs4',
        'nanomsg',
        'flask',
        'pyzmq',
        'uvloop',
    ],
    entry_points={
        'console_scripts': [
            'mite = mite.__main__:main',
        ],
    },
    setup_requires=['pytest-runner'],
    tests_require=['pytest']
)

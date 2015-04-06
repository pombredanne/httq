#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2015, Nigel Small
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from httq import __author__, __email__, __license__, __version__


setup(
    name="httq",
    version=__version__,
    description='fast and lightweight HTTP client written in pure Python',
    long_description=open("README.rst").read(),
    author=__author__,
    author_email=__email__,
    url="http://httq.io/",
    py_modules=["httq"],
    scripts=["httq.py"],
    entry_points={
        "console_scripts": [
            "httq = httq:main",
        ],
    },
    install_requires=[],
    license=__license__,
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development",
    ],
)

====
HTTQ
====

.. module:: httq

HTTQ is a fast and lightweight HTTP client written in pure Python and distributed under the Apache 2 license.
It is contained within a single file module with no external dependencies so it can be easily dropped into existing projects.


Quick Example
=============

>>> from httq import HTTP
>>> http = HTTP(b"nigelsmall.com")
>>> http.get(b"/hello").response().read()
b'hello, world'


Download
========

::

    wget http://httq.io/httq.py


API
===

.. autoclass:: HTTP
   :members:
.. autoclass:: ConnectionError
   :members:

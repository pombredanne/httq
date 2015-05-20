====
HTTQ
====

.. module:: httq

HTTQ is a fast and lightweight HTTP client written in pure Python and distributed under the Apache 2 license.
It is contained within a single file module with no external dependencies so it can be easily dropped into existing projects.


Quick Example
=============

>>> from httq import HTTP
>>> http = HTTP(b"httq.io:8080")
>>> print(http.get(b"/hello").response().content)
hello, world


Download
========

::

    wget http://httq.io:8080/httq.py


Overview
========

- HTTP/HTTPS
- Resource
- Module functions
    - get/head/put/patch/post/delete
    - basic_auth
    - internet_time
    - parse_header
    - parse_uri
    - parse_uri_authority
- SocketError


Managing Connections
====================

- DEFAULT_PORT
- connect
- close
- reconnect
- host


Sending Requests
================

- request
- request_method
- request_url
- request_headers
- options/get/head/post/put/patch/delete/trace
- writable
- write


Receiving Responses
===================

- readable
- read
- readall
- readinto
- version
- status_code
- reason
- headers
- content_type
- encoding
- content


Working with Resources
======================

TODO

Full API
========

.. autoclass:: HTTP
   :members:
.. autoclass:: HTTPS
   :members:
.. autoclass:: Resource
   :members:
.. autoclass:: SocketError
   :members:

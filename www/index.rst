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

The HTTQ module exports three levels of API, ranging from most flexible to most convenient.
At the lowest level, the :class:`HTTP` and :class:`HTTPS` classes expose a connection-level facility where request and response transmission can be finely controlled.
The :class:`Resource`  class wraps a URL, exposes ``GET``, ``POST`` and other HTTP methods as instance methods and manages reconnection implicitly.
Finally, several module level functions are offered, such as :func:`get`, which can be used in a similar way to the builtin function :func:`open`.

And as well as direct HTTP functionality, a few helper functions are provided to help coerce values to and from raw byte representations.


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


HTTP API
========

The HTTP API exists within a single class: :class:`HTTP` (or :class:`HTTPS` for secure transfer).
This class contains three distinct sets of methods and attributes: connection management, request handling and response handling.
Each of these logical API is described in the relevant section below.


Connection Management
---------------------

.. autoclass:: HTTP
   :members: DEFAULT_PORT, host, connect, reconnect, close


Request Handling
----------------

.. autoclass:: HTTP
   :members: request, request_method, request_url, request_headers,
             options, get, head, post, put, patch, delete, trace,
             writable, write


Response Handling
-----------------

.. autoclass:: HTTP
   :members: response, version, status_code, reason, headers,
             readable, read, readinto, content_type, encoding, content


HTTPS
-----

.. autoclass:: HTTPS
   :members:


Resource API
============

.. autoclass:: Resource
   :members:


Helper Functions
================

.. autofunction:: get
.. autofunction:: head
.. autofunction:: put
.. autofunction:: patch
.. autofunction:: post
.. autofunction:: delete


Errors
======

.. autoclass:: SocketError
   :members:

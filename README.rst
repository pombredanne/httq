====
HTTQ
====

HTTQ is a fast and lightweight HTTP client written in pure Python and distributed under the Apache 2 license.
It is contained within a single file module with no external dependencies so it can be easily dropped into existing projects.

The `HTTP` class has separate methods for sending requests and receiving responses.
This decoupling allows multiple requests to be pipelined on a single connection prior to the corresponding responses being read. 

Example Code
============

.. code:: python

    >>> from httq import HTTP
    >>> http = HTTP(b"httq.io:8080")
    >>> print(http.get(b"/hello").response().content)
    hello, world

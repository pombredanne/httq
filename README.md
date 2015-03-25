# HTTQ

HTTQ is a fast and lightweight HTTP client written in pure Python.
It no dependencies outside the standard library and exists as a single module that can be dropped into an existing project.

The lowest level API provided by HTTQ is the `HTTP` class.
To create an instance of this class, only a host value needs to be provided:

```python
from httq import HTTP
http = HTTP(b"localhost")
```

If the HTTP connection needs to be made to a port other than port 80, this can be specified after a colon:

```python
http = HTTP(b"localhost:8080")
```

A simple `GET` request can be sent using the `get` method:

```python
http.get(b"/foo")
```

The response headers can then be read with the `response` method and the actual content body with the `read` method:

```python
content = http.response().read()
```

The `get` method returns the `HTTP` instance itself so these methods can be easily chained together:

```python
content = http.get(b"/foo").response().read()
```

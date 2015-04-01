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


from base64 import b64encode
from io import DEFAULT_BUFFER_SIZE
import json
from select import select
import socket
import sys
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


DEFAULT_PORT = 80

METHODS = {m.decode("UTF-8"): m
           for m in [b"OPTIONS", b"GET", b"HEAD", b"POST", b"PUT", b"DELETE", b"TRACE"]}


if sys.version_info >= (3,):
    SPACE = ord(' ')

    def bstr(s, encoding="ISO-8859-1"):
        if isinstance(s, bytes):
            return s
        elif isinstance(s, bytearray):
            return bytes(s)
        elif isinstance(s, str):
            return s.encode(encoding)
        else:
            return str(s).encode(encoding)

    def hexb(n):
        return hex(n)[2:].encode("UTF-8")

else:
    SPACE = b' '

    def bstr(s, encoding="ISO-8859-1"):
        if isinstance(s, bytes):
            return s
        elif isinstance(s, unicode):
            return s.encode(encoding)
        else:
            return bytes(s)

    def hexb(n):
        return hex(n)[2:]


def basic_auth(user_id, password):
    return b"Basic " + b64encode(b":".join((bstr(user_id), bstr(password))))


def internet_time(value):
    # TODO
    return bstr(value)


REQUEST_HEADERS = {
    "accept": b"Accept",
    "accept_charset": b"Accept-Charset",
    "accept_datetime": b"Accept-Datetime",
    "accept_encoding": b"Accept-Encoding",
    "accept_language": b"Accept-Language",
    "authorization": b"Authorization",
    "cache_control": b"Cache-Control",
    "connection": b"Connection",
    "content_md5": b"Content-MD5",
    "content_type": b"Content-Type",
    "cookie": b"Cookie",
    "date": b"Date",
    "expect": b"Expect",
    "from": b"From",
    "if_match": b"If-Match",
    "if_modified_since": b"If-Modified-Since",
    "if_none_match": b"If-None-Match",
    "if_range": b"If-Range",
    "if_unmodified_since": b"If-Unmodified-Since",
    "max_forwards": b"Max-Forwards",
    "origin": b"Origin",
    "pragma": b"Pragma",
    "proxy_authorization": b"Proxy-Authorization",
    "range": b"Range",
    "referer": b"Referer",
    "te": b"TE",
    "user_agent": b"User-Agent",
    "upgrade": b"Upgrade",
    "via": b"Via",
    "warning": b"Warning",
}

STATUS_CODES = {bstr(code): code for code in range(100, 600)}
NO_CONTENT_STATUS_CODES = list(range(100, 200)) + [204, 304]


def parse_header(value):
    if value is None:
        return None, None
    if not isinstance(value, bytes):
        value = bstr(value)
    p = 0
    delimiter = value.find(b";", p)
    eol = len(value)
    if p <= delimiter < eol:
        string_value = value[p:delimiter]
        params = {}
        while delimiter < eol:
            # Skip whitespace after previous delimiter
            p = delimiter + 1
            while p < eol and value[p] == SPACE:
                p += 1
            # Find next delimiter
            delimiter = value.find(b";", p)
            if delimiter == -1:
                delimiter = eol
            # Add parameter
            eq = value.find(b"=", p)
            if p <= eq < delimiter:
                params[value[p:eq]] = value[(eq + 1):delimiter]
            elif p < delimiter:
                params[value[p:delimiter]] = None
    else:
        string_value = value[p:]
        params = {}
    return string_value, params


class ConnectionError(IOError):

    def __init__(self, *args, **kwargs):
        super(ConnectionError, self).__init__(*args, **kwargs)


class HTTP(object):
    """ Low-level HTTP client providing access to raw request and response functions.

    :param host:
    :type host: bytes
    :param headers:
    """

    _socket = None
    _received = b""

    _has_content = None
    _content_length = None
    _chunked = None

    _content = b""
    _content_type = None
    _encoding = None
    _typed_content = None
    _request_headers = {}
    _response_headers = {}

    #: Boolean flag indicating whether a chunked request is currently being written.
    writable = False
    #: HTTP version from last response
    version = None
    #: Status code from last response
    status_code = None
    #: Reason phrase from last response
    reason = None

    def __init__(self, host, **headers):
        self.connect(host, **headers)

    def __del__(self):
        try:
            self.close()
        except socket.error:
            pass

    def _recv(self, n):
        s = self._socket
        ready_to_read, _, _ = select((s,), (), (), 0)
        if ready_to_read:
            data = s.recv(n)
            data_length = len(data)
            if data_length == 0:
                raise ConnectionError("Peer has closed connection")
            self._received += data
            return data_length
        else:
            return 0

    def _read(self, n):
        recv = self._recv
        required = n - len(self._received)
        while required > 0:
            if required > DEFAULT_BUFFER_SIZE:
                required -= recv(required)
            elif required > 0:
                required -= recv(DEFAULT_BUFFER_SIZE)
        received = self._received
        data, self._received = received[:n], received[n:]
        return data

    def _read_line(self):
        recv = self._recv
        eol = self._received.find(b"\r\n")
        while eol == -1:
            p = len(self._received)
            while recv(DEFAULT_BUFFER_SIZE) == 0:
                pass
            eol = self._received.find(b"\r\n", p)
        received = self._received
        data, self._received = received[:eol], received[(eol + 2):]
        return data

    def connect(self, host, **headers):
        """ Establish a connection to a remote host.

        :param host: the host to which to connect
        :type host: bytes
        :param headers: headers to pass into each request for this connection
        """
        if not isinstance(host, bytes):
            host = bstr(host)

        # Reset connection attributes and headers
        self._request_headers.clear()
        self._request_headers[b"Host"] = host

        for name, value in headers.items():
            try:
                name = REQUEST_HEADERS[name]
            except KeyError:
                name = bstr(name).replace(b"_", b"-").title()
            if not isinstance(value, bytes):
                value = bstr(value)
            self._request_headers[name] = value

        # Establish connection
        host, _, port = host.partition(b":")
        if port:
            port = int(port)
        else:
            port = DEFAULT_PORT

        self._socket = socket.create_connection((host, port))
        self._received = b""

    def reconnect(self):
        """ Re-establish a connection to the same remote host.
        """
        host = self.host
        headers = dict(self._request_headers)
        self.close()
        self.connect(host)
        self._request_headers.update(headers)

    def close(self):
        """ Close the current connection.
        """
        if self._socket:
            self._socket.close()
            self._socket = None
        self._received = b""

        self._request_headers.clear()

    @property
    def host(self):
        """ The remote host to which this client is connected.
        """
        return self._request_headers[b"Host"]

    def request(self, method, url, body=None, **headers):
        """ Make or initiate a request to the remote host.

        For simple (non-chunked) requests, pass the `method`, `url` and
        `body` plus any extra `headers`, if required. An empty body can
        be specified by passing :code:`b''` as the `body` argument::

        >>> http.request(b'GET', '/foo/1', b'')

        >>> http.request(b'POST', '/foo/', b'{"foo": "bar"}', content_type=b'application/json')

        Chunked requests can be initiated by passing :const:`None` to
        the `body` argument (either explicitly or using hte default
        value) and following the :func:`request` with one or more
        :func:`write` operations::

        >>> http.request(b'POST', '/foo/')
        >>> http.write(b'data chunk 1')
        >>> http.write(b'data chunk 2')
        >>> http.write(b'')

        :param method: request method, e.g. :code:`b'GET'`
        :type method: bytes
        :param url: relative URL for this request
        :type url: bytes
        :param body: the byte content to send with this request
                     or :const:`None` for separate, chunked data
        :type body: bytes
        :param headers:
        """
        if not isinstance(method, bytes):
            try:
                method = METHODS[method]
            except KeyError:
                method = bstr(method)

        if not isinstance(url, bytes):
            url = bstr(url)

        if self.writable:
            self.write(b"")

        # Request line
        data = [method, b" ", url, b" HTTP/1.1\r\n"]

        # Common headers
        for key, value in self._request_headers.items():
            data += [key, b": ", value, b"\r\n"]

        # Other headers
        for name, value in headers.items():
            try:
                name = REQUEST_HEADERS[name]
            except KeyError:
                name = bstr(name).replace(b"_", b"-").title()
            if not isinstance(value, bytes):
                value = bstr(value)
            data += [name, b": ", value, b"\r\n"]

        if body is None:
            # Chunked content
            data.append(b"Transfer-Encoding: chunked\r\n\r\n")
            self.writable = True

        else:
            # Fixed-length content
            if isinstance(body, dict):
                data += [b"Content-Type: application/json\r\n"]
                body = json.dumps(body, ensure_ascii=True, separators=",:").encode("UTF-8")
            elif not isinstance(body, bytes):
                body = bstr(bytes)
            content_length = len(body)
            if content_length == 0:
                data.append(b"\r\n")
            else:
                data += [b"Content-Length: ", bstr(content_length), b"\r\n\r\n", body]
            self.writable = False

        # Send
        try:
            joined = b"".join(data)
            self._socket.sendall(joined)
        except socket.error:
            raise ConnectionError("Peer has closed connection")

        return self

    def options(self, url=b"*", body=None, **headers):
        """ Make or initiate an OPTIONS request to the remote host.

        :param url:
        :type url: bytes
        :param body:
        :type body: bytes
        :param headers:
        """
        return self.request(b"OPTIONS", url, body, **headers)

    def get(self, url, **headers):
        """ Make a GET request to the remote host.

        :param url:
        :type url: bytes
        :param headers:
        """
        return self.request(b"GET", url, b"", **headers)

    def head(self, url, **headers):
        """ Make a HEAD request to the remote host.

        :param url:
        :type url: bytes
        :param headers:
        """
        return self.request(b"HEAD", url, b"", **headers)

    def post(self, url, body=None, **headers):
        """ Make or initiate a POST request to the remote host.

        :param url:
        :type url: bytes
        :param body:
        :type body: bytes
        :param headers:
        """
        return self.request(b"POST", url, body, **headers)

    def put(self, url, body=None, **headers):
        """ Make or initiate a PUT request to the remote host.

        :param url:
        :type url: bytes
        :param body:
        :type body: bytes
        :param headers:
        """
        return self.request(b"PUT", url, body, **headers)

    def delete(self, url, **headers):
        """ Make a DELETE request to the remote host.

        :param url:
        :type url: bytes
        :param headers:
        """
        return self.request(b"DELETE", url, b"", **headers)

    def trace(self, url, body=None, **headers):
        """ Make or initiate a TRACE request to the remote host.

        :param url:
        :type url: bytes
        :param body:
        :type body: bytes
        :param headers:
        """
        return self.request(b"TRACE", url, body, **headers)

    def write(self, *chunks):
        """ Write one or more chunks of request data to the remote host.

        :param chunks:
        """
        assert self.writable, "No chunked request sent"

        data = []
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            chunk_length = len(chunk)
            data += [hexb(chunk_length), b"\r\n", chunk, b"\r\n"]
            if chunk_length == 0:
                self.writable = False
                break
        joined = b"".join(data)
        self._socket.sendall(joined)

        return self

    def response(self):
        if self._content_length or self._chunked:
            self.read()

        read_line = self._read_line
        headers = self._response_headers

        # Status line
        status_line = read_line()
        p = status_line.find(b" ")
        self.version = status_line[:p]  # TODO: convert to text
        p += 1
        q = status_line.find(b" ", p)
        status_code = STATUS_CODES[status_line[p:q]]  # faster than using the int function
        self.status_code = status_code
        self.reason = status_line[(q + 1):]  # TODO: convert to text

        # Headers
        headers.clear()
        has_content = status_code not in NO_CONTENT_STATUS_CODES
        content_length = None
        chunked = False
        while True:
            header_line = read_line()
            if header_line == b"":
                break
            delimiter = header_line.find(b":")
            key = header_line[:delimiter].title()
            p = delimiter + 1
            while header_line[p] == SPACE:
                p += 1
            value = header_line[p:]
            headers[key] = value
            if key == b"Content-Length":
                try:
                    has_content = True
                    content_length = int(value)
                except (TypeError, ValueError):
                    pass
            elif key == b"Transfer-Encoding":
                if value == b"chunked":
                    has_content = True
                    chunked = True

        if not has_content:
            self._finish()

        self._has_content = has_content
        self._content_length = content_length
        self._chunked = chunked

        self._content = b""
        self._content_type = None
        self._encoding = None
        self._typed_content = None

        return self

    @property
    def readable(self):
        """ Boolean indicating whether response content is currently available to read.
        """
        return self._has_content

    def read(self):
        """ Read and return all available response content.
        """
        assert self.readable, "No content to read"

        recv = self._recv
        read = self._read
        read_line = self._read_line

        if self._chunked:
            # Read until empty chunk
            chunks = []
            chunk_size = -1
            while chunk_size != 0:
                chunk_size = int(read_line(), 16)
                if chunk_size != 0:
                    chunks.append(read(chunk_size))
                read(2)
            self._content = b"".join(chunks)

        elif self._content_length:
            # Read fixed length
            self._content = read(self._content_length)

        elif self._has_content:
            # read until connection closed
            chunks = []
            try:
                while True:
                    available = recv(DEFAULT_BUFFER_SIZE)
                    if available:
                        chunks.append(self._received)
                        self._received = b""
            except ConnectionError:
                self._content = b"".join(chunks)

        self._has_content = None
        self._content_length = None
        self._chunked = None

        self._finish()

        return self._content

    @property
    def headers(self):
        """ Headers from the last response.
        """
        return self._response_headers

    def _parse_content_type(self):
        try:
            content_type, params = parse_header(self._response_headers[b"Content-Type"])
        except KeyError:
            self._content_type = "application/octet-stream"
            self._encoding = "ISO-8859-1"
        else:
            self._content_type = content_type.decode("ISO-8859-1")
            self._encoding = params.get(b"charset", b"ISO-8859-1").decode("ISO-8859-1")

    @property
    def content_type(self):
        """ Content type of the last response.
        """
        if self._content_type is None:
            self._parse_content_type()
        return self._content_type

    @property
    def encoding(self):
        """ Character encoding for the last response.
        """
        if self._encoding is None:
            self._parse_content_type()
        return self._encoding

    @property
    def content(self):
        """ Full, typed content from the last response.
        """
        if self.readable:
            self.read()
        if self._typed_content is None:
            content_type = self.content_type
            if content_type == "text/html" and BeautifulSoup:
                self._typed_content = BeautifulSoup(self._content)
            elif content_type.startswith("text/"):
                self._typed_content = self._content.decode(self.encoding)
            elif content_type == "application/json":
                self._typed_content = json.loads(self._content.decode(self.encoding))
            else:
                self._typed_content = self._content
        return self._typed_content

    def _finish(self):
        if self.version == b"HTTP/1.0":
            connection = self._response_headers.get(b"Connection", b"close")
        else:
            connection = self._response_headers.get(b"Connection", b"keep-alive")
        if connection == b"close":
            self.close()


class Resource(object):

    def __init__(self, uri, **headers):
        parsed = urlparse(uri)
        if parsed.scheme == "http":
            self.http = HTTP(parsed.netloc, **headers)
            self.path = bstr(parsed.path)
        else:
            raise ValueError("Unsupported scheme '%s'" % parsed.scheme)

    def get(self, **headers):
        http = self.http
        try:
            return http.get(self.path, **headers).response().content
        except ConnectionError:
            http.reconnect()
            return http.get(self.path, **headers).response().content

    def put(self, content, **headers):
        http = self.http
        try:
            return http.put(self.path, content, **headers).response().content
        except ConnectionError:
            http.reconnect()
            return http.put(self.path, content, **headers).response().content

    def post(self, content, **headers):
        http = self.http
        try:
            return http.post(self.path, content, **headers).response().content
        except ConnectionError:
            http.reconnect()
            return http.post(self.path, content, **headers).response().content

    def delete(self, **headers):
        http = self.http
        try:
            return http.delete(self.path, **headers).response().content
        except ConnectionError:
            http.reconnect()
            return http.delete(self.path, **headers).response().content


def main2():
    script, opts, args = sys.argv[0], {}, []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            opts[arg] = None
        else:
            args.append(arg)
    url = args[0]
    parsed = urlparse(url)
    http = HTTP(parsed.hostname, parsed.port)
    if parsed.query:
        relative_url = "%s?%s" % (parsed.path, parsed.query)
    else:
        relative_url = parsed.path
    http.get(relative_url)
    print(http.response().read())


def main3():
    script, opts, args = sys.argv[0], {}, []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            opts[arg] = None
        else:
            args.append(arg)
    url = args[0].encode("ISO-8859-1")
    parsed = urlparse(url)
    http = HTTP(parsed.hostname, parsed.port)
    if parsed.query:
        relative_url = "%s?%s" % (parsed.path, parsed.query)
    else:
        relative_url = parsed.path
    http.get(relative_url)
    print(http.response().read().decode("ISO-8859-1"))


if __name__ == "__main__":
    if sys.version_info >= (3,):
        main3()
    else:
        main2()

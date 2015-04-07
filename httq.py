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


__author__ = "Nigel Small"
__copyright__ = "2015, Nigel Small"
__email__ = "nigel@nigelsmall.com"
__license__ = "Apache License, Version 2.0"
__version__ = "0.0.1"
__all__ = ["HTTP", "Resource", "get", "head", "put", "patch", "post", "delete", "ConnectionError"]


METHODS = {
    method.decode("UTF-8"): method
    for method in [b"OPTIONS", b"GET", b"HEAD", b"POST", b"PUT", b"DELETE", b"TRACE"]
}
HTTP_VERSIONS = {
    _version: _version.decode("UTF-8")
    for _version in [b"HTTP/0.9", b"HTTP/1.0", b"HTTP/1.1"]
}
REASONS = {
    _reason: _reason.decode("UTF-8") for _reason in [
        b'Continue',
        b'Switching Protocols',

        b'OK',
        b'Created',
        b'Accepted',
        b'Non-Authoritative Information',
        b'No Content',
        b'Reset Content',
        b'Partial Content',

        b'Multiple Choices',
        b'Moved Permanently',
        b'Found',
        b'See Other',
        b'Not Modified',
        b'Use Proxy',
        b'Temporary Redirect',

        b'Bad Request',
        b'Unauthorized',
        b'Payment Required',
        b'Forbidden',
        b'Not Found',
        b'Method Not Allowed',
        b'Not Acceptable',
        b'Proxy Authentication Required',
        b'Request Timeout',
        b'Conflict',
        b'Gone',
        b'Length Required',
        b'Precondition Failed',
        b'Request Entity Too Large',
        b'Request-URI Too Long',
        b'Unsupported Media Type',
        b'Requested Range Not Satisfiable',
        b'Expectation Failed',
        b'Precondition Required',
        b'Too Many Requests',
        b'Request Header Fields Too Large',

        b'Internal Server Error',
        b'Not Implemented',
        b'Bad Gateway',
        b'Service Unavailable',
        b'Gateway Timeout',
        b'HTTP Version Not Supported',
        b'Network Authentication Required',
    ]
}

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


def basic_auth(*args):
    return b"Basic " + b64encode(b":".join(map(bstr, args)))


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


def parse_uri(uri):
    scheme = authority = path = query = fragment = None

    if uri is not None:

        if not isinstance(uri, bytes):
            uri = bstr(uri)

        # Scheme
        q = uri.find(b":")
        if q == -1:
            start = 0
        else:
            scheme = uri[:q]
            start = q + 1
        end = len(uri)

        # Fragment
        q = uri.find(b"#", start)
        if q != -1:
            fragment = uri[(q + 1):]
            end = q

        # Query
        q = uri.find(b"?", start)
        if start <= q < end:
            query = uri[(q + 1):end]
            end = q

        # Authority and path
        p = start + 2
        if uri[start:p] == b"//":
            q = uri.find(b"/", p)
            if q == -1:
                authority = uri[p:end]
                path = b""
            else:
                authority = uri[p:q]
                path = uri[q:end]
        else:
            path = uri[start:end]

    return scheme, authority, path, query, fragment


def parse_uri_authority(authority):
    user_info = host = port = None

    if authority is not None:

        if not isinstance(authority, bytes):
            authority = bstr(authority)

        # User info
        p = authority.find(b"@")
        if p != -1:
            user_info = authority[:p]

        # Host and port
        p += 1
        q = authority.find(b":", p)
        if q == -1:
            host = authority[p:]
        else:
            host = authority[p:q]
            q += 1
            try:
                port = int(authority[q:])
            except ValueError:
                port = authority[q:]

    return user_info, host, port


class HTTP(object):
    """ Low-level HTTP client providing access to raw request and response functions.

    :param authority: URI authority to which to connect
    :param headers:
    """

    DEFAULT_PORT = 80

    _socket = None
    _send = None
    _recv = None
    _user_info = None
    _host = None
    _port = None
    _connection_headers = {}
    _received = b""

    _writable = False
    _requests = []

    _readable = False
    _version = None
    _status_code = None
    _reason = None
    _response_headers = {}
    _content_length = None
    _chunked = None
    _content = b""
    _content_type = None
    _encoding = None
    _typed_content = None

    def __init__(self, authority=None, **headers):
        if authority:
            self.connect(authority)
        if headers:
            self._add_connection_headers(**headers)

    def __del__(self):
        try:
            self.close()
        except socket.error:
            pass

    def __repr__(self):
        params = [b"HTTP"]
        try:
            host = self._connection_headers[b"Host"]
        except KeyError:
            pass
        else:
            params.append(host)
            for i, (method, url, _) in enumerate(self._requests):
                if i == 0 and self._readable:
                    params.append(b"(" + method + b" " + url + b")->(" + bstr(self.status_code) + b")")
                else:
                    params.append(b"(" + method + b" " + url + b")->()")
        if sys.version_info >= (3,):
            return "<%s>" % " ".join(param.decode("UTF-8") for param in params)
        else:
            return "<%s>" % " ".join(params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # finish reading or writing
        pass

    def _receive(self, n):
        s = self._socket
        recv = self._recv
        ready_to_read, _, _ = select((s,), (), (), 0)
        if ready_to_read:
            data = recv(n)
            data_length = len(data)
            if data_length == 0:
                raise ConnectionError("Peer has closed connection")
            self._received += data
            return data_length
        else:
            return 0

    def _read(self, n):
        receive = self._receive
        required = n - len(self._received)
        while required > 0:
            if required > DEFAULT_BUFFER_SIZE:
                required -= receive(required)
            elif required > 0:
                required -= receive(DEFAULT_BUFFER_SIZE)
        received = self._received
        data, self._received = received[:n], received[n:]
        return data

    def _read_line(self):
        receive = self._receive
        eol = self._received.find(b"\r\n")
        while eol == -1:
            while receive(DEFAULT_BUFFER_SIZE) == 0:
                pass
            eol = self._received.find(b"\r\n")
        received = self._received
        data, self._received = received[:eol], received[(eol + 2):]
        return data

    def _add_connection_headers(self, **headers):
        for name, value in headers.items():
            try:
                name = REQUEST_HEADERS[name]
            except KeyError:
                name = bstr(name).replace(b"_", b"-").title()
            if not isinstance(value, bytes):
                value = bstr(value)
            self._connection_headers[name] = value

    def _connect(self, host, port):
        self._socket = socket.create_connection((host, port or self.DEFAULT_PORT))
        self._send = self._socket.sendall
        self._recv = self._socket.recv
        self._received = b""
        del self._requests[:]

    def connect(self, authority, **headers):
        """ Establish a connection to a remote host.

        :param authority: the URI authority to which to connect
        :param headers: headers to pass into each request for this connection
        """
        user_info, host, port = parse_uri_authority(authority)

        # Reset connection attributes and headers
        connection_headers = self._connection_headers
        connection_headers.clear()
        if user_info:
            connection_headers[b"Authorization"] = basic_auth(user_info)
        if port:
            connection_headers[b"Host"] = host + b":" + bstr(port)
        else:
            connection_headers[b"Host"] = host

        if headers:
            self._add_connection_headers(**headers)

        self._connect(host, port)

        self._user_info = user_info
        self._host = host
        self._port = port

    def reconnect(self):
        """ Re-establish a connection to the same remote host.
        """
        if self._socket:
            self._socket.close()
            self._socket = None
        self._connect(self._host, self._port)

    def close(self):
        """ Close the current connection.
        """
        if self._socket:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self._socket = None
            self._send = None
            self._recv = None
        self._received = b""
        del self._requests[:]

        self._connection_headers.clear()

    @property
    def host(self):
        """ The remote host to which this client is connected.
        """
        return self._connection_headers[b"Host"]

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
        :param url: relative URL for this request
        :param body: the byte content to send with this request
                     or :const:`None` for separate, chunked data
        :param headers:
        """
        if self._writable:
            self.write(b"")

        if not isinstance(method, bytes):
            try:
                method = METHODS[method]
            except KeyError:
                method = bstr(method)

        if not isinstance(url, bytes):
            url = bstr(url)

        # Request line
        data = [method, b" ", url, b" HTTP/1.1\r\n"]

        # Common headers
        connection_headers = self._connection_headers
        request_headers = dict(connection_headers)
        for key, value in connection_headers.items():
            data += [key, b": ", value, b"\r\n"]

        # Other headers
        for name, value in headers.items():
            try:
                name = REQUEST_HEADERS[name]
            except KeyError:
                name = bstr(name).replace(b"_", b"-").title()
            if not isinstance(value, bytes):
                value = bstr(value)
            request_headers[name] = value
            data += [name, b": ", value, b"\r\n"]

        if body is None:
            # Chunked content
            request_headers[b"Transfer-Encoding"] = b"chunked"
            data.append(b"Transfer-Encoding: chunked\r\n\r\n")
            self._writable = True

        else:
            # Fixed-length content
            if isinstance(body, dict):
                request_headers[b"Content-Type"] = b"application/json"
                data += [b"Content-Type: application/json\r\n"]
                body = json.dumps(body, ensure_ascii=True, separators=",:").encode("UTF-8")
            elif not isinstance(body, bytes):
                body = bstr(body)
            content_length = len(body)
            if content_length == 0:
                data.append(b"\r\n")
            else:
                content_length_bytes = bstr(content_length)
                request_headers[b"Content-Length"] = content_length_bytes
                data += [b"Content-Length: ", content_length_bytes, b"\r\n\r\n", body]
            self._writable = False

        # Send
        try:
            self._send(b"".join(data))
        except socket.error:
            raise ConnectionError("Peer has closed connection")
        else:
            self._requests.append((method, url, request_headers))

        return self

    @property
    def request_method(self):
        """ The method used for the request behind the next response.
        """
        try:
            return self._requests[-1][0]
        except IndexError:
            return None

    @property
    def request_url(self):
        """ The URL used for the request behind the next response.
        """
        try:
            return self._requests[-1][1]
        except IndexError:
            return None

    @property
    def request_headers(self):
        """ The headers sent with the request behind the next response.
        """
        try:
            return self._requests[-1][2]
        except IndexError:
            return None

    def options(self, url=b"*", body=None, **headers):
        """ Make or initiate an OPTIONS request to the remote host.

        :param url:
        :param body:
        :param headers:
        """
        return self.request(b"OPTIONS", url, body, **headers)

    def get(self, url, **headers):
        """ Make a GET request to the remote host.

        :param url:
        :param headers:
        """
        return self.request(b"GET", url, b"", **headers)

    def head(self, url, **headers):
        """ Make a HEAD request to the remote host.

        :param url:
        :param headers:
        """
        return self.request(b"HEAD", url, b"", **headers)

    def post(self, url, body=None, **headers):
        """ Make or initiate a POST request to the remote host.

        :param url:
        :param body:
        :param headers:
        """
        return self.request(b"POST", url, body, **headers)

    def put(self, url, body=None, **headers):
        """ Make or initiate a PUT request to the remote host.

        :param url:
        :param body:
        :param headers:
        """
        return self.request(b"PUT", url, body, **headers)

    def patch(self, url, body=None, **headers):
        """ Make or initiate a PATCH request to the remote host.

        :param url:
        :param body:
        :param headers:
        """
        return self.request(b"PATCH", url, body, **headers)

    def delete(self, url, **headers):
        """ Make a DELETE request to the remote host.

        :param url:
        :param headers:
        """
        return self.request(b"DELETE", url, b"", **headers)

    def trace(self, url, body=None, **headers):
        """ Make or initiate a TRACE request to the remote host.

        :param url:
        :param body:
        :param headers:
        """
        return self.request(b"TRACE", url, body, **headers)

    def writable(self):
        """ Boolean flag indicating whether a chunked request is currently being written.
        """
        return self._writable

    def write(self, *chunks):
        """ Write one or more chunks of request data to the remote host.

        :param chunks:
        """
        assert self._writable, "No chunked request sent"

        data = []
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            chunk_length = len(chunk)
            data += [hexb(chunk_length), b"\r\n", chunk, b"\r\n"]
            if chunk_length == 0:
                self._writable = False
                break

        self._send(b"".join(data))

        return self

    def response(self):
        """ Read the status line and headers for the next response.

        :return: this HTTP instance
        """
        if not self._requests:
            raise IOError("No requests outstanding")

        if self._readable:
            self.readall()

        read_line = self._read_line
        headers = self._response_headers

        is_head_response = self.request_method == b"HEAD"

        status_line = read_line()

        # HTTP version
        p = status_line.find(b" ")
        self._version = status_line[:p]

        # Status code
        p += 1
        q = status_line.find(b" ", p)
        status_code = STATUS_CODES[status_line[p:q]]
        self._status_code = status_code

        # Reason phrase
        self._reason = status_line[(q + 1):]

        # Headers
        headers.clear()
        readable = status_code not in NO_CONTENT_STATUS_CODES
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
            if is_head_response:
                pass
            elif key == b"Content-Length":
                try:
                    content_length = int(value)
                except (TypeError, ValueError):
                    pass
                else:
                    if content_length == 0:
                        readable = False
            elif key == b"Transfer-Encoding":
                if value == b"chunked":
                    chunked = True

        self._content = b""
        self._content_type = None
        self._encoding = None
        self._typed_content = NotImplemented

        if is_head_response:
            self._readable = False
            self._typed_content = None
            finish = True

        elif readable:
            self._readable = True
            self._content_length = content_length
            self._chunked = chunked
            finish = False

        else:
            finish = True

        if finish:
            self._readable = False
            self._content_length = None
            self._chunked = None

            self._requests.pop(0)

            if self.version == "HTTP/1.0":
                connection = self._response_headers.get(b"Connection", b"close")
            else:
                connection = self._response_headers.get(b"Connection", b"keep-alive")

            if connection == b"close":
                self.close()

        return self

    def readable(self):
        """ Boolean indicating whether response content is currently available to read.
        """
        return self._readable

    def read(self, size=-1):
        # TODO
        raise NotImplementedError()

    def readall(self):
        """ Read and return all available response content.
        """
        if not self._readable:
            raise IOError("No content to read")

        recv = self._receive
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

        elif self._readable:
            # Read until connection closed
            chunks = []
            try:
                while True:
                    available = recv(DEFAULT_BUFFER_SIZE)
                    if available:
                        chunks.append(self._received)
                        self._received = b""
            except ConnectionError:
                self._content = b"".join(chunks)

        self._readable = False
        self._content_length = None
        self._chunked = None

        self._requests.pop(0)

        if self.version == "HTTP/1.0":
            connection = self._response_headers.get(b"Connection", b"close")
        else:
            connection = self._response_headers.get(b"Connection", b"keep-alive")

        if connection == b"close":
            self.close()

        return self._content

    def readinto(self, b):
        # TODO
        raise NotImplementedError()

    @property
    def version(self):
        """ HTTP version from the last response.
        """
        _version = self._version
        if isinstance(_version, bytes):
            try:
                _version = HTTP_VERSIONS[_version]
            except KeyError:
                _version = _version.decode("ISO-8859-1")
            finally:
                self._version = _version
        return _version

    @property
    def status_code(self):
        """ Status code from the last response.
        """
        return self._status_code

    @property
    def reason(self):
        """ Reason phrase from the last response.
        """
        _reason = self._reason
        if isinstance(_reason, bytes):
            try:
                _reason = REASONS[_reason]
            except KeyError:
                _reason = _reason.decode("ISO-8859-1")
            finally:
                self._reason = _reason
        return _reason

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
        """ Character encoding of the last response.
        """
        if self._encoding is None:
            self._parse_content_type()
        return self._encoding

    @property
    def content(self):
        """ Full, typed content from the last response.
        """
        if self._readable:
            self.readall()
        if self._typed_content is NotImplemented:
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

try:
    import ssl
except ImportError:
    pass
else:
    class HTTPS(HTTP):
        """ This class allows communication via SSL.
        """

        DEFAULT_PORT = 443

        _ssl_context = None

        def __init__(self, authority=None, **headers):
            self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            self._ssl_context.options |= ssl.OP_NO_SSLv2
            super(HTTPS, self).__init__(authority, **headers)

        def _connect(self, host, port):
            super(HTTPS, self)._connect(host, port)
            self._socket = self._ssl_context.wrap_socket(self._socket, server_hostname=host if ssl.HAS_SNI else None)

    __all__.insert(1, "HTTPS")


# TODO: follow redirects
# TODO: throw exceptions on 400/500
class Resource(object):

    def __init__(self, uri, **headers):
        if not isinstance(uri, bytes):
            uri = bstr(uri)
        parsed = urlparse(uri)
        if parsed.scheme == b"http":
            self.http = HTTP(parsed.netloc, **headers)
            self.path = bstr(parsed.path)  # TODO: include querystring
        elif parsed.scheme == b"https":
            self.http = HTTPS(parsed.netloc, **headers)
            self.path = bstr(parsed.path)  # TODO: include querystring
        else:
            raise ValueError("Unsupported scheme '%s'" % parsed.scheme)

    def get(self, **headers):
        http = self.http
        try:
            return http.get(self.path, **headers).response()
        except ConnectionError:
            http.reconnect()
            return http.get(self.path, **headers).response()

    def head(self, **headers):
        http = self.http
        try:
            return http.head(self.path, **headers).response()
        except ConnectionError:
            http.reconnect()
            return http.head(self.path, **headers).response()

    def put(self, content, **headers):
        http = self.http
        try:
            return http.put(self.path, content, **headers).response()
        except ConnectionError:
            http.reconnect()
            return http.put(self.path, content, **headers).response()

    def patch(self, content, **headers):
        http = self.http
        try:
            return http.patch(self.path, content, **headers).response()
        except ConnectionError:
            http.reconnect()
            return http.patch(self.path, content, **headers).response()

    def post(self, content, **headers):
        http = self.http
        try:
            return http.post(self.path, content, **headers).response()
        except ConnectionError:
            http.reconnect()
            return http.post(self.path, content, **headers).response()

    def delete(self, **headers):
        http = self.http
        try:
            return http.delete(self.path, **headers).response()
        except ConnectionError:
            http.reconnect()
            return http.delete(self.path, **headers).response()


def get(url, **headers):
    return Resource(url).get(**headers)


def head(url, **headers):
    return Resource(url).head(**headers)


def put(url, content, **headers):
    return Resource(url).put(content, **headers)


def patch(url, content, **headers):
    return Resource(url).patch(content, **headers)


def post(url, content, **headers):
    return Resource(url).post(content, **headers)


def delete(url, **headers):
    return Resource(url).delete(**headers)


class ConnectionError(IOError):

    def __init__(self, *args, **kwargs):
        super(ConnectionError, self).__init__(*args, **kwargs)


def main2():
    script, opts, args = sys.argv[0], {}, []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            opts[arg] = None
        else:
            args.append(arg)
    url = args[0]
    parsed = urlparse(url)
    http = HTTP(parsed.netloc)
    if parsed.query:
        relative_url = "%s?%s" % (parsed.path, parsed.query)
    else:
        relative_url = parsed.path
    http.get(relative_url)
    print(http.response().readall())


def main3():
    script, opts, args = sys.argv[0], {}, []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            opts[arg] = None
        else:
            args.append(arg)
    url = args[0].encode("ISO-8859-1")
    parsed = urlparse(url)
    http = HTTP(parsed.netloc)
    if parsed.query:
        relative_url = "%s?%s" % (parsed.path, parsed.query)
    else:
        relative_url = parsed.path
    http.get(relative_url)
    print(http.response().readall().decode("ISO-8859-1"))


def main():
    if sys.version_info >= (3,):
        main3()
    else:
        main2()


if __name__ == "__main__":
    main()

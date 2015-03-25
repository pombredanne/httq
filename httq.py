#!/usr/bin/env python
# -*- encoding: utf-8 -*-


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


DEFAULT_PORT = 80

METHODS = {m.decode("UTF-8"): m
           for m in [b"OPTIONS", b"GET", b"HEAD", b"POST", b"PUT", b"DELETE", b"TRACE"]}


def barr(s, encoding="ISO-8859-1"):
    if isinstance(s, bytes):
        return bytearray(s)
    elif isinstance(s, bytearray):
        return s
    elif isinstance(s, str):
        return bytearray(s, encoding=encoding)
    else:
        return bytearray(str(s), encoding=encoding)


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


def parse_header_value(value):
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


def header_case(s):
    b = barr(s)
    start_of_word = 0
    for i, ch in enumerate(b):
        if ch == 95:
            b[i] = 45
            start_of_word = i + 1
        elif i == start_of_word and 97 <= ch <= 122:
            b[i] -= 32
    return bstr(b)


class ConnectionError(IOError):

    def __init__(self, *args, **kwargs):
        super(ConnectionError, self).__init__(*args, **kwargs)


class HTTP(object):

    # Connection attributes
    connected = False
    socket = None

    # Request attributes
    request_headers = {}

    # Response attributes
    _received = b""
    version = None
    status_code = None
    reason_phrase = None
    _raw_response_headers = {}
    _parsed_response_headers = {}
    _parsed_response_header_params = {}
    readable = False
    writable = False

    def __init__(self, host, **headers):
        self.connect(host, **headers)

    def __del__(self):
        try:
            self.close()
        except socket.error:
            pass

    def _recv(self, n):
        s = self.socket
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
        required = n - len(self._received)
        while required > 0:
            if required > DEFAULT_BUFFER_SIZE:
                required -= self._recv(required)
            elif required > 0:
                required -= self._recv(DEFAULT_BUFFER_SIZE)
        received = self._received
        line, self._received = received[:n], received[n:]
        return line

    def _read_line(self):
        eol = self._received.find(b"\r\n")
        while eol == -1:
            p = len(self._received)
            self._recv(DEFAULT_BUFFER_SIZE)
            eol = self._received.find(b"\r\n", p)
        received = self._received
        line, self._received = received[:eol], received[(eol + 2):]
        return line

    def _add_parsed_header(self, name, value, params, converter=None):
        try:
            value = converter(value)
        except (TypeError, ValueError):
            pass
        self._parsed_response_headers[name] = value
        if params:
            self._parsed_response_header_params[name] = params
        return value

    def connect(self, host, **headers):
        """ Establish a connection to a remote host.
        """
        if not isinstance(host, bytes):
            host = bstr(host)

        # Reset connection attributes and headers
        self.request_headers.clear()
        self.request_headers[b"Host"] = host

        for name, value in headers.items():
            try:
                name = REQUEST_HEADERS[name]
            except KeyError:
                name = header_case(name)
            if not isinstance(value, bytes):
                value = bstr(value)
            self.request_headers[name] = value

        # Establish connection
        host, _, port = host.partition(b":")
        if port:
            port = int(port)
        else:
            port = DEFAULT_PORT

        self.socket = socket.create_connection((host, port))
        self._received = b""
        self.connected = True

    def reconnect(self):
        host = self.host
        headers = dict(self.request_headers)
        self.close()
        self.connect(host)
        self.request_headers.update(headers)

    def close(self):
        """ Close the current connection.
        """
        if self.socket:
            self.socket.close()
            self.socket = None
        self._received = b""
        self.connected = False

        self.request_headers.clear()

    @property
    def host(self):
        return self.request_headers[b"Host"]

    def request(self, method, url, body=None, **headers):
        """ Make or initiate a request to the remote host.

        :param method:
        :param url:
        :param body:
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
        for key, value in self.request_headers.items():
            data += [key, b": ", value, b"\r\n"]

        # Other headers
        for name, value in headers.items():
            try:
                name = REQUEST_HEADERS[name]
            except KeyError:
                name = header_case(name)
            if not isinstance(value, bytes):
                value = bstr(value)
            data += [name, b": ", value, b"\r\n"]

        if body is None:
            # Chunked content
            data.append(b"Transfer-Encoding: chunked\r\n\r\n")
            self.writable = True
        else:
            # Fixed-length content
            assert isinstance(body, bytes)
            content_length = len(body)
            if content_length == 0:
                data.append(b"\r\n")
            else:
                data += [b"Content-Length: ", bstr(content_length), b"\r\n\r\n", body]
            self.writable = False

        # Send
        try:
            joined = b"".join(data)
            self.socket.sendall(joined)
        except socket.error:
            raise ConnectionError("Peer has closed connection")

        return self

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
        self.socket.sendall(joined)

        return self

    def response(self):
        if self.readable:
            self.read()

        read_line = self._read_line
        raw_headers = self._raw_response_headers

        # Status line
        status_line = read_line()
        p = status_line.find(b" ")
        self.version = status_line[:p]
        p += 1
        q = status_line.find(b" ", p)
        status_code = STATUS_CODES[status_line[p:q]]  # faster than using the int function
        self.status_code = status_code
        self.reason_phrase = status_line[(q + 1):]

        # Headers
        readable = status_code != 204
        self._parsed_response_headers.clear()
        raw_headers.clear()
        while True:
            header_line = read_line()
            if header_line == b"":
                break
            delimiter = header_line.find(b":")
            key = header_line[:delimiter].lower()
            p = delimiter + 1
            while header_line[p] == SPACE:
                p += 1
            value = header_line[p:]
            raw_headers[key] = value
            if key == b"content-length":
                header, params = parse_header_value(value)
                readable = self._add_parsed_header(key, header, params, int)
            elif key == b"connection":
                header, params = parse_header_value(value)
                self._add_parsed_header(key, header, params)
            elif key == b"transfer-encoding":
                header, params = parse_header_value(value)
                self._add_parsed_header(key, header, params)
                chunked = header == b"chunked"
                if chunked:
                    readable = True

        if not readable:
            self.finish()

        self.readable = readable

        return self

    def read(self):
        assert self.readable, "No content available to read"

        # Try sized
        content_length = self.content_length
        read = self._read
        read_line = self._read_line
        if content_length == 0:
            content = b""
        elif content_length:
            content = read(content_length)
        else:
            # Assume chunked
            chunks = []
            chunk_size = -1
            while chunk_size != 0:
                chunk_size = int(read_line(), 16)
                chunks.append(read(chunk_size))
                read(2)
            content = b"".join(chunks)

        self.readable = None
        self.finish()

        return content

    def finish(self):
        if self.version == b"HTTP/1.0" or self.connection == b"close":
            self.close()

    def header(self, name):
        if not isinstance(name, bytes):
            name = bstr(name)
        name = name.lower()
        return self._raw_response_headers.get(name)

    def _parsed_header(self, name, converter=None):
        parsed_response_headers = self._parsed_response_headers
        if name not in parsed_response_headers:
            header, params = parse_header_value(self._raw_response_headers.get(name))
            self._add_parsed_header(name, header, params, converter)
        return parsed_response_headers.get(name)

    @property
    def charset(self):
        try:
            charset = self._parsed_response_header_params.get(b"content-type").get(b"charset")
        except KeyError:
            charset = None
        if charset:
            if isinstance(charset, str):
                return charset
            else:
                return charset.decode("ISO-8859-1")
        else:
            return "ISO-8859-1"

    @property
    def access_control_allow_origin(self):
        return self._parsed_header(b"access-control-allow-origin")

    @property
    def accept_patch(self):
        return self._parsed_header(b"accept-patch")

    @property
    def accept_ranges(self):
        return self._parsed_header(b"accept-ranges")

    @property
    def age(self):
        return self._parsed_header(b"age")

    @property
    def allow(self):
        return self._parsed_header(b"allow", lambda x: x.split(b","))

    @property
    def cache_control(self):
        return self._parsed_header(b"cache-control")

    @property
    def connection(self):
        return self._parsed_response_headers.get(b"connection")

    @property
    def content_disposition(self):
        return self._parsed_header(b"content-disposition")

    @property
    def content_encoding(self):
        return self._parsed_header(b"content-encoding")

    @property
    def content_language(self):
        return self._parsed_header(b"content-language")
    @property
    def content_length(self):
        return self._parsed_response_headers.get(b"content-length")

    @property
    def content_location(self):
        return self._parsed_header(b"content-location")
    @property
    def content_md5(self):
        return self._parsed_header(b"content-md5")

    @property
    def content_range(self):
        return self._parsed_header(b"content-range")

    @property
    def content_type(self):
        return self._parsed_header(b"content-type")

    @property
    def date(self):
        return self._parsed_header(b"date")

    @property
    def e_tag(self):
        return self._parsed_header(b"etag")

    @property
    def expires(self):
        return self._parsed_header(b"expires")

    @property
    def last_modified(self):
        return self._parsed_header(b"last-modified")

    @property
    def link(self):
        return self._parsed_header(b"link")

    @property
    def location(self):
        return self._parsed_header(b"location")

    @property
    def p3p(self):
        return self._parsed_header(b"p3p")

    @property
    def pragma(self):
        return self._parsed_header(b"pragma")

    @property
    def proxy_authenticate(self):
        return self._parsed_header(b"proxy_authenticate")

    @property
    def refresh(self):
        return self._parsed_header(b"refresh")

    @property
    def retry_after(self):
        return self._parsed_header(b"retry-after")

    @property
    def server(self):
        return self._parsed_header(b"server")

    @property
    def set_cookie(self):
        return self._parsed_header(b"set-cookie")

    @property
    def strict_transport_security(self):
        return self._parsed_header(b"strict-transport-security")

    @property
    def trailer(self):
        return self._parsed_header(b"trailer")

    @property
    def transfer_encoding(self):
        return self._parsed_response_headers.get(b"transfer-encoding")

    @property
    def upgrade(self):
        return self._parsed_header(b"upgrade")

    @property
    def vary(self):
        return self._parsed_header(b"vary")

    @property
    def via(self):
        return self._parsed_header(b"via")

    @property
    def warning(self):
        return self._parsed_header(b"warning")

    @property
    def www_authenticate(self):
        return self._parsed_header(b"www-authenticate")

    def options(self, url=b"*", body=None, **headers):
        """ Make or initiate an OPTIONS request to the remote host.

        :param url:
        :param headers:
        :param body:
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
        :param headers:
        :param body:
        """
        return self.request(b"POST", url, body, **headers)

    def put(self, url, body=None, **headers):
        """ Make or initiate a PUT request to the remote host.

        :param url:
        :param headers:
        :param body:
        """
        return self.request(b"PUT", url, body, **headers)

    def delete(self, url, **headers):
        """ Make a DELETE request to the remote host.

        :param url:
        :param headers:
        """
        return self.request(b"DELETE", url, b"", **headers)

    def trace(self, url, body=None, **headers):
        """ Make or initiate a TRACE request to the remote host.

        :param url:
        :param headers:
        :param body:
        """
        return self.request(b"TRACE", url, body, **headers)


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
            content_out = http.get(self.path, **headers).response().read()
        except ConnectionError:
            http.reconnect()
            content_out = http.get(self.path, **headers).response().read()
        if http.content_type == b"application/json":
            return json.loads(content_out.decode(http.charset))
        else:
            return content_out

    def put(self, content, **headers):
        http = self.http
        if isinstance(content, dict):
            headers.setdefault(b"Content-Type", b"application/json")
            content = json.dumps(content, ensure_ascii=True, separators=",:").encode("UTF-8")
        elif not isinstance(content, bytes):
            content = bstr(content, "UTF-8")
        try:
            content_out = http.put(self.path, content, **headers).response().read()
        except ConnectionError:
            http.reconnect()
            content_out = http.put(self.path, content, **headers).response().read()
        if http.content_type == b"application/json":
            return json.loads(content_out.decode(http.charset))
        else:
            return content_out

    def post(self, content, **headers):
        http = self.http
        if isinstance(content, dict):
            headers.setdefault(b"Content-Type", b"application/json")
            content = json.dumps(content, ensure_ascii=True, separators=",:").encode("UTF-8")
        elif not isinstance(content, bytes):
            content = bstr(content, "UTF-8")
        try:
            content_out = http.post(self.path, content, **headers).response().read()
        except ConnectionError:
            http.reconnect()
            content_out = http.post(self.path, content, **headers).response().read()
        if http.content_type == b"application/json":
            return json.loads(content_out.decode(http.charset))
        else:
            return content_out

    def delete(self, **headers):
        http = self.http
        try:
            content_out = http.delete(self.path, **headers).response().read()
        except ConnectionError:
            http.reconnect()
            content_out = http.delete(self.path, **headers).response().read()
        if http.content_type == b"application/json":
            return json.loads(content_out.decode(http.charset))
        else:
            return content_out


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

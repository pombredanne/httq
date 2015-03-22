#!/usr/bin/env python
# -*- encoding: utf-8 -*-


from base64 import b64encode
from io import DEFAULT_BUFFER_SIZE
from select import select
import socket
import sys
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


DEFAULT_PORT = 80

GET = b"GET"
PUT = b"PUT"
POST = b"POST"
DELETE = b"DELETE"


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

    def hex_to_bytes(n):
        return hex(n)[2:].encode("UTF-8")

    def int_to_bytes(n):
        return str(n).encode("UTF-8")

else:
    SPACE = b' '

    def bstr(s, encoding="ISO-8859-1"):
        if isinstance(s, bytes):
            return s
        elif isinstance(s, unicode):
            return s.encode(encoding)
        else:
            return bytes(s)

    def hex_to_bytes(n):
        return hex(n)[2:]

    int_to_bytes = bytes


def credentials_to_bytes(value):
    try:
        user_id, password = value
    except ValueError:
        raise ValueError("")
    else:
        return b"Basic " + b64encode(b":".join((bstr(user_id), bstr(password))))


REQUEST_HEADERS = {
    # argument: (header, transform function)
    "accept": (b"Accept", None),
    "accept_charset": (b"Accept-Charset", None),
    "accept_datetime": (b"Accept-Datetime", None),
    "accept_encoding": (b"Accept-Encoding", None),
    "accept_language": (b"Accept-Language", None),
    "authorization": (b"Authorization", credentials_to_bytes),
    "cache_control": (b"Cache-Control", None),
    "connection": (b"Connection", None),
    "content_length": (b"Content-Length", int_to_bytes),
    "content_md5": (b"Content-MD5", None),
    "content_type": (b"Content-Type", None),
    "cookie": (b"Cookie", None),
    "date": (b"Date", None),
    "expect": (b"Expect", None),
    "from": (b"From", None),
    "host": (b"Host", None),
    "if_match": (b"If-Match", None),
    "if_modified_since": (b"If-Modified-Since", None),
    "if_none_match": (b"If-None-Match", None),
    "if_range": (b"If-Range", None),
    "if_unmodified_since": (b"If-Unmodified-Since", None),
    "max_forwards": (b"Max-Forwards", int_to_bytes),
    "origin": (b"Origin", None),
    "pragma": (b"Pragma", None),
    "proxy_authorization": (b"Proxy-Authorization", credentials_to_bytes),
    "range": (b"Range", None),
    "referer": (b"Referer", None),
    "te": (b"TE", None),
    "user_agent": (b"User-Agent", None),
    "upgrade": (b"Upgrade", None),
    "via": (b"Via", None),
    "warning": (b"Warning", None),
}

STATUS_CODES = {bstr(code): code for code in range(100, 600)}


def log(line, colour):
    if __debug__:
        print("\x1b[3%sm%s\x1b[0m" % (colour, line.decode("ISO-8859-1")))


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

    def _parse_header(self, key, value, converter=None):
        if value is None:
            self._parsed_response_headers[key] = None
            return None
        p = 0
        delimiter = value.find(b";", p)
        eol = len(value)
        if p <= delimiter < eol:
            string_value = value[p:delimiter]
            params = {}
            while delimiter < eol:
                # Skip whitespace after previous delimiter
                p = delimiter + 1
                while value[p] == SPACE:
                    p += 1
                # Find next delimiter
                delimiter = value.find(b";", p)
                if delimiter == -1:
                    delimiter = eol
                # Add parameter
                eq = value.find(b"=", p)
                if p <= eq < delimiter:
                    params[value[p:eq]] = value[eq+1:delimiter]
                else:
                    params[value[p:delimiter]] = None
            if params:
                self._parsed_response_header_params[key] = params
        else:
            string_value = value[p:]
        try:
            parsed_value = converter(string_value)
        except (TypeError, ValueError):
            parsed_value = string_value
        self._parsed_response_headers[key] = parsed_value
        return parsed_value

    def connect(self, host, **headers):
        """ Establish a connection to a remote host.
        """
        if not isinstance(host, bytes):
            host = bstr(host)

        if __debug__:
            log(b"Connecting to " + host, 1)

        # Reset connection attributes and headers
        self.request_headers.clear()
        self.request_headers[b"Host"] = host

        for key, value in headers.items():
            try:
                header, to_bytes = REQUEST_HEADERS[key]
            except KeyError:
                raise ValueError("Unknown header %r" % key)
            else:
                if to_bytes:
                    value = to_bytes(value)
                elif not isinstance(value, bytes):
                    value = bstr(value)
                self.request_headers[header] = value

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
        headers = self.request_headers
        self.close()
        self.connect(host, **headers)

    def close(self):
        """ Close the current connection.
        """
        if __debug__:
            log(b"Closing connection", 1)

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
        assert isinstance(method, bytes), "Method must be a bytes object"
        assert isinstance(url, bytes), "URL must be a bytes object"

        if self.writable:
            self.write(b"")

        # Request line
        data = [method, b" ", url, b" HTTP/1.1\r\n"]

        # Common headers
        for key, value in self.request_headers.items():
            data += [key, b": ", value, b"\r\n"]

        # Other headers
        for key, value in headers.items():
            try:
                header, to_bytes = REQUEST_HEADERS[key]
            except KeyError:
                raise ValueError("Unknown header %r" % key)
            else:
                if to_bytes:
                    value = to_bytes(value)
                elif not isinstance(value, bytes):
                    value = bstr(value)
                data += [header, b": ", value, b"\r\n"]

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
                data += [b"Content-Length: ", int_to_bytes(content_length), b"\r\n\r\n", body]
            self.writable = False

        # Send
        try:
            joined = b"".join(data)
            self.socket.sendall(joined)
        except socket.error:
            raise ConnectionError("Peer has closed connection")
        else:
            if __debug__:
                for i, line in enumerate(b"".join(data)[:-2].split(b"\r\n")):
                    log(line, 6 if i == 0 else 4)

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
            data += [hex_to_bytes(chunk_length), b"\r\n", chunk, b"\r\n"]
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
        parse_header = self._parse_header
        raw_headers = self._raw_response_headers

        # Status line
        status_line = read_line()
        log(status_line, 6)
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
            log(header_line, 4)
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
                readable = parse_header(key, value, int)
            elif key == b"connection":
                parse_header(key, value)
            elif key == b"transfer-encoding":
                chunked = parse_header(key, value) == b"chunked"
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

    @property
    def access_control_allow_origin(self):
        parsed_response_headers = self._parsed_response_headers
        if b"access-control-allow-origin" not in parsed_response_headers:
            self._parse_header(b"access-control-allow-origin", self._raw_response_headers.get(b"access-control-allow-origin"))
        return parsed_response_headers.get(b"access-control-allow-origin")

    @property
    def accept_patch(self):
        parsed_response_headers = self._parsed_response_headers
        if b"accept-patch" not in parsed_response_headers:
            self._parse_header(b"accept-patch", self._raw_response_headers.get(b"accept-patch"))
        return parsed_response_headers.get(b"accept-patch")

    @property
    def accept_ranges(self):
        parsed_response_headers = self._parsed_response_headers
        if b"accept-ranges" not in parsed_response_headers:
            self._parse_header(b"accept-ranges", self._raw_response_headers.get(b"accept-ranges"))
        return parsed_response_headers.get(b"accept-ranges")

    @property
    def age(self):
        parsed_response_headers = self._parsed_response_headers
        if b"age" not in parsed_response_headers:
            self._parse_header(b"age", self._raw_response_headers.get(b"age"))
        return parsed_response_headers.get(b"age")

    @property
    def allow(self):
        parsed_response_headers = self._parsed_response_headers
        if b"allow" not in parsed_response_headers:
            self._parse_header(b"allow", self._raw_response_headers.get(b"allow"), lambda x: x.split(b","))
        return parsed_response_headers.get(b"allow")

    @property
    def cache_control(self):
        parsed_response_headers = self._parsed_response_headers
        if b"cache-control" not in parsed_response_headers:
            self._parse_header(b"cache-control", self._raw_response_headers.get(b"cache-control"))
        return parsed_response_headers.get(b"cache-control")

    @property
    def connection(self):
        return self._parsed_response_headers.get(b"connection")

    @property
    def content_disposition(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-disposition" not in parsed_response_headers:
            self._parse_header(b"content-disposition", self._raw_response_headers.get(b"content-disposition"))
        return parsed_response_headers.get(b"content-disposition")

    @property
    def content_encoding(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-encoding" not in parsed_response_headers:
            self._parse_header(b"content-encoding", self._raw_response_headers.get(b"content-encoding"))
        return parsed_response_headers.get(b"content-encoding")

    @property
    def content_language(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-language" not in parsed_response_headers:
            self._parse_header(b"content-language", self._raw_response_headers.get(b"content-language"))
        return parsed_response_headers.get(b"content-language")

    @property
    def content_length(self):
        return self._parsed_response_headers.get(b"content-length")

    @property
    def content_location(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-location" not in parsed_response_headers:
            self._parse_header(b"content-location", self._raw_response_headers.get(b"content-location"))
        return parsed_response_headers.get(b"content-location")

    @property
    def content_md5(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-md5" not in parsed_response_headers:
            self._parse_header(b"content-md5", self._raw_response_headers.get(b"content-md5"))
        return parsed_response_headers.get(b"content-md5")

    @property
    def content_range(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-range" not in parsed_response_headers:
            self._parse_header(b"content-range", self._raw_response_headers.get(b"content-range"))
        return parsed_response_headers.get(b"content-range")

    @property
    def content_type(self):
        parsed_response_headers = self._parsed_response_headers
        if b"content-type" not in parsed_response_headers:
            self._parse_header(b"content-type", self._raw_response_headers.get(b"content-type"))
        return parsed_response_headers.get(b"content-type")

    @property
    def date(self):
        parsed_response_headers = self._parsed_response_headers
        if b"date" not in parsed_response_headers:
            self._parse_header(b"date", self._raw_response_headers.get(b"date"))
        return parsed_response_headers.get(b"date")

    @property
    def e_tag(self):
        parsed_response_headers = self._parsed_response_headers
        if b"etag" not in parsed_response_headers:
            self._parse_header(b"etag", self._raw_response_headers.get(b"etag"))
        return parsed_response_headers.get(b"etag")

    @property
    def expires(self):
        parsed_response_headers = self._parsed_response_headers
        if b"expires" not in parsed_response_headers:
            self._parse_header(b"expires", self._raw_response_headers.get(b"expires"))
        return parsed_response_headers.get(b"expires")

    @property
    def last_modified(self):
        parsed_response_headers = self._parsed_response_headers
        if b"last-modified" not in parsed_response_headers:
            self._parse_header(b"last-modified", self._raw_response_headers.get(b"last-modified"))
        return parsed_response_headers.get(b"last-modified")

    @property
    def link(self):
        parsed_response_headers = self._parsed_response_headers
        if b"link" not in parsed_response_headers:
            self._parse_header(b"link", self._raw_response_headers.get(b"link"))
        return parsed_response_headers.get(b"link")

    @property
    def location(self):
        parsed_response_headers = self._parsed_response_headers
        if b"location" not in parsed_response_headers:
            self._parse_header(b"location", self._raw_response_headers.get(b"location"))
        return parsed_response_headers.get(b"location")

    @property
    def p3p(self):
        parsed_response_headers = self._parsed_response_headers
        if b"p3p" not in parsed_response_headers:
            self._parse_header(b"p3p", self._raw_response_headers.get(b"p3p"))
        return parsed_response_headers.get(b"p3p")

    @property
    def pragma(self):
        parsed_response_headers = self._parsed_response_headers
        if b"pragma" not in parsed_response_headers:
            self._parse_header(b"pragma", self._raw_response_headers.get(b"pragma"))
        return parsed_response_headers.get(b"pragma")

    @property
    def proxy_authenticate(self):
        parsed_response_headers = self._parsed_response_headers
        if b"proxy-authenticate" not in parsed_response_headers:
            self._parse_header(b"proxy-authenticate", self._raw_response_headers.get(b"proxy-authenticate"))
        return parsed_response_headers.get(b"proxy-authenticate")

    @property
    def refresh(self):
        parsed_response_headers = self._parsed_response_headers
        if b"refresh" not in parsed_response_headers:
            self._parse_header(b"refresh", self._raw_response_headers.get(b"refresh"))
        return parsed_response_headers.get(b"refresh")

    @property
    def retry_after(self):
        parsed_response_headers = self._parsed_response_headers
        if b"retry-after" not in parsed_response_headers:
            self._parse_header(b"retry-after", self._raw_response_headers.get(b"retry-after"))
        return parsed_response_headers.get(b"retry-after")

    @property
    def server(self):
        parsed_response_headers = self._parsed_response_headers
        if b"server" not in parsed_response_headers:
            self._parse_header(b"server", self._raw_response_headers.get(b"server"))
        return parsed_response_headers.get(b"server")

    @property
    def set_cookie(self):
        parsed_response_headers = self._parsed_response_headers
        if b"set-cookie" not in parsed_response_headers:
            self._parse_header(b"set-cookie", self._raw_response_headers.get(b"set-cookie"))
        return parsed_response_headers.get(b"set-cookie")

    @property
    def strict_transport_security(self):
        parsed_response_headers = self._parsed_response_headers
        if b"strict-transport-security" not in parsed_response_headers:
            self._parse_header(b"strict-transport-security", self._raw_response_headers.get(b"strict-transport-security"))
        return parsed_response_headers.get(b"strict-transport-security")

    @property
    def trailer(self):
        parsed_response_headers = self._parsed_response_headers
        if b"trailer" not in parsed_response_headers:
            self._parse_header(b"trailer", self._raw_response_headers.get(b"trailer"))
        return parsed_response_headers.get(b"trailer")

    @property
    def transfer_encoding(self):
        return self._parsed_response_headers.get(b"transfer-encoding")

    @property
    def upgrade(self):
        parsed_response_headers = self._parsed_response_headers
        if b"upgrade" not in parsed_response_headers:
            self._parse_header(b"upgrade", self._raw_response_headers.get(b"upgrade"))
        return parsed_response_headers.get(b"upgrade")

    @property
    def vary(self):
        parsed_response_headers = self._parsed_response_headers
        if b"vary" not in parsed_response_headers:
            self._parse_header(b"vary", self._raw_response_headers.get(b"vary"))
        return parsed_response_headers.get(b"vary")

    @property
    def via(self):
        parsed_response_headers = self._parsed_response_headers
        if b"via" not in parsed_response_headers:
            self._parse_header(b"via", self._raw_response_headers.get(b"via"))
        return parsed_response_headers.get(b"via")

    @property
    def warning(self):
        parsed_response_headers = self._parsed_response_headers
        if b"warning" not in parsed_response_headers:
            self._parse_header(b"warning", self._raw_response_headers.get(b"warning"))
        return parsed_response_headers.get(b"warning")

    @property
    def www_authenticate(self):
        parsed_response_headers = self._parsed_response_headers
        if b"www-authenticate" not in parsed_response_headers:
            self._parse_header(b"www-authenticate", self._raw_response_headers.get(b"www-authenticate"))
        return parsed_response_headers.get(b"www-authenticate")

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

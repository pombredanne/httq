#!/usr/bin/env python
# -*- encoding: utf-8 -*-


from io import DEFAULT_BUFFER_SIZE
from select import select
import socket
import sys


DEFAULT_PORT = 80

GET = b"GET"
PUT = b"PUT"
POST = b"POST"
DELETE = b"DELETE"

HEADERS = {
    "content_type": b"Content-Type",
}

HEXEN = [b"0", b"1", b"2", b"3", b"4", b"5", b"6", b"7", b"8", b"9", b"A", b"B", b"C", b"D", b"E", b"F"]


if sys.version_info >= (3,):
    SP_CHAR = ord(' ')

    def hexb(n):
        if n < 0x10:
            return HEXEN[n]
        else:
            return hex(40000)[2:].encode("ASCII")

    def int_to_bytes(n):
        if n < 10:
            return HEXEN[n]
        else:
            return str(n).encode("ASCII")

else:
    SP_CHAR = b' '

    def hexb(n):
        return hex(n)[2:]

    int_to_bytes = bytes


def log(line, colour):
    if __debug__ and line:
        print("\x1b[3%sm%s\x1b[0m" % (colour, line.decode("ISO-8859-1")))


class ConnectionError(IOError):

    def __init__(self, *args, **kwargs):
        super(ConnectionError, self).__init__(*args, **kwargs)


class HTTP(object):

    # Connection attributes
    socket = None
    host = None
    port = None
    host_port = None
    _received = b""

    # Response attributes
    status_code = None
    reason_phrase = None
    _raw_headers = {}
    _parsed_headers = {}
    _parsed_header_params = {}
    readable = False
    writable = False

    def __init__(self, host=None, port=DEFAULT_PORT):
        if host is not None:
            self.connect(host, port)

    def _recv(self, n):
        s = self.socket
        ready_to_read, _, _ = select((s,), (), (), 0)
        if ready_to_read:
            data = s.recv(n)
            if data:
                self._received += data
            else:
                raise ConnectionError("Peer has closed connection")

    def _read(self, n):
        if n > len(self._received):
            while True:
                required = n - len(self._received)
                if required > DEFAULT_BUFFER_SIZE:
                    self._recv(required)
                elif required > 0:
                    self._recv(DEFAULT_BUFFER_SIZE)
                else:
                    break
        line, self._received = self._received[:n], self._received[n:]
        return line

    def _read_line(self):
        while True:
            try:
                eol = self._received.index(b"\r\n")
            except ValueError:
                self._recv(DEFAULT_BUFFER_SIZE)
            else:
                line, self._received = self._received[:eol], self._received[(eol + 2):]
                return line

    def _parse_header(self, key, value, converter=None):
        if value is None:
            self._parsed_headers[key] = None
        p = 0
        delimiter = value.find(b";", p)
        eol = len(value)
        if p <= delimiter < eol:
            string_value = value[p:delimiter]
            params = {}
            while delimiter < eol:
                # Skip whitespace after previous delimiter
                p = delimiter + 1
                while value[p] == SP_CHAR:
                    p += 1
                # Find next delimiter
                try:
                    delimiter = value.index(b";", p)
                except ValueError:
                    delimiter = eol
                # Add parameter
                eq = value.find(b"=", p)
                if p <= eq < delimiter:
                    params[value[p:eq]] = value[eq+1:delimiter]
                else:
                    params[value[p:delimiter]] = None
            if params:
                self._parsed_header_params[key] = params
        else:
            string_value = value[p:]
        try:
            parsed_value = converter(string_value)
        except (TypeError, ValueError):
            parsed_value = string_value
        self._parsed_headers[key] = parsed_value
        return parsed_value

    def connect(self, host, port=DEFAULT_PORT):
        """ Establish a connection to a remote host.

        :param host: the host to connect to
        :param port: the port on which to connect (defaults to DEFAULT_PORT)
        """
        assert isinstance(host, bytes), "Host name must be a bytes object"

        # Reset connection attributes
        self.host = host
        self.port = port
        self.host_port = host if port == DEFAULT_PORT else host + b":" + int_to_bytes(port)

        # Establish connection
        self.socket = socket.create_connection((self.host, self.port))
        self._received = b""

    def close(self):
        """ Close the current connection.
        """
        self.socket.close()
        self.socket = None

    def request(self, method, uri, body=None, **headers):
        """ Make or initiate a request to the remote host.

        :param method:
        :param uri:
        :param headers:
        :param body:
        """
        assert isinstance(method, bytes), "Method must be a bytes object"
        assert isinstance(uri, bytes), "URI must be a bytes object"

        # Request and Host header
        data = [method, b" ", uri, b" HTTP/1.1\r\nHost: ", self.host_port, b"\r\n"]

        if self.writable:
            self.write(b"")

        # Other headers
        for key, value in headers.items():
            assert isinstance(value, bytes)
            try:
                data += [HEADERS[key], b": ", value, b"\r\n"]
            except KeyError:
                raise ValueError("Unknown header %r" % key)

        # Content-Length & body or Transfer-Encoding
        if body is None:
            data += [b"Transfer-Encoding: chunked\r\n\r\n"]
            self.writable = True
        else:
            assert isinstance(body, bytes)
            content_length = len(body)
            if content_length == 0:
                data += [b"\r\n"]
            else:
                data += [b"Content-Length: ", int_to_bytes(content_length), b"\r\n\r\n", body]
            self.writable = False

        # Send
        if __debug__:
            for i, line in enumerate(b"".join(data).rstrip().split(b"\r\n")):
                log(line, 6 if i == 0 else 4)
        self.socket.sendall(b"".join(data))

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
        self.socket.sendall(b"".join(data))

    def response(self):
        if self.readable:
            self.read()

        # Status line
        status_line = self._read_line()
        log(status_line, 6)
        p = status_line.index(b" ") + 1
        q = status_line.index(b" ", p)
        status_code = int(status_line[p:q])
        self.status_code = status_code
        self.reason_phrase = status_line[(q + 1):]

        # Headers
        self.readable = status_code != 204
        self._parsed_headers.clear()
        raw_headers = self._raw_headers
        raw_headers.clear()
        while True:
            header_line = self._read_line()
            log(header_line, 4)
            if header_line == b"":
                break
            delimiter = header_line.index(b":")
            key = header_line[:delimiter].lower()
            p = delimiter + 1
            while header_line[p] == SP_CHAR:
                p += 1
            value = header_line[p:]
            raw_headers[key] = value
            if key == b"content-length":
                self.readable = self._parse_header(key, value, int)
            elif key == b"connection":
                self._parse_header(key, value)  # TODO: handle connection:close
            elif key == b"transfer-encoding":
                chunked = self._parse_header(key, value) == b"chunked"
                if chunked:
                    self.readable = True

        return self.status_code

    @property
    def allow(self):
        if b"allow" not in self._parsed_headers:
            self._parse_header(b"allow", self._raw_headers.get(b"allow"), lambda x: x.split(b","))
        return self._parsed_headers.get(b"allow")

    @property
    def connection(self):
        return self._parsed_headers.get(b"connection")

    @property
    def content_length(self):
        return self._parsed_headers.get(b"content-length")

    @property
    def content_type(self):
        if b"content-type" not in self._parsed_headers:
            self._parse_header(b"content-type", self._raw_headers.get(b"content-type"))
        return self._parsed_headers.get(b"content-type")

    @property
    def server(self):
        if b"server" not in self._parsed_headers:
            self._parse_header(b"server", self._raw_headers.get(b"server"))
        return self._parsed_headers.get(b"server")

    @property
    def transfer_encoding(self):
        return self._parsed_headers.get(b"transfer-encoding")

    @property
    def www_authenticate(self):
        if b"www-authenticate" not in self._parsed_headers:
            self._parse_header(b"www-authenticate", self._raw_headers.get(b"www-authenticate"))
        return self._parsed_headers.get(b"www-authenticate")

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
                chunks += [read(chunk_size)]
                read(2)
            content = b"".join(chunks)

        self.readable = None
        return content

    def options(self, uri=b"*", body=None, **headers):
        """ Make or initiate an OPTIONS request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"OPTIONS", uri, body, **headers)

    def get(self, uri, **headers):
        """ Make a GET request to the remote host.

        :param uri:
        :param headers:
        """
        self.request(b"GET", uri, b"", **headers)

    def head(self, uri, **headers):
        """ Make a HEAD request to the remote host.

        :param uri:
        :param headers:
        """
        self.request(b"HEAD", uri, b"", **headers)

    def post(self, uri, body=None, **headers):
        """ Make or initiate a POST request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"POST", uri, body, **headers)

    def put(self, uri, body=None, **headers):
        """ Make or initiate a PUT request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"PUT", uri, body, **headers)

    def delete(self, uri, **headers):
        """ Make a DELETE request to the remote host.

        :param uri:
        :param headers:
        """
        self.request(b"DELETE", uri, b"", **headers)

    def trace(self, uri, body=None, **headers):
        """ Make or initiate a TRACE request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"TRACE", uri, body, **headers)

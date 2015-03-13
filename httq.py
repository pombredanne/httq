#!/usr/bin/env python
# -*- encoding: utf-8 -*-


from io import DEFAULT_BUFFER_SIZE
import socket
import sys


DEFAULT_PORT = 80

GET = b"GET"
PUT = b"PUT"
POST = b"POST"
DELETE = b"DELETE"

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


class HTTP(object):

    # Connection attributes
    host = None
    port = None
    host_port = None

    # Response attributes
    status_code = None
    reason_phrase = None
    _raw_headers = {}
    _parsed_headers = {}
    _parsed_header_params = {}

    def __init__(self, host=None, port=DEFAULT_PORT):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._received = b""
        if host is not None:
            self.connect(host, port)

    def _read(self, n):
        s = self.socket
        while len(self._received) < n:
            self._received += s.recv(DEFAULT_BUFFER_SIZE)
        line, self._received = self._received[:n], self._received[n:]
        return line

    def _read_line(self):
        s = self.socket
        while True:
            try:
                eol = self._received.index(b"\r\n")
            except ValueError:
                self._received += s.recv(DEFAULT_BUFFER_SIZE)
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
            self._parsed_headers[key] = converter(string_value)
        except (TypeError, ValueError):
            self._parsed_headers[key] = string_value

    def connect(self, host, port=DEFAULT_PORT):
        """ Establish a connection to a remote host.

        :param host: the host to connect to
        :param port: the port on which to connect (defaults to DEFAULT_PORT)
        """
        assert isinstance(host, bytes)
        self.socket.connect((host, port))
        self._received = b""

        # Reset connection attributes
        self.host = host
        self.port = port
        self.host_port = host + b":" + int_to_bytes(port)

    def close(self):
        """ Close the current connection.
        """
        self.socket.close()

    @property
    def closed(self):
        """ Indicates whether the connection is closed.
        """
        return self.socket._closed

    def request(self, method, uri, headers=None, body=None):
        """ Make or initiate a request to the remote host.

        :param method:
        :param uri:
        :param headers:
        :param body:
        """
        assert isinstance(method, bytes)
        assert isinstance(uri, bytes)

        # Request and Host header
        bits = [method, b" ", uri, b" HTTP/1.1\r\nHost: ", self.host_port, b"\r\n"]

        # Other headers
        if headers:
            for key, value in headers.items():
                assert isinstance(key, bytes)
                assert isinstance(value, bytes)
                bits += [key, b": ", value, b"\r\n"]

        # Content-Length & body or Transfer-Encoding
        if body is None:
            bits += [b"Transfer-Encoding: chunked\r\n\r\n"]
        else:
            assert isinstance(body, bytes)
            bits += [b"Content-Length: ", int_to_bytes(len(body)), b"\r\n\r\n", body]

        # Send
        self.socket.sendall(b"".join(bits))

    def options(self, uri=b"*", headers=None, body=None):
        """ Make or initiate an OPTIONS request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"OPTIONS", uri, headers, body)

    def get(self, uri, headers=None):
        """ Make a GET request to the remote host.

        :param uri:
        :param headers:
        """
        self.request(b"GET", uri, headers, b"")

    def head(self, uri, headers=None):
        """ Make a HEAD request to the remote host.

        :param uri:
        :param headers:
        """
        self.request(b"HEAD", uri, headers, b"")

    def post(self, uri, headers=None, body=None):
        """ Make or initiate a POST request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"POST", uri, headers, body)

    def put(self, uri, headers=None, body=None):
        """ Make or initiate a PUT request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"PUT", uri, headers, body)

    def delete(self, uri, headers=None):
        """ Make a DELETE request to the remote host.

        :param uri:
        :param headers:
        """
        self.request(b"DELETE", uri, headers, b"")

    def trace(self, uri, headers=None, body=None):
        """ Make or initiate a TRACE request to the remote host.

        :param uri:
        :param headers:
        :param body:
        """
        self.request(b"TRACE", uri, headers, body)

    def write(self, *chunks):
        """ Write one or more chunks of request data to teh remote host.

        :param chunks:
        """
        bits = []
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            bits += [hexb(len(chunk)), b"\r\n", chunk, b"\r\n"]
        self.socket.sendall(b"".join(bits))

    def response(self):
        # Status line
        status_line = self._read_line()
        p = status_line.index(b" ") + 1
        q = status_line.index(b" ", p)
        self.status_code = int(status_line[p:q])
        self.reason_phrase = status_line[(q + 1):]

        # Headers
        self._parsed_headers.clear()
        raw_headers = self._raw_headers
        raw_headers.clear()
        while True:
            line = self._read_line()
            if line == b"":
                break
            delimiter = line.index(b":")
            key = line[:delimiter].lower()
            p = delimiter + 1
            while line[p] == SP_CHAR:
                p += 1
            value = line[p:]
            raw_headers[key] = value
            if key == b"content-length":
                self._parse_header(key, value, int)
            elif key == b"transfer-encoding":
                self._parse_header(key, value)

        return self.status_code

    @property
    def allow(self):
        if b"allow" not in self._parsed_headers:
            self._parse_header(b"allow", self._raw_headers.get(b"allow"), lambda x: x.split(b","))
        return self._parsed_headers.get(b"allow")

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

    def read(self):
        # Try sized
        content_length = self.content_length
        if content_length == 0:
            return b""
        if content_length:
            return self._read(content_length)

        # Assume chunked
        chunks = []
        chunk_size = -1
        while chunk_size != 0:
            chunk_size = int(self._read_line(), 16)
            chunks.append(self._read(chunk_size))
            self._read(2)
        return b"".join(chunks)

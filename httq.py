#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import socket
import sys

CR = b"\r"
LF = b"\n"
EOL = CR + LF
SP = b" "
COLON = b":"
SEMICOLON = b";"
EQUALS = b"="

DEFAULT_PORT = 80

GET = b"GET"
PUT = b"PUT"
POST = b"POST"
DELETE = b"DELETE"

HTTP_1_1 = b"HTTP/1.1"

HEXEN = [b"0", b"1", b"2", b"3", b"4", b"5", b"6", b"7", b"8", b"9", b"A", b"B", b"C", b"D", b"E", b"F"]


if sys.version_info >= (3,):
    SP_CHAR = ord(' ')

else:
    SP_CHAR = b' '


def hexb(n):
    if n == 0:
        return b"0"
    else:
        digits = []
        while n > 0:
            n, digit = divmod(n, 0x10)
            digits.insert(0, HEXEN[digit])
        return b"".join(digits)


class HTTP(object):

    # Connection attributes
    host = None
    port = None
    _host_header = b""

    # Response attributes
    status_code = None
    reason_phrase = None
    _raw_headers = []
    _parsed_headers = {}
    _parsed_header_params = {}

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.file = self.socket.makefile("rwb")
        self._transfer_encoding_header = b"Transfer-Encoding: chunked" + EOL

    @property
    def closed(self):
        return self.socket._closed

    def connect(self, host, port=DEFAULT_PORT):
        assert isinstance(host, bytes)
        self.socket.connect((host, port))
        # Reset connection attributes
        self.host = host
        self.port = port
        self._host_header = b"Host: " + host + EOL

    def close(self):
        self.file.close()
        self.socket.close()

    def request(self, method, url, headers, *chunks):
        assert isinstance(method, bytes)
        assert isinstance(url, bytes)
        f = self.file
        lines = [method, SP, url, SP, HTTP_1_1, EOL, self._host_header, self._transfer_encoding_header]
        for key, value in headers.items():
            assert isinstance(key, bytes)
            assert isinstance(value, bytes)
            lines += [key, COLON, SP, value, EOL]
        lines += [EOL]
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            lines += [hexb(len(chunk)), EOL, chunk, EOL]
        f.writelines(lines)
        f.flush()

    def write(self, *chunks):
        f = self.file
        lines = []
        for chunk in chunks:
            assert isinstance(chunk, bytes)
            lines += [hexb(len(chunk)), EOL, chunk, EOL]
        f.writelines(lines)
        f.flush()

    def _parse_header(self, line, converter=None):
        # Find key
        delimiter = line.index(COLON)
        key = line[:delimiter].lower()
        # Find start of value
        p = delimiter + 1
        while line[p] == SP_CHAR:
            p += 1
        # Find end of value
        delimiter = line.find(SEMICOLON, p)
        eol = line.index(EOL, p)
        #
        if p <= delimiter < eol:
            string_value = line[p:delimiter]
            params = {}
            while delimiter < eol:
                # Skip whitespace after previous delimiter
                p = delimiter + 1
                while line[p] == SP_CHAR:
                    p += 1
                # Find next delimiter
                try:
                    delimiter = line.index(SEMICOLON, p)
                except ValueError:
                    delimiter = eol
                # Add parameter
                eq = line.find(EQUALS, p)
                if p <= eq < delimiter:
                    params[line[p:eq]] = line[eq+1:delimiter]
                else:
                    params[line[p:delimiter]] = None
            if params:
                self._parsed_header_params[key] = params
        #
        else:
            string_value = line[p:eol]
        # Record the main value, converting if requested
        try:
            self._parsed_headers[key] = converter(string_value)
        except (TypeError, ValueError):
            self._parsed_headers[key] = string_value

    def response(self):
        f = self.file

        # Status line
        status_line = f.readline()
        p = status_line.index(SP) + 1
        q = status_line.index(SP, p)
        self.status_code = int(status_line[p:q])
        p = q + 1
        q = status_line.index(EOL, p)
        self.reason_phrase = status_line[p:q]

        # Headers
        self._parsed_headers.clear()
        raw_headers = self._raw_headers
        del raw_headers[:]
        while True:
            line = f.readline()
            if line == EOL:
                break
            elif line.startswith(b"Content-Length:") or line.startswith(b"content-length:"):
                self._parse_header(line, int)
            elif line.startswith(b"Transfer-Encoding:") or line.startswith(b"transfer-encoding:"):
                self._parse_header(line)
            raw_headers.append(line)

        return self.status_code

    @property
    def content_length(self):
        return self._parsed_headers.get(b"content-length")

    @property
    def content_type(self):
        if b"content-type" not in self._parsed_headers:
            for line in self._raw_headers:
                if line.startswith(b"Content-Type:") or line.startswith(b"content-type:"):
                    self._parse_header(line)
        return self._parsed_headers.get(b"content-type")

    def read(self):
        f = self.file

        # Try sized
        content_length = self.content_length
        if content_length:
            return f.read(content_length)

        # Assume chunked
        chunks = []
        chunk_size = -1
        while chunk_size != 0:
            chunk_size = int(f.readline(), 16)
            chunks.append(f.read(chunk_size))
            f.read(2)
        return b"".join(chunks)

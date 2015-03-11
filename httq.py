#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import socket
import sys


DEFAULT_PORT = 80
CR = b"\r"
LF = b"\n"
EOL = CR + LF
GET = b"GET"
SP = b" "
HTTP_1_1 = b"HTTP/1.1"
HOST = b"Host"
COLON = b":"


if sys.version_info >= (3,):
    SP_CHAR = ord(' ')

else:
    SP_CHAR = b' '


class HTTP(object):

    # Connection attributes
    host = None
    port = None
    host_header = b""

    # Response attributes
    status_code = None
    reason_phrase = None
    _raw_headers = []
    _parsed_headers = {}

    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.file = self.socket.makefile("rwb")

    @property
    def closed(self):
        return self.socket._closed

    def connect(self, host, port=DEFAULT_PORT):
        assert isinstance(host, bytes)
        self.socket.connect((host, port))
        # Reset connection attributes
        self.host = host
        self.port = port
        self.host_header = b"Host: " + host + EOL

    def close(self):
        self.file.close()
        self.socket.close()

    def get(self, url):
        assert isinstance(url, bytes)
        f = self.file
        f.writelines([GET, SP, url, SP, HTTP_1_1, EOL, self.host_header, EOL])
        f.flush()

    def _parse_header(self, line, value_parser=None):
        p = line.index(COLON)
        key = line[:p].lower()
        p += 1
        while line[p] == SP_CHAR:
            p += 1
        q = line.index(CR, p)
        try:
            self._parsed_headers[key] = value_parser(line[p:q])
        except (TypeError, ValueError):
            self._parsed_headers[key] = line[p:q]

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

    def content(self):
        return self.file.read(self.content_length)


def test():
    http = HTTP()
    http.connect(b"localhost", 7474)
    http.get(b"/db/data/")
    for i in range(1):
        if http.response() in (200, 404):
            print(http.status_code)
            print(http.reason_phrase)
            print(http.content_length)
            print(http.content_type)
            print(http._raw_headers)
            print(http._parsed_headers)
            content = http.content()
            print(content)
            print()
    http.close()


if __name__ == "__main__":
    test()

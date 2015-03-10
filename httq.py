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
    DIGIT_0 = ord('0')
    DIGIT_9 = ord('9')
else:
    DIGIT_0 = b'0'
    DIGIT_9 = b'9'


def spliterate(s, sep=b" ", max_split=-1):
    p = 0
    try:
        while max_split != 0:
            q = s.index(sep, p)
            yield s[p:q]
            p = q + 1
            if max_split > 0:
                max_split -= 1
    except ValueError:
        pass
    finally:
        try:
            eol = s.index(EOL, p)
        except ValueError:
            yield s[p:]
        else:
            yield s[p:eol]


class HTTP(object):

    # Connection attributes
    host = None
    port = None
    host_header = b""

    # Response attributes
    status_code = None
    reason_phrase = None
    headers = []
    content_length = None
    _content_type = None

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

    def response(self):
        f = self.file

        # Status line
        status_line = f.readline()
        p = status_line.index(b" ") + 1
        q = status_line.index(b" ", p)
        self.status_code = int(status_line[p:q])
        p = q + 1
        q = status_line.index(EOL, p)
        self.reason_phrase = status_line[p:q]

        # Headers
        headers = self.headers
        del headers[:]
        self.content_length = None
        self._content_type = None
        while True:
            line = f.readline()
            if line == EOL:
                break
            elif line.startswith(b"Content-Length:") or line.startswith(b"content-length:"):
                content_length = line[15:].strip()
                if DIGIT_0 <= content_length[0] <= DIGIT_9:
                    self.content_length = int(content_length)
                else:
                    self.content_length = content_length
            headers.append(line)

        return self.status_code

    @property
    def content_type(self):
        if self._content_type is None:
            for line in self.headers:
                if line.startswith(b"Content-Type:") or line.startswith(b"content-type:"):
                    self._content_type = line[13:].strip()
        return self._content_type

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
            content = http.content()
            print(content)
            print()
    http.close()


if __name__ == "__main__":
    test()

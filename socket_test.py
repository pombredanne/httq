
from socket import SHUT_RDWR
from unittest import main, TestCase


from httq import HTTPSocket


class SendTestCase(TestCase):

    def test_can_send_request(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send_x(b"GET /hello HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Content-Length:'):
                assert header == b'Content-Length: 12'
        chunks = list(s.recv_content(12))
        assert chunks == [b'hello, world']
        s.shutdown(SHUT_RDWR)
        s.close()


class SizedContentTestCase(TestCase):

    def test_can_retrieve_sized_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /hello HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Content-Length:'):
                assert header == b'Content-Length: 12'
        chunks = list(s.recv_content(12))
        assert chunks == [b'hello, world']
        s.shutdown(SHUT_RDWR)
        s.close()

    def test_can_retrieve_empty_sized_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /empty HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Content-Length:'):
                assert header == b'Content-Length: 0'
        chunks = list(s.recv_content(0))
        assert chunks == []
        s.shutdown(SHUT_RDWR)
        s.close()

    def test_can_retrieve_slow_sized_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /slow HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Content-Length:'):
                assert header == b'Content-Length: 18'
        chunks = list(s.recv_content(18))
        assert chunks == [b'line\r\n', b'line\r\n', b'line\r\n']
        s.shutdown(SHUT_RDWR)
        s.close()


class UnsizedContentTestCase(TestCase):

    def test_can_retrieve_unsized_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /hello HTTP/1.1\r\nHost: httq.io:8080\r\nUser-Agent: OldBrowser/1.0\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'HTTP/'):
                assert header.startswith(b'HTTP/1.0')
        chunks = list(s.recv_content())
        assert chunks == [b'hello, world']
        s.shutdown(SHUT_RDWR)
        s.close()

    def test_can_retrieve_empty_unsized_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /empty HTTP/1.1\r\nHost: httq.io:8080\r\nUser-Agent: OldBrowser/1.0\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'HTTP/'):
                assert header.startswith(b'HTTP/1.0')
        chunks = list(s.recv_content())
        assert chunks == []
        s.shutdown(SHUT_RDWR)
        s.close()

    def test_can_retrieve_slow_unsized_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /slow HTTP/1.1\r\nHost: httq.io:8080\r\nUser-Agent: OldBrowser/1.0\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'HTTP/'):
                assert header.startswith(b'HTTP/1.0')
        chunks = list(s.recv_content())
        assert chunks == [b'line\r\n', b'line\r\n', b'line\r\n']
        s.shutdown(SHUT_RDWR)
        s.close()


class ChunkedContentTestCase(TestCase):

    def test_can_retrieve_chunked_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /chunks HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Transfer-Encoding'):
                assert header == b"Transfer-Encoding: chunked"
        chunks = list(s.recv_chunked_content())
        assert chunks == [b'chunk 1\r\n', b'chunk 2\r\n', b'chunk 3\r\n']
        s.shutdown(SHUT_RDWR)
        s.close()

    def test_can_retrieve_empty_chunked_content(self):
        s = HTTPSocket()
        s.connect(("httq.io", 8080))
        s.send(b"GET /chunks?0 HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Transfer-Encoding'):
                assert header == b"Transfer-Encoding: chunked"
        chunks = list(s.recv_chunked_content())
        assert chunks == []
        s.shutdown(SHUT_RDWR)
        s.close()


if __name__ == "__main__":
    main()

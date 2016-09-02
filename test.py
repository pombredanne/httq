
from socket import SHUT_RDWR
from unittest import TestCase, main
import sys

from httq import bstr, parse_uri, HTTPSocket, HTTP, HTTPS


class HelperTestCase(TestCase):

    def test_can_bstr_bytes(self):
        b = b"hello, world"
        assert bstr(b) is b

    def test_can_bstr_bytearray(self):
        b = bytearray(b"hello, world")
        assert bstr(b) == b"hello, world"

    def test_can_bstr_text(self):
        b = b"hello, world".decode("UTF-8")
        assert bstr(b) == b"hello, world"

    def test_can_bstr_number(self):
        b = 42
        assert bstr(b) == b"42"


class URITestCase(TestCase):

    def test_can_correctly_parse_uris(self):
        uri_list = [
            (b"foo://bob@somewhere@example.com:8042/over/there?name=ferret#nose",
             (b"foo", b"bob@somewhere@example.com:8042", b"/over/there", b"name=ferret", b"nose")),
            (b"foo://bob@somewhere@example.com:8042/over/there?name=ferret",
             (b"foo", b"bob@somewhere@example.com:8042", b"/over/there", b"name=ferret", None)),
            (b"foo://bob@somewhere@example.com:8042/over/there",
             (b"foo", b"bob@somewhere@example.com:8042", b"/over/there", None, None)),
            (b"foo://bob@somewhere@example.com:8042/over/there#nose",
             (b"foo", b"bob@somewhere@example.com:8042", b"/over/there", None, b"nose")),
            (b"foo://bob@somewhere@example.com:8042",
             (b"foo", b"bob@somewhere@example.com:8042", b"", None, None)),
            (b"//bob@somewhere@example.com:8042",
             (None, b"bob@somewhere@example.com:8042", b"", None, None)),
            (b"//bob@somewhere@example.com:8042/over/there",
             (None, b"bob@somewhere@example.com:8042", b"/over/there", None, None)),
            (None,
             (None, None, None, None, None)),
            (b"?name=ferret",
             (None, None, b"", b"name=ferret", None)),
            (b"#nose",
             (None, None, b"", None, b"nose")),
        ]
        for uri, parts in uri_list:
            assert parse_uri(uri) == parts


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
        s.send(b"GET /dots HTTP/1.1\r\nHost: httq.io:8080\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'Content-Length:'):
                assert header == b'Content-Length: 3'
        chunks = list(s.recv_content(3))
        assert chunks == [b'.', b'.', b'.']
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
        s.send(b"GET /dots HTTP/1.1\r\nHost: httq.io:8080\r\nUser-Agent: OldBrowser/1.0\r\n\r\n")
        for header in s.recv_headers():
            if header.startswith(b'HTTP/'):
                assert header.startswith(b'HTTP/1.0')
        chunks = list(s.recv_content())
        assert chunks == [b'.', b'.', b'.']
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


class ConnectTestCase(TestCase):

    def test_can_establish_http_connection_without_port(self):
        http = HTTP(b"httq.io")
        assert http.host == b"httq.io"
        http.close()

    def test_can_establish_http_connection_with_port(self):
        http = HTTP(b"httq.io:8080")
        assert http.host == b"httq.io:8080"
        http.close()

    def test_can_establish_https_connection_without_port(self):
        http = HTTPS(b"eu.httpbin.org")
        assert http.host == b"eu.httpbin.org"
        http.close()

    def test_can_establish_https_connection_with_port(self):
        http = HTTPS(b"eu.httpbin.org:443")
        assert http.host == b"eu.httpbin.org:443"
        http.close()

    def test_can_reconnect(self):
        http = HTTP(b"httq.io:8080")
        assert http.host == b"httq.io:8080"
        http.reconnect()
        assert http.host == b"httq.io:8080"
        http.close()


class RequestDetailTestCase(TestCase):

    def test_request_method(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello")
        http.response()
        assert http.request_method == b"GET"
        http.close()

    def test_request_url(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello")
        http.response()
        assert http.request_url == b"/hello"
        http.close()

    def test_request_headers(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello")
        http.response()
        assert http.request_headers == {b"Host": b"httq.io:8080"}
        http.close()

    def test_request_method_with_no_request(self):
        http = HTTP(b"httq.io:8080")
        assert http.request_method is None
        http.close()

    def test_request_url_with_no_request(self):
        http = HTTP(b"httq.io:8080")
        assert http.request_url is None
        http.close()

    def test_request_headers_with_no_request(self):
        http = HTTP(b"httq.io:8080")
        assert http.request_headers == {b"Host": b"httq.io:8080"}
        http.close()


class HeadMethodTestCase(TestCase):

    def test_can_use_head_method_long_hand(self):
        http = HTTP(b"httq.io:8080")
        http.head(b"/hello")
        http.response()
        assert http.status_code == 200
        assert http.reason == "OK"
        assert http.content_type == "text/plain"
        assert not http.readable()
        assert http.content is None
        http.close()


class GetMethodTestCase(TestCase):

    def test_can_use_get_method_long_hand(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello")
        http.response()
        assert http.readable()
        assert http.status_code == 200
        assert http.reason == "OK"
        assert http.content_type == "text/plain"
        assert http.readable()
        assert http.content == "hello, world"
        assert not http.readable()
        http.close()

    def test_can_use_get_method_short_hand(self):
        assert HTTP(b"httq.io:8080").get(b"/hello").response().content == "hello, world"

    def test_can_use_get_method_with_unicode_args(self):
        if sys.version_info >= (3,):
            host = "httq.io:8080"
            path = "/hello"
        else:
            host = "httq.io:8080".decode("utf-8")
            path = "/hello".decode("utf-8")
        http = HTTP(host)
        http.get(path).response()
        assert http.status_code == 200
        assert http.reason == "OK"
        assert http.content_type == "text/plain"
        assert http.readable()
        assert http.content == "hello, world"
        assert not http.readable()
        http.close()

    def test_can_pipeline_multiple_get_requests(self):
        count = 3
        turns = range(1, count + 1)
        http = HTTP(b"httq.io:8080")
        for i in turns:
            http.get("/echo?%d" % i)
            assert len(http._requests) == i
        for i in reversed(turns):
            assert len(http._requests) == i
            assert http.response().status_code == 200
            http.readall()
        assert len(http._requests) == 0
        http.close()

    def test_can_read_in_bits(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello").response()
        assert http.readable()
        assert http.status_code == 200
        assert http.reason == "OK"
        assert http.content_type == "text/plain"
        assert http.readable()
        assert http.read(5) == b"hello"
        assert http.readable()
        assert http.read(5) == b", wor"
        assert http.readable()
        assert http.read(5) == b"ld"
        assert not http.readable()
        assert http.read(5) == b""
        assert http.content == "hello, world"
        http.close()

    def test_can_read_some_then_all_the_rest(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello").response()
        assert http.readable()
        assert http.status_code == 200
        assert http.reason == "OK"
        assert http.content_type == "text/plain"
        assert http.readable()
        assert http.read(5) == b"hello"
        assert http.readable()
        assert http.readall() == b", world"
        assert not http.readable()
        assert http.read(5) == b""
        assert http.content == "hello, world"
        http.close()

    def test_can_read_some_then_all_the_rest_through_content(self):
        http = HTTP(b"httq.io:8080")
        http.get(b"/hello").response()
        assert http.readable()
        assert http.status_code == 200
        assert http.reason == "OK"
        assert http.content_type == "text/plain"
        assert http.readable()
        assert http.read(5) == b"hello"
        assert http.readable()
        assert http.content == "hello, world"
        assert not http.readable()
        assert http.read(5) == b""
        http.close()

    def test_can_get_http_1_0_for_all_requests(self):
        assert HTTP(b"httq.io:8080", user_agent=b"OldBrowser/1.0").get(b"/hello").response().content == "hello, world"

    def test_can_get_http_1_0_for_one_request(self):
        assert HTTP(b"httq.io:8080").get(b"/hello", user_agent=b"OldBrowser/1.0").response().content == "hello, world"

    def test_can_get_chunks(self):
        assert HTTP(b"httq.io:8080").get(b"/chunks").response().content == "chunk 1\r\nchunk 2\r\nchunk 3\r\n"

    def test_can_get_unusual_status(self):
        http = HTTP(b"httq.io:8080")
        response = http.get(b"/status?299+Unexpected+Foo").response()
        assert response.status_code == 299
        assert response.reason == 'Unexpected Foo'


class JSONTestCase(TestCase):

    def test_can_get_json(self):
        http = HTTP(b"httq.io:8080")
        response = http.get(b"/json?foo=bar").response()
        content = response.content
        assert content == {"method": "GET", "query": "foo=bar", "content": ""}

    def test_can_post_json(self):
        http = HTTP(b"httq.io:8080")
        response = http.post(b"/json?foo=bar", b"bumblebee").response()
        content = response.content
        assert content == {"method": "POST", "query": "foo=bar", "content": "bumblebee"}

    def test_can_put_json(self):
        http = HTTP(b"httq.io:8080")
        response = http.put(b"/json?foo=bar", b"bumblebee").response()
        content = response.content
        assert content == {"method": "PUT", "query": "foo=bar", "content": "bumblebee"}

    def test_can_delete_json(self):
        http = HTTP(b"httq.io:8080")
        response = http.delete(b"/json?foo=bar").response()
        content = response.content
        assert content == {"method": "DELETE", "query": "foo=bar", "content": ""}

    def test_can_post_json_in_chunks(self):
        http = HTTP(b"httq.io:8080")
        http.post(b"/json?foo=bar")
        http.write(b"bum")
        http.write(b"ble")
        http.write(b"bee")
        http.write(b"")
        response = http.response()
        content = response.content
        assert content == {"method": "POST", "query": "foo=bar", "content": "bumblebee"}

    def test_can_post_dict_as_json(self):
        http = HTTP(b"httq.io:8080")
        response = http.post(b"/json?foo=bar", {"bee": "bumble"}).response()
        content = response.content
        assert content == {"method": "POST", "query": "foo=bar", "content": '{"bee": "bumble"}'}


if __name__ == "__main__":
    main()

# Copyright 2022 Akamai Technologies, Inc
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

from __future__ import annotations

from typing import Any

import pytest
from helpers import build_request_headers, build_response_headers

from urllib3_ext_hface import HeadersType
from urllib3_ext_hface.events import ConnectionTerminated, DataReceived, HeadersReceived
from urllib3_ext_hface.protocols import HTTPOverTCPProtocol, HTTP1ClientFactory


@pytest.fixture(name="client")
def _client(request: Any) -> HTTPOverTCPProtocol:
    factory = HTTP1ClientFactory()
    return factory(tls_version="TLS 1.2")


def assert_connection_available(protocol: HTTPOverTCPProtocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert protocol.is_available()
    assert not protocol.has_expired()


def assert_connection_active(protocol: HTTPOverTCPProtocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert not protocol.is_available()
    assert not protocol.has_expired()


def assert_connection_expired(protocol: HTTPOverTCPProtocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert not protocol.is_available()
    assert protocol.has_expired()


class TestClient:
    def test_connection_made(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test that no preface is sent for HTTP/1
        """
        assert_connection_available(client)

    def test_connection_lost(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection lost without EOF before the first request.
        """
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_eof_received(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection closed with EOF before the first request.
        """
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)
        client.connection_lost()
        assert_connection_expired(client)

    def test_send_get(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a GET request.
        """
        headers = build_request_headers()
        stream_id = client.get_available_stream_id()
        assert stream_id == 1
        client.submit_headers(stream_id, headers, end_stream=True)
        assert client.bytes_to_send() == b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"
        assert client.bytes_to_send() == b""
        assert_connection_active(client)

    def test_send_post(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        assert client.bytes_to_send() == (
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
        )
        client.bytes_to_send()
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == b"Hello HTTP!"
        assert_connection_active(client)

    def test_send_post_at_once(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request when headers are sent with data.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == (
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
            b"Hello HTTP!"
        )
        assert_connection_active(client)

    def test_send_post_in_parts(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request when data are not provided at once.
        """
        headers = build_request_headers((b"content-length", b"11"), method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        client.bytes_to_send()
        client.submit_data(stream_id, b"H")
        client.submit_data(stream_id, b"el")
        client.submit_data(stream_id, b"lo HTTP!")
        assert client.bytes_to_send() == b"Hello HTTP!"
        assert_connection_active(client)

    def test_send_post_wo_content_length(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request uses transfer-encoding if content-length is not given.
        """
        headers = build_request_headers(method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        assert client.bytes_to_send() == (
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"\r\n"
        )
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == b"b\r\nHello HTTP!\r\n0\r\n\r\n"
        assert_connection_active(client)

    @classmethod
    def _send_request(
        cls,
        client: HTTPOverTCPProtocol,
        headers: HeadersType | None = None,
        end_stream: bool = True,
    ) -> int:
        if headers is None:
            headers = build_request_headers()
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers, end_stream=end_stream)
        client.bytes_to_send()
        return stream_id

    @pytest.mark.parametrize(
        "payload,error_code",
        [
            pytest.param(b"\r\n\r\n", 400, id="empty"),
            pytest.param(b"\r\nContent-Length: 11\r\n\r\n", 400, id="status_empty"),
            pytest.param(
                b"XXX\r\nContent-Length: 11\r\n\r\n", 400, id="status_invalid"
            ),
            pytest.param(b"X" * 100_000, 431, id="status_too_long"),
        ],
    )
    def test_recv_invalid(
        self, client: HTTPOverTCPProtocol, payload: bytes, error_code: int
    ) -> None:
        """
        Test that invalid response causes an error.
        """
        self._send_request(client)
        client.bytes_received(payload)
        assert client.next_event() == ConnectionTerminated(error_code)
        assert_connection_expired(client)

    def test_recv(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(
            b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello HTTP!"
        )
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() == DataReceived(
            stream_id, b"Hello HTTP!", end_stream=True
        )
        assert_connection_available(client)

    def test_recv_fragmented(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response in multiple fragments.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(b"HTTP/1.1 200 OK\r\nContent-Len")
        assert client.next_event() is None
        client.bytes_received(b"gth: 11\r\n\r\nHello ")
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() == DataReceived(
            stream_id, b"Hello ", end_stream=False
        )
        assert client.next_event() is None
        client.bytes_received(b"HTTP!")
        assert client.next_event() == DataReceived(stream_id, b"HTTP!", end_stream=True)
        assert_connection_available(client)

    def test_recv_response_to_head_request(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response to a HEAD request.

        Response to HEAD has never body so headers should end the stream,
        even if Content-Length header is present.
        """
        request_headers = build_request_headers(method=b"HEAD")
        stream_id = self._send_request(client, request_headers)
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n")
        assert client.next_event() == HeadersReceived(
            stream_id, expected_headers, end_stream=True
        )
        assert_connection_available(client)

    def test_recv_transfer_encoding_chunked(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response with transfer-encoding instead of content-length.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers((b"transfer-encoding", b"chunked"))
        client.bytes_received(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() is None
        client.bytes_received(b"6\r\nHello \r\n")
        assert client.next_event() == DataReceived(
            stream_id, b"Hello ", end_stream=False
        )
        assert client.next_event() is None
        client.bytes_received(b"5\r\nHTTP!\r\n0\r\n\r\n")
        assert client.next_event() == DataReceived(stream_id, b"HTTP!", end_stream=True)
        assert_connection_available(client)

    def test_recv_http_10(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response without content-length or transfer-encoding.
        """
        stream_id = self._send_request(client)
        expected_headers = build_response_headers()
        client.bytes_received(b"HTTP/1.0 200 OK\r\n\r\n")
        assert client.next_event() == HeadersReceived(stream_id, expected_headers)
        assert client.next_event() is None
        client.bytes_received(b"Hello ")
        assert client.next_event() == DataReceived(
            stream_id, b"Hello ", end_stream=False
        )
        assert client.next_event() is None
        client.bytes_received(b"HTTP!")
        assert client.next_event() == DataReceived(
            stream_id, b"HTTP!", end_stream=False
        )
        assert client.next_event() is None
        client.eof_received()
        assert client.next_event() == DataReceived(stream_id, b"", end_stream=True)
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_recv_connection_close(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response without content-length or transfer-encoding.
        """
        self._send_request(client)
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 11\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"Hello HTTP!"
        )
        client.bytes_received(response)
        assert isinstance(client.next_event(), HeadersReceived)
        assert isinstance(client.next_event(), DataReceived)
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"HTTP/1.1 200 OK\r\n", id="partial-headers"),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n", id="headers"
            ),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello ",
                id="partial-body",
            ),
            pytest.param(b"HTTP/1.0 200 OK\r\n", id="http10-partial-headers"),
            pytest.param(b"HTTP/1.0 200 OK\r\n\r\n", id="http10-headers"),
            pytest.param(b"HTTP/1.0 200 OK\r\n\r\nHello ", id="http10-partial-body"),
        ],
    )
    def test_connection_lost_during_response(
        self, client: HTTPOverTCPProtocol, payload: bytes
    ) -> None:
        """
        Test connection lost without EOF when receiving a response.
        """
        self._send_request(client)
        client.bytes_received(payload)
        client.connection_lost()
        event = client.next_event()
        while isinstance(event, (HeadersReceived, DataReceived)):
            event = client.next_event()
        assert event == ConnectionTerminated()
        assert_connection_expired(client)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"HTTP/1.1 200 OK\r\n", id="partial-headers"),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n", id="headers"
            ),
            pytest.param(
                b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello ",
                id="partial-body",
            ),
            pytest.param(b"HTTP/1.0 200 OK\r\n", id="http10-partial-headers"),
        ],
    )
    def test_eof_received_during_response(
        self, client: HTTPOverTCPProtocol, payload: bytes
    ) -> None:
        """
        Test connection closed with EOF when receiving a response.
        """
        self._send_request(client)
        client.bytes_received(payload)
        client.eof_received()
        event = client.next_event()
        while isinstance(event, (HeadersReceived, DataReceived)):
            event = client.next_event()
        assert event == ConnectionTerminated(400)
        assert_connection_expired(client)

    def test_stream_reset(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test that stream reset for HTTP/1 is translated to connection reset.
        """
        self._send_request(client)
        client.bytes_received(b"HTTP/1.1 200 OK\r\n")
        client.submit_stream_reset(1)
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    @classmethod
    def _recv_response(
        cls, client: HTTPOverTCPProtocol, response: bytes | None = None
    ) -> None:
        if response is None:
            response = b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello HTTP!"
        client.bytes_received(response)
        event = client.next_event()
        assert isinstance(event, HeadersReceived)
        while event is not None:
            event = client.next_event()

    def test_connection_lost_after_response(self, client: HTTPOverTCPProtocol) -> None:
        self._send_request(client)
        self._recv_response(client)
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_eof_received_after_response(self, client: HTTPOverTCPProtocol) -> None:
        self._recv_response(client)
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_multiple_requests(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test multiple requests.

        HTTP/1 supports serial requests only.
        """
        assert self._send_request(client) == 1
        expected_headers = build_response_headers((b"content-length", b"11"))
        client.bytes_received(
            b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nHello HTTP!"
        )
        assert client.next_event() == HeadersReceived(1, expected_headers)
        assert client.next_event() == DataReceived(1, b"Hello HTTP!", end_stream=True)
        assert client.next_event() is None

        assert self._send_request(client) == 2
        expected_headers = build_response_headers((b"content-length", b"12"))
        client.bytes_received(
            b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\nHello again!"
        )
        assert client.next_event() == HeadersReceived(2, expected_headers)
        assert client.next_event() == DataReceived(2, b"Hello again!", end_stream=True)
        assert_connection_available(client)

    _connect_request_headers = [
        (b":method", b"CONNECT"),
        (b":authority", b"example.com:443"),
    ]

    def test_http_connect(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test CONNECT request and response.
        """
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert client.bytes_to_send() == (
            # fmt: off
            b"CONNECT example.com:443 HTTP/1.1\r\n"
            b"Host: example.com:443\r\n"
            b"\r\n"
        )
        client.bytes_received(b"HTTP/1.1 200 OK\r\n\r\n")
        assert client.next_event() == HeadersReceived(stream_id, [(b":status", b"200")])
        assert_connection_active(client)

    def test_http_connect_trailing_data(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test data sent with a response to a CONNECT request.
        """
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert client.bytes_to_send()
        client.bytes_received(b"HTTP/1.1 200 OK\r\n\r\nHello")
        assert isinstance(client.next_event(), HeadersReceived)
        assert client.next_event() == DataReceived(stream_id, b"Hello")
        assert_connection_active(client)

    def _http_connect(self, client: HTTPOverTCPProtocol) -> int:
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert client.bytes_to_send()
        client.bytes_received(b"HTTP/1.1 200 OK\r\n\r\n")
        assert isinstance(client.next_event(), HeadersReceived)
        assert client.next_event() is None
        return stream_id

    def test_http_connect_data(self, client: HTTPOverTCPProtocol) -> None:
        """
        Data can be exchanged after a CONNECT request.
        """
        stream_id = self._http_connect(client)
        client.submit_data(stream_id, b"Ping")
        assert client.bytes_to_send() == b"Ping"
        client.bytes_received(b"Pong")
        assert client.next_event() == DataReceived(stream_id, b"Pong")
        assert_connection_active(client)

    def test_http_connect_client_end_stream(self, client: HTTPOverTCPProtocol) -> None:
        stream_id = self._http_connect(client)
        client.submit_data(stream_id, b"Bye", end_stream=True)
        assert client.bytes_to_send() == b"Bye"
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_http_connect_eof_received(self, client: HTTPOverTCPProtocol) -> None:
        self._http_connect(client)
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_http_connect_connection_lost(self, client: HTTPOverTCPProtocol) -> None:
        self._http_connect(client)
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

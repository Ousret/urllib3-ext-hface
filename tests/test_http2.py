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

from typing import Any, cast

import hpack
import pytest
from helpers import build_request_headers, build_response_headers

from urllib3_ext_hface import HeadersType, HeaderType
from urllib3_ext_hface.events import (
    ConnectionTerminated,
    DataReceived,
    HeadersReceived,
    StreamResetSent,
)
from urllib3_ext_hface.protocols import HTTPOverTCPProtocol, HTTP2ClientFactory

CLIENT_MAGIC = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"


class Frame:
    DATA = 0x00
    HEADERS = 0x01
    RST_STREAM = 0x03
    SETTINGS = 0x04
    GOAWAY = 0x07


def build_frame(
    type: int,
    data: bytes = b"",
    *,
    flags: int = 0,
    stream_id: int = 0,
) -> bytes:
    parts = [
        len(data).to_bytes(byteorder="big", length=3),
        type.to_bytes(byteorder="big", length=1),
        flags.to_bytes(byteorder="big", length=1),
        stream_id.to_bytes(byteorder="big", length=4),
        data,
    ]
    return b"".join(parts)


def build_headers_frame(
    headers: list[HeaderType],
    *,
    end_stream: bool = False,
    stream_id: int = 1,
    encoder: hpack.Encoder | None = None,
) -> bytes:
    if encoder is None:
        encoder = hpack.Encoder()
    data = encoder.encode(headers)
    flags = 5 if end_stream else 4
    return build_frame(Frame.HEADERS, data, flags=flags, stream_id=stream_id)


def build_data_frame(
    data: bytes,
    stream_id: int = 1,
    end_stream: bool = True,
) -> bytes:
    flags = 1 if end_stream else 0
    return build_frame(Frame.DATA, data, flags=flags, stream_id=stream_id)


def get_frame_type(frame: bytes) -> int:
    if len(frame) < 9:
        raise ValueError("Not a valid HTTP/2 frame.")
    size = 9 + int.from_bytes(frame[:3], "big")
    if len(frame) < size:
        raise ValueError("Frame too short.")
    if len(frame) > size:
        raise ValueError("Frame too long.")
    return frame[3]


def decode_headers(frame: bytes) -> HeadersType:
    frame_type = get_frame_type(frame)
    if frame_type != Frame.HEADERS:
        raise ValueError("Not a HEADERS frame.")
    decoder = hpack.Decoder()
    return cast(HeadersType, decoder.decode(frame[9:], raw=True))


@pytest.fixture(name="client")
def _client(request: Any) -> HTTPOverTCPProtocol:
    factory = HTTP2ClientFactory()
    return factory(tls_version="TLS 1.2", alpn_protocol="h2")


def assert_connection_available(protocol: HTTPOverTCPProtocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert protocol.is_available()
    assert not protocol.has_expired()


def assert_connection_expired(protocol: HTTPOverTCPProtocol) -> None:
    assert protocol.next_event() is None
    assert protocol.bytes_to_send() == b""
    assert not protocol.is_available()
    assert protocol.has_expired()


class TestClient:
    def test_init_connection(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection that connection preface is sent and received.
        """
        client_preface = client.bytes_to_send()
        assert client_preface.startswith(CLIENT_MAGIC)
        assert get_frame_type(client_preface[len(CLIENT_MAGIC) :]) == Frame.SETTINGS
        server_preface = build_frame(Frame.SETTINGS)
        client.bytes_received(server_preface)
        assert client.next_event() is None
        assert get_frame_type(client.bytes_to_send()) == Frame.SETTINGS  # ACK settings

    @classmethod
    def _init_connection(cls, client: HTTPOverTCPProtocol) -> None:
        client.bytes_received(build_frame(Frame.SETTINGS))
        # Consume initial data, so that tests do not see them.
        client.bytes_to_send()

    def test_connection_lost(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection lost without EOF with no request inflight.
        """
        self._init_connection(client)
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_eof_received(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection closed with EOF with no request inflight.
        """
        self._init_connection(client)
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)
        client.connection_lost()
        assert_connection_expired(client)

    def test_send_get(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a GET request.
        """
        self._init_connection(client)
        headers = build_request_headers()
        stream_id = client.get_available_stream_id()
        assert stream_id == 1
        client.submit_headers(stream_id, headers, end_stream=True)
        assert client.bytes_to_send() == build_headers_frame(headers, end_stream=True)
        assert_connection_available(client)

    def test_send_post(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request.
        """
        self._init_connection(client)
        headers = build_request_headers(method=b"POST")
        stream_id = client.get_available_stream_id()
        assert stream_id == 1
        client.submit_headers(stream_id, headers)
        assert client.bytes_to_send() == build_headers_frame(headers)
        client.submit_data(1, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == build_data_frame(b"Hello HTTP!")
        assert_connection_available(client)

    def test_send_post_at_once(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request when headers are sent with data.
        """
        self._init_connection(client)
        headers = build_request_headers(method=b"POST")
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers)
        client.submit_data(stream_id, b"Hello HTTP!", end_stream=True)
        assert client.bytes_to_send() == (
            build_headers_frame(headers) + build_data_frame(b"Hello HTTP!")
        )
        assert_connection_available(client)

    def test_send_post_in_parts(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test a POST request when data are not provided at once.
        """
        self._init_connection(client)
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, build_request_headers(method=b"POST"))
        client.bytes_to_send()
        client.submit_data(stream_id, b"H")
        client.submit_data(stream_id, b"el")
        client.submit_data(stream_id, b"lo HTTP!", end_stream=True)
        assert client.bytes_to_send() == (
            build_data_frame(b"H", end_stream=False)
            + build_data_frame(b"el", end_stream=False)
            + build_data_frame(b"lo HTTP!")
        )
        assert_connection_available(client)

    def test_send_rst_stream(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test that RST_STREAM frame can be sent.
        """
        self._init_connection(client)
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, build_request_headers(method=b"POST"))
        client.bytes_to_send()
        client.submit_stream_reset(stream_id)
        assert client.bytes_to_send() == build_frame(
            Frame.RST_STREAM, b"\0\0\0\0", stream_id=stream_id
        )
        assert client.next_event() == StreamResetSent(stream_id)
        assert_connection_available(client)

    @classmethod
    def _send_request(cls, client: HTTPOverTCPProtocol, method: bytes = b"GET") -> int:
        headers = build_request_headers(method=method)
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, headers, end_stream=True)
        client.bytes_to_send()
        return stream_id

    def test_connection_lost_during_request(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection lost without EOF with a request inflight.
        """
        self._init_connection(client)
        self._send_request(client)
        client.connection_lost()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)

    def test_eof_received_during_request(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test connection closed with EOF with a request inflight.
        """
        self._init_connection(client)
        self._send_request(client)
        client.eof_received()
        assert client.next_event() == ConnectionTerminated()
        assert_connection_expired(client)
        client.connection_lost()
        assert_connection_expired(client)

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                build_data_frame(b"Hello HTTP!"),
                id="unexpected_frame_type",
            ),
            pytest.param(
                build_headers_frame(build_response_headers(), stream_id=0),
                id="missing_stream_id",
            ),
            # FIXME
            # pytest.param(
            #     build_headers_frame(build_response_headers(), stream_id=2),
            #     id="invalid_stream_id",
            # ),
        ],
    )
    def test_recv_invalid(self, client: HTTPOverTCPProtocol, payload: bytes) -> None:
        """
        Test that invalid response causes an error and GOAWAY sent.
        """
        self._init_connection(client)
        self._send_request(client)
        client.bytes_received(payload)
        assert client.next_event() == ConnectionTerminated(0x01)
        assert client.next_event() is None
        assert get_frame_type(client.bytes_to_send()) == Frame.GOAWAY
        assert_connection_expired(client)

    def test_recv(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response.
        """
        self._init_connection(client)
        stream_id = self._send_request(client)
        headers = build_response_headers()
        response = build_headers_frame(headers) + build_data_frame(b"Hello HTTP!")
        client.bytes_received(response)
        assert client.next_event() == HeadersReceived(stream_id, headers)
        assert client.next_event() == DataReceived(
            stream_id, b"Hello HTTP!", end_stream=True
        )
        assert_connection_available(client)

    def test_recv_fragmented(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test receive a response in multiple fragments.
        """
        self._init_connection(client)
        stream_id = self._send_request(client)
        headers = build_response_headers()
        headers_frame = build_headers_frame(headers)
        data_frame = build_data_frame(b"Hello HTTP!")
        client.bytes_received(headers_frame[:2])
        assert client.next_event() is None
        client.bytes_received(headers_frame[2:] + data_frame[:2])
        assert client.next_event() == HeadersReceived(stream_id, headers)
        assert client.next_event() is None
        client.bytes_received(data_frame[2:])
        assert client.next_event() == DataReceived(
            stream_id, b"Hello HTTP!", end_stream=True
        )
        assert_connection_available(client)

    def test_multiple_requests(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test multiple parallel requests.
        """
        self._init_connection(client)
        # Requests
        encoder = hpack.Encoder()
        request_headers = build_request_headers()
        stream_id_a = client.get_available_stream_id()
        assert stream_id_a == 1
        client.submit_headers(1, request_headers, end_stream=True)
        assert client.bytes_to_send() == build_headers_frame(
            request_headers, stream_id=1, end_stream=True, encoder=encoder
        )
        stream_id_b = client.get_available_stream_id()
        assert stream_id_b == 3
        client.submit_headers(3, request_headers, end_stream=True)
        assert client.bytes_to_send() == build_headers_frame(
            request_headers, stream_id=3, end_stream=True, encoder=encoder
        )
        # Responses
        response_headers = build_response_headers()
        headers_frame_a = build_headers_frame(response_headers, stream_id=1)
        data_frame_a = build_data_frame(b"Hello HTTP!", stream_id=1)
        headers_frame_b = build_headers_frame(response_headers, stream_id=3)
        data_frame_b = build_data_frame(b"Hello again!", stream_id=3)
        client.bytes_received(headers_frame_b)
        assert client.next_event() == HeadersReceived(3, response_headers)
        assert client.next_event() is None
        client.bytes_received(headers_frame_a)
        assert client.next_event() == HeadersReceived(1, response_headers)
        assert client.next_event() is None
        client.bytes_received(data_frame_a)
        assert client.next_event() == DataReceived(1, b"Hello HTTP!", end_stream=True)
        assert client.next_event() is None
        client.bytes_received(data_frame_b)
        assert client.next_event() == DataReceived(3, b"Hello again!", end_stream=True)
        assert_connection_available(client)

    _connect_request_headers = [
        (b":method", b"CONNECT"),
        (b":authority", b"example.com:443"),
    ]

    def test_http_connect(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test CONNECT request and response.
        """
        self._init_connection(client)
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert decode_headers(client.bytes_to_send()) == self._connect_request_headers
        client.bytes_received(build_headers_frame([(b":status", b"200")]))
        assert client.next_event() == HeadersReceived(stream_id, [(b":status", b"200")])
        assert_connection_available(client)

    def _http_connect(self, client: HTTPOverTCPProtocol) -> int:
        self._init_connection(client)
        stream_id = client.get_available_stream_id()
        client.submit_headers(stream_id, self._connect_request_headers)
        assert get_frame_type(client.bytes_to_send()) == Frame.HEADERS
        client.bytes_received(build_headers_frame([(b":status", b"200")]))
        assert isinstance(client.next_event(), HeadersReceived)
        return stream_id

    def test_http_connect_data(self, client: HTTPOverTCPProtocol) -> None:
        """
        Data can be exchanged after a CONNECT request.
        """
        stream_id = self._http_connect(client)
        client.submit_data(stream_id, b"Ping")
        assert client.bytes_to_send() == build_data_frame(b"Ping", end_stream=False)
        client.bytes_received(build_data_frame(b"Pong", end_stream=False))
        assert client.next_event() == DataReceived(stream_id, b"Pong")
        assert_connection_available(client)

    def test_http_connect_client_end_stream(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test stream closed by the client after a CONNECT request.
        """
        stream_id = self._http_connect(client)
        client.submit_data(stream_id, b"Bye", end_stream=True)
        assert client.bytes_to_send() == build_data_frame(b"Bye", end_stream=True)

    def test_http_connect_server_end_stream(self, client: HTTPOverTCPProtocol) -> None:
        """
        Test stream closed by the server after a CONNECT request.
        """
        stream_id = self._http_connect(client)
        client.bytes_received(build_data_frame(b"Bye", end_stream=True))
        assert client.next_event() == DataReceived(stream_id, b"Bye", end_stream=True)

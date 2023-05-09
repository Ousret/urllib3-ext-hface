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

from typing import Iterator

import pytest
from helpers import build_request_headers, build_response_headers

from urllib3_ext_hface.events import (
    ConnectionTerminated,
    DataReceived,
    Event,
    HeadersReceived,
    StreamResetReceived,
)
from urllib3_ext_hface.protocols import HTTPOverTCPProtocol, protocol_registry


def _generate_http1() -> Iterator[
    tuple[str, tuple[HTTPOverTCPProtocol, HTTPOverTCPProtocol]]
]:
    for client_name, client_factory in protocol_registry.http1_clients.items():
        client = client_factory(tls_version="TLS 1.2")
        yield f"http1-{client_name}", (client,)


def _generate_http2() -> Iterator[
    tuple[str, tuple[HTTPOverTCPProtocol, HTTPOverTCPProtocol]]
]:
    for client_name, client_factory in protocol_registry.http2_clients.items():
        client = client_factory(tls_version="TLS 1.2", alpn_protocol="h2")
        yield f"http2-{client_name}", (client,)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "client" in metafunc.fixturenames or "server" in metafunc.fixturenames:
        ids = []
        values = []
        for id, value in _generate_http1():
            ids.append(id)
            values.append(value)
        for id, value in _generate_http2():
            ids.append(id)
            values.append(value)
        metafunc.parametrize(("client",), values, ids=ids)


def xfer(source: HTTPOverTCPProtocol, target: HTTPOverTCPProtocol) -> list[Event]:
    data = source.bytes_to_send()
    if data:
        target.bytes_received(data)
    if source.has_expired():
        target.connection_lost()
    return list(iter(target.next_event, None))

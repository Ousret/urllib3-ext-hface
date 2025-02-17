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

from collections import deque
from typing import Iterator, cast

import h2.config
import h2.connection
import h2.events
import h2.exceptions

from ..._typing import HeadersType
from ...events import (
    ConnectionTerminated,
    DataReceived,
    Event,
    GoawayReceived,
    HandshakeCompleted,
    HeadersReceived,
    StreamResetReceived,
    StreamResetSent,
)
from .._protocols import HTTP2Protocol


class HTTP2ProtocolHyperImpl(HTTP2Protocol):
    implementation: str = "h2"

    def __init__(
        self,
        *,
        validate_outbound_headers: bool = False,
        validate_inbound_headers: bool = False,
        normalize_outbound_headers: bool = True,
        normalize_inbound_headers: bool = True,
    ) -> None:
        self._connection: h2.connection.H2Connection = h2.connection.H2Connection(
            h2.config.H2Configuration(
                client_side=True,
                validate_outbound_headers=validate_outbound_headers,
                normalize_outbound_headers=normalize_outbound_headers,
                validate_inbound_headers=validate_inbound_headers,
                normalize_inbound_headers=normalize_inbound_headers,
            )
        )
        self._connection.initiate_connection()
        self._events: deque[Event] = deque()
        self._terminated: bool = False

    @staticmethod
    def exceptions() -> tuple[type[BaseException], ...]:
        return h2.exceptions.ProtocolError, h2.exceptions.H2Error

    def is_available(self) -> bool:
        # TODO: check that we do not run out of stream IDs.
        return not self._terminated

    def has_expired(self) -> bool:
        # TODO: check that we do not run out of stream IDs.
        return self._terminated

    def get_available_stream_id(self) -> int:
        return self._connection.get_next_available_stream_id()  # type: ignore[no-any-return]

    def submit_close(self, error_code: int = 0) -> None:
        self._connection.close_connection(error_code)

    def submit_headers(
        self, stream_id: int, headers: HeadersType, end_stream: bool = False
    ) -> None:
        self._connection.send_headers(stream_id, headers, end_stream)

    def submit_data(
        self, stream_id: int, data: bytes, end_stream: bool = False
    ) -> None:
        self._connection.send_data(stream_id, data, end_stream)

    def submit_stream_reset(self, stream_id: int, error_code: int = 0) -> None:
        self._connection.reset_stream(stream_id, error_code)
        self._events.append(StreamResetSent(stream_id, error_code))

    def next_event(self) -> Event | None:
        if not self._events:
            return None
        return self._events.popleft()

    def has_pending_event(self) -> bool:
        return len(self._events) > 0

    def _map_events(self, h2_events: list[h2.events.Event]) -> Iterator[Event]:
        for e in h2_events:
            if isinstance(
                e,
                (
                    h2.events.RequestReceived,
                    h2.events.ResponseReceived,
                    h2.events.TrailersReceived,
                ),
            ):
                end_stream = e.stream_ended is not None
                yield HeadersReceived(e.stream_id, e.headers, end_stream=end_stream)
            elif isinstance(e, h2.events.DataReceived):
                end_stream = e.stream_ended is not None
                self._connection.acknowledge_received_data(
                    e.flow_controlled_length, e.stream_id
                )
                yield DataReceived(e.stream_id, e.data, end_stream=end_stream)
            elif isinstance(e, h2.events.StreamReset):
                yield StreamResetReceived(e.stream_id, e.error_code)
            elif isinstance(e, h2.events.ConnectionTerminated):
                # ConnectionTerminated from h2 means that GOAWAY was received.
                # A server can send GOAWAY for graceful shutdown, where clients
                # do not open new streams, but inflight requests can be completed.
                #
                # Saying "connection was terminated" can be confusing,
                # so we emit an event called "GoawayReceived".
                yield GoawayReceived(e.last_stream_id, e.error_code)
            elif isinstance(e, h2.events.SettingsAcknowledged):
                yield HandshakeCompleted(alpn_protocol="h2")

    def connection_lost(self) -> None:
        self._connection_terminated()

    def eof_received(self) -> None:
        self._connection_terminated()

    def bytes_received(self, data: bytes) -> None:
        if not data:
            return
        try:
            h2_events = self._connection.receive_data(data)
        except h2.exceptions.ProtocolError as e:
            self._connection_terminated(e.error_code, str(e))
        else:
            self._events.extend(self._map_events(h2_events))

    def bytes_to_send(self) -> bytes:
        return cast(bytes, self._connection.data_to_send())

    def _connection_terminated(
        self, error_code: int = 0, message: str | None = None
    ) -> None:
        if self._terminated:
            return
        error_code = int(error_code)  # Convert h2 IntEnum to an actual int
        self._terminated = True
        self._events.append(ConnectionTerminated(error_code, message))

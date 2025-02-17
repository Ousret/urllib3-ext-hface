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

from abc import ABCMeta, abstractmethod
from typing import Any, Sequence

from .._error_codes import HTTPErrorCodes
from .._typing import HeadersType
from ..events import Event


class BaseProtocol(metaclass=ABCMeta):
    """Sans-IO common methods whenever it is TCP, UDP or QUIC."""

    @abstractmethod
    def bytes_received(self, data: bytes) -> None:
        """
        Called when some data is received.
        """
        raise NotImplementedError

    # Sending direction

    @abstractmethod
    def bytes_to_send(self) -> bytes:
        """
        Returns data for sending out of the internal data buffer.
        """
        raise NotImplementedError

    @abstractmethod
    def connection_lost(self) -> None:
        """
        Called when the connection is lost or closed.
        """
        raise NotImplementedError


class OverTCPProtocol(BaseProtocol):
    """
    Interface for sans-IO protocols on top TCP.
    """

    @abstractmethod
    def eof_received(self) -> None:
        """
        Called when the other end signals it won’t send any more data.
        """
        raise NotImplementedError


class OverUDPProtocol(BaseProtocol):
    """
    Interface for sans-IO protocols on top UDP.
    """

    @abstractmethod
    def clock(self, now: float) -> None:
        """
        Notify the protocol that time has moved.

        The clock value set by this method can be used in subsequent calls
        to other methods. When the time is after the value of :meth:`get_timer`,
        the protocol can handle various timeouts.

        :param now: current time in seconds.
            Typically, the event loop's internal clock.
        """
        raise NotImplementedError

    @abstractmethod
    def get_timer(self) -> float | None:
        """
        Return a clock value when the protocol wants to be notified.

        If the protocol implementation needs to handle any timeouts,
        it should return the closes timeout from this method.

        :return: time in seconds or None if no timer is necessary
        """
        raise NotImplementedError


class OverQUICProtocol(OverUDPProtocol):
    @property
    @abstractmethod
    def connection_ids(self) -> Sequence[bytes]:
        """
        QUIC connection IDs

        This property can be used to assign UDP packets to QUIC connections.

        :return: a sequence of connection IDs
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def session_ticket(self) -> Any | None:
        raise NotImplementedError


class HTTPProtocol(metaclass=ABCMeta):
    """
    Sans-IO representation of an HTTP connection
    """

    implementation: str

    @staticmethod
    @abstractmethod
    def exceptions() -> tuple[type[BaseException], ...]:
        """Return exception types that should be handled in your application."""
        raise NotImplementedError

    @property
    @abstractmethod
    def http_version(self) -> str:
        """
        An HTTP version as a string.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def multiplexed(self) -> bool:
        """
        Whether this connection supports multiple parallel streams.

        Returns ``True`` for HTTP/2 and HTTP/3 connections.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def error_codes(self) -> HTTPErrorCodes:
        """
        Error codes for the HTTP version of this protocol.

        These error codes can be used when a stream is reset
        or when a GOAWAY frame is sent.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return whether this connection is capable to open new streams.
        """
        raise NotImplementedError

    @abstractmethod
    def has_expired(self) -> bool:
        """
        Return whether this connection is closed or should be closed.
        """
        raise NotImplementedError

    @abstractmethod
    def get_available_stream_id(self) -> int:
        """
        Return an ID that can be used to create a new stream.

        Use the returned ID with :meth:`.submit_headers` to create the stream.
        This method may or may not return one value until that method is called.

        :return: stream ID
        """
        raise NotImplementedError

    @abstractmethod
    def submit_headers(
        self, stream_id: int, headers: HeadersType, end_stream: bool = False
    ) -> None:
        """
        Submit a frame with HTTP headers.

        If this is a client connection, this method starts an HTTP request.
        If this is a server connection, it starts an HTTP response.

        :param stream_id: stream ID
        :param headers: HTTP headers
        :param end_stream: whether to close the stream for sending
        """
        raise NotImplementedError

    @abstractmethod
    def submit_data(
        self, stream_id: int, data: bytes, end_stream: bool = False
    ) -> None:
        """
        Submit a frame with HTTP data.

        :param stream_id: stream ID
        :param data: payload
        :param end_stream: whether to close the stream for sending
        """
        raise NotImplementedError

    @abstractmethod
    def submit_stream_reset(self, stream_id: int, error_code: int = 0) -> None:
        """
        Immediate terminate a stream.

        Stream reset is used to request cancellation of a stream
        or to indicate that an error condition has occurred.

        Use :attr:`.error_codes` to obtain error codes for common problems.

        :param stream_id: stream ID
        :param error_code:  indicates why the stream is being terminated
        """
        raise NotImplementedError

    @abstractmethod
    def submit_close(self, error_code: int = 0) -> None:
        """
        Submit graceful close the connection.

        Use :attr:`.error_codes` to obtain error codes for common problems.

        :param error_code:  indicates why the connections is being closed
        """
        raise NotImplementedError

    @abstractmethod
    def next_event(self) -> Event | None:
        """
        Consume next HTTP event.

        :return: an event instance
        """
        raise NotImplementedError

    @abstractmethod
    def has_pending_event(self) -> bool:
        """Verify if there is queued event waiting to be consumed."""
        raise NotImplementedError


class HTTPOverTCPProtocol(HTTPProtocol, OverTCPProtocol):
    """
    :class:`HTTPProtocol` over a TCP connection

    An interface for HTTP/1 and HTTP/2 protocols.
    Extends :class:`.HTTPProtocol`.
    """


class HTTPOverQUICProtocol(HTTPProtocol, OverQUICProtocol):
    """
    :class:`HTTPProtocol` over a QUIC connection

    Abstract base class for HTTP/3 protocols.
    Extends :class:`.HTTPProtocol`.
    """


class HTTP1Protocol(HTTPOverTCPProtocol):
    """
    Sans-IO representation of an HTTP/1 connection

    An interface for HTTP/1 implementations.
    Extends :class:`.HTTPOverTCPProtocol`.
    """

    @property
    def http_version(self) -> str:
        return "1"

    @property
    def multiplexed(self) -> bool:
        return False

    error_codes = HTTPErrorCodes(
        protocol_error=400,
        internal_error=500,
        connect_error=502,
    )


class HTTP2Protocol(HTTPOverTCPProtocol):
    """
    Sans-IO representation of an HTTP/2 connection

    An abstract base class for HTTP/2 implementations.
    Extends :class:`.HTTPOverTCPProtocol`.
    """

    @property
    def http_version(self) -> str:
        return "2"

    @property
    def multiplexed(self) -> bool:
        return True

    error_codes = HTTPErrorCodes(
        protocol_error=0x01,
        internal_error=0x02,
        connect_error=0x0A,
    )


class HTTP3Protocol(HTTPOverQUICProtocol):
    """
    Sans-IO representation of an HTTP/2 connection

    An abstract base class for HTTP/3 implementations.
    Extends :class:`.HTTPOverQUICProtocol`
    """

    @property
    def http_version(self) -> str:
        return "3"

    @property
    def multiplexed(self) -> bool:
        return True

    error_codes = HTTPErrorCodes(
        protocol_error=0x0101,
        internal_error=0x0102,
        connect_error=0x010F,
    )

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

from ._configuration import ClientTLSConfig
from ._error_codes import HTTPErrorCodes
from ._typing import AddressType, DatagramType, HeadersType, HeaderType
from ._version import __version__
from .protocols import (
    ALPNHTTPFactory,
    HTTP1ClientFactory,
    HTTP1Protocol,
    HTTP2ClientFactory,
    HTTP2Protocol,
    HTTP3ClientFactory,
    HTTP3Protocol,
    HTTPOverQUICClientFactory,
    HTTPOverQUICProtocol,
    HTTPOverTCPFactory,
    HTTPOverTCPProtocol,
    HTTPProtocol,
)

__all__ = (
    "ClientTLSConfig",
    "HTTPErrorCodes",
    "AddressType",
    "DatagramType",
    "HeadersType",
    "HeaderType",
    "ALPNHTTPFactory",
    "HTTP1ClientFactory",
    "HTTP1Protocol",
    "HTTP2ClientFactory",
    "HTTP2Protocol",
    "HTTP3ClientFactory",
    "HTTP3Protocol",
    "HTTPOverQUICClientFactory",
    "HTTPOverQUICProtocol",
    "HTTPOverTCPFactory",
    "HTTPOverTCPProtocol",
    "HTTPProtocol",
    "__version__",
)

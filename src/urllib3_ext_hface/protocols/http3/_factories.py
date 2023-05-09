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

import os
import ssl

import aioquic.h3.connection
import aioquic.quic.configuration
import aioquic.quic.connection

from ..._configuration import ClientTLSConfig
from ..._typing import AddressType
from .._factories import HTTPOverQUICClientFactory
from .._protocols import HTTP3Protocol
from ._protocol import HTTP3ProtocolImpl


class HTTP3ClientFactory(HTTPOverQUICClientFactory):
    """
    Creates a default HTTP/3 protocol for client-side usage.

    The HTTP/3 implementation is built on the top of the aioquic_ library.

    .. _aioquic: https://aioquic.readthedocs.io/

    Implements :class:`.HTTPOverQUICClientFactory`.
    """

    def __call__(
        self,
        *,
        remote_address: AddressType,
        server_name: str,
        tls_config: ClientTLSConfig,
    ) -> HTTP3Protocol:
        configuration = self._build_configuration(tls_config=tls_config)
        configuration.server_name = server_name
        return HTTP3ProtocolImpl(configuration, remote_address=remote_address)

    def _build_configuration(
        self, *, tls_config: ClientTLSConfig
    ) -> aioquic.quic.configuration.QuicConfiguration:
        # OpenSSL (so Python builtin ssl.SSLContext) trusts to SSL_CERT_FILE by default.
        # We set it here explicitly, so that TLS implementations not using OpenSSL
        # (namely aioquic and our default HTTP/3 implementation) use this variable too.
        #
        # We could (and probably should) be more sophisticated in unifying
        # TLS configuration, but just this one hack helps a lot.
        tls_cafile = tls_config.cafile or os.environ.get("SSL_CERT_FILE")
        return aioquic.quic.configuration.QuicConfiguration(
            is_client=True,
            verify_mode=ssl.CERT_NONE if tls_config.insecure else ssl.CERT_REQUIRED,
            cafile=tls_cafile,
            capath=tls_config.capath,
            cadata=tls_config.cadata,
            alpn_protocols=["h3"],
        )

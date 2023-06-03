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

"""
HTTP factories create HTTP protools based on defined set of arguments.

We define the :class:`HTTPProtocol` interface to allow interchange
HTTP versions and protocol implementations. But constructors of
the class is not part of the interface. Every implementation
can use a different options to init instances.

Factories unify access to the creation of the protocol instances,
so that clients and servers can swap protocol implementations,
delegating the initialization to factories.
"""
from __future__ import annotations

import importlib
import inspect
from abc import ABCMeta
from typing import Any

from ._protocols import HTTPOverQUICProtocol, HTTPOverTCPProtocol, HTTPProtocol


class HTTPProtocolFactory(metaclass=ABCMeta):
    @staticmethod
    def new(
        type_protocol: type[HTTPProtocol],
        implementation: str | None = None,
        **kwargs: Any,
    ) -> HTTPOverQUICProtocol | HTTPOverTCPProtocol:
        assert type_protocol != HTTPProtocol

        version_target: str = "".join(
            c
            for c in str(type_protocol).replace("urllib3_ext_hface", "")
            if c.isdigit()
        )
        module_expr: str = f".protocols.http{version_target}"

        if implementation:
            module_expr += f"._{implementation.lower()}"

        http_module = importlib.import_module(
            f".protocols.http{version_target}", "urllib3_ext_hface"
        )

        implementations: list[
            tuple[str, type[HTTPOverQUICProtocol | HTTPOverTCPProtocol]]
        ] = inspect.getmembers(
            http_module,
            lambda e: isinstance(e, type)
            and issubclass(e, (HTTPOverQUICProtocol, HTTPOverTCPProtocol)),
        )

        if not implementations:
            raise ImportError(
                "Unable to instantiate a HTTPProtocol for given type target and implementation."
            )

        implementation_target: type[
            HTTPOverQUICProtocol | HTTPOverTCPProtocol
        ] = implementations.pop()[1]

        return implementation_target(**kwargs)

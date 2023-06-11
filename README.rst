
===================================================
urllib3 extension: hface
===================================================

PyPI_

This project is a fork of the akamai/hface project but highly slimmed.
The purpose of that project is to enable basic support for HTTP/1.1, HTTP/2 and HTTP/3 in urllib3.

* HTTP/1.1, HTTP/2, and HTTP/3 support through respectively h11, h2 and aioquic
* Sans-IO_ core with pluggable protocol implementations
* Layered design with well-defined APIs
* Client-oriented only

.. _PyPI: https://pypi.org/project/urllib3-ext-hface

.. _Sans-IO: https://sans-io.readthedocs.io/

Documentation
-------------

This library is pretty straight forward and is very easy to understand.

.. code-block:: python

    from urllib3_ext_hface import HTTPProtocolFactory, HTTP1Protocol, HTTP2Protocol, HTTP3Protocol

    protocol = HTTPProtocolFactory.new(HTTP2Protocol)

    # ...
    protocol.bytes_to_send()  # Out to your network I/O implementation
    # ...
    protocol.bytes_received()  # Whatever comes from your network I/O implementation
    # ...
    protocol.next_event()  # Output the next event in order that the state-machine generated

Here ``protocol`` is either of type ``HTTPOverQUICProtocol`` or ``HTTPOverTCPProtocol``, depending
on the foremost, you will either be on a DGRAM (UDP) or STREAM (TCP) socket.

Find just bellow a somewhat stupid example that can help you get started.

.. code-block:: python

    from urllib3_ext_hface import HTTPProtocolFactory, HTTP1Protocol, HTTP2Protocol, HTTP3Protocol
    import ssl
    import socket
    import certifi

    RECV_LENGTH = 4096

    if __name__ == "__main__":

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.set_alpn_protocols(["h2"])

        ctx.load_default_certs()
        ctx.load_verify_locations(certifi.where())

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        sock = ctx.wrap_socket(sock, server_hostname="httpbin.org")

        sock.connect(("httpbin.org", 443))

        sock.settimeout(3)

        protocol = HTTPProtocolFactory.new(HTTP2Protocol)

        # Start HTTP2*PRI
        while True:
            data_out = protocol.bytes_to_send()

            if not data_out:
                break

            sock.sendall(data_out)

            protocol.bytes_received(
                sock.recv(RECV_LENGTH)
            )

        stream_id = protocol.get_available_stream_id()

        protocol.submit_headers(
            stream_id,
            [
                (b":authority", b"httpbin.org"),
                (b":scheme", b"https"),
                (b":path", b"/headers"),
                (b":method", b"GET"),
                (b"User-Agent", b"Awesome Sans-IO!")
            ],
            True
        )

        sock.sendall(
            protocol.bytes_to_send()
        )

        while True:

            try:
                protocol.bytes_received(
                    sock.recv(RECV_LENGTH)
                )
            except TimeoutError:
                protocol.connection_lost()

            event = protocol.next_event()

            if hasattr(event, "data"):
                print(event.data)

            print(event)

            if hasattr(event, "end_stream") and event.end_stream is True:
                break

        protocol.submit_close()

        sock.sendall(protocol.bytes_to_send())

        sock.close()

License
-------

::

    Copyright 2022 Akamai Technologies, Inc

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

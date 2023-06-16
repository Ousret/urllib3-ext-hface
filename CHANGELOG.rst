v0.3.4 (2023-06-16)
-------------------

* Switch ``aioquic`` to (own) fork ``qh3`` that fixes numerous issues. The dependency chain is simpler. Pending discussions with original owner to merge.

v0.3.3 (2023-06-12)
-------------------

* Push the ``HandshakeCompleted`` event for the ``HTTP2ProtocolHyperImpl``.

v0.3.2 (2023-06-12)
-------------------

* Properly forward ConnectionTerminated event from the QUIC layer in ``HTTP3ProtocolAioQuicImpl``.

v0.3.1 (2023-06-10)
-------------------

* Allow passing extra config parameter for HTTP2Protocol through the factory.
* Remove server-side code in the primary (h11) HTTP1Protocol.

v0.3.0 (2023-06-03)
-------------------

* Breaking: Conception simplification. Remove HTTPFactories in favor of a single unified HTTPFactory.
* Lazy import HTTPProtocol implementation.

v0.2.12 (2023-05-25)
--------------------

* Remove ``InvalidPacket``, ``PacketInfo`` from protocols.http3.
* Fix an error trying to unset previously unknown connection id in quic event handler.

v0.2.11 (2023-05-24)
--------

* Add keyfile, certfile and keypassword in ``ClientTLSConfig`` to be passed down the QUIC configuration.

v0.2.10 (2023-05-23)
--------

* Add staticmethod ``exceptions`` on ``HTTPProtocol`` that return sub-dependency-protocol specific exceptions.

v0.2.9 (2023-05-23)
--------

* No longer lower (twice) header name case in h11 response event.

v0.2.8 (2023-05-21)
--------

* Add method ``has_pending_event`` across protocols impl.

v0.2.7 (2023-05-21)
--------

* Remove undesired and miscalled ping() method in quic connection.

v0.2.6 (2023-05-21)
--------

* Fix ``OverUDPProtocol`` not inheriting ``BaseProtocol``.

v0.2.5 (2023-05-21)
--------

* Add getter for the ``SessionTicket`` provided by aioquic in ``HTTP3Protocol``.

v0.2.4 (2023-05-20)
--------

* Enforce `bytes_to_send` and `bytes_received` for all abstract protocols.
* Implement graceful close for ``HTTP2Protocol`` (GoAway packet).

v0.2.3 (2023-05-14)
--------

* Remove ``ProtocolRegistry``.

v0.2.2 (2023-05-13)
--------

* Allow setting ciphers and session ticket through ``HTTP3ProtocolFactory``.

v0.2.1 (2023-05-13)
--------

* Simplification made in ``HTTP3Protocol`` so that closer to generic usage across protocols.

v0.2.0 (2023-05-09)
--------

* Explicit support for Python 3.11.
* `HTTPOverQUICOpener` does not require ``tls_config`` (similar to ``HTTPOverTCPOpener``).
* Removed everything except Sans-IO protocols interfaces.
* Fixed a bug in HTTP2Protocol that missed to acknowledge received data.

v0.1 (2022-11-01)
-----------------

* Initial release.

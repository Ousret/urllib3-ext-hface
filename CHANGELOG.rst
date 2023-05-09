
v0.2.0 (2023-05-09)
--------

* Explicit support for Python 3.11.
* `HTTPOverQUICOpener` does not require ``tls_config`` (similar to ``HTTPOverTCPOpener``).
* Removed everything except Sans-IO protocols interfaces.
* Fixed a bug in HTTP2Protocol that missed to acknowledge received data.

v0.1 (2022-11-01)
-----------------

* Initial release.

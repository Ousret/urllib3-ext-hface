
===================================================
urllib3 extension: hface
===================================================

Documentation_ | GitHub_ | PyPI_

This project is a fork of the akamai/hface project but highly slimmed.
The purpose of that project is to enable basic support for HTTP/1.1, HTTP/2 and HTTP/3 in urllib3.

* HTTP/1.1, HTTP/2, and HTTP/3 support through respectively h11, h2 and aioquic
* Sans-IO_ core with pluggable protocol implementations
* Layered design with well-defined APIs
* Client-oriented only

See online documentation_ for more info.

.. _Documentation: https://urllib3.readthedocs.io/
.. _GitHub: https://github.com/Ousret/urllib3-ext-hface
.. _PyPI: https://pypi.org/project/urllib3-ext-hface

.. _Sans-IO: https://sans-io.readthedocs.io/

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

# WEEX Python Connectors

[![Open Issues](https://img.shields.io/github/issues/weex-labs/weex-connector-python)](https://github.com/weex-labs/weex-connector-python/issues)
![Python Version](https://img.shields.io/badge/Python-%3E%3D3.9-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

English is the source of truth for this README. Languages: English | [Chinese](./README.zh-CN.md)

Collection of modular, auto-generated Python SDKs for WEEX APIs.

## Prerequisites

Before using the SDK, ensure you have:

- Python 3.9 or later
- `pip`
- Optional: `venv` or another virtual environment tool

## Available SDK

- [weex-common](./common) - Shared runtime utilities for configuration, signing, transport, errors, and WebSocket support.
- [weex-spot-sdk](./clients/spot) - Spot trading connector with REST APIs, WebSocket APIs, and WebSocket Streams.
- [weex-contract-sdk](./clients/contract) - Contract trading connector with REST APIs, WebSocket APIs, and WebSocket Streams.

## Documentation

For detailed information, refer to:

- [WEEX Spot API Documentation](https://www.weex.com/api-doc/spot)
- [WEEX Contract API Documentation](https://www.weex.com/api-doc/contract)
- [WEEX Python Common Runtime](./common/README.md)
- [WEEX Python Spot SDK](./clients/spot/README.md)
- [WEEX Python Contract SDK](./clients/contract/README.md)

Repository: [weex-labs/weex-connector-python](https://github.com/weex-labs/weex-connector-python)

Connector-specific scope notes, staging guidance, and runnable examples are documented in each client README.

## Installation

Each connector is maintained as a separate Python package inside this repository. These packages are currently installed from source, so from the repository root install the shared runtime first, then install the connector you need:

```bash
pip install -e ./common
pip install -e ./clients/spot
pip install -e ./clients/contract
```

If you only need one connector, install `./common` and the connector package you plan to use.

## Contributing

Since this repository contains generated SDK code, we recommend you:

1. Open an issue before proposing API surface changes or reporting generator mismatches.
2. Keep shared runtime changes in [common](./common).
3. Update the affected README, examples, and tests together when public behavior changes.

## Code Style

This repository keeps the current public Python SDK surface stable and follows a lightweight Python contribution workflow:

- Keep public import paths and package names stable.
- Keep changes PEP 8-compatible and consistent with the existing module layout.
- Re-run the repository checks before delivery:

```bash
python -m compileall ./common/src
python -m compileall ./clients/spot/src
python -m compileall ./clients/contract/src
```

If you install the optional `dev` dependencies for a connector, also run its local tests as part of your change review.

## Migration Guide

If you are upgrading from the previous standalone WEEX Python SDK layout:

- `weex_spot_sdk` and `weex_contract_sdk` remain the public import packages.
- Shared runtime code now lives in [common](./common), so `weex-common` must be installed before either connector.
- Connector-specific examples and tests remain inside each client directory.

## License

See the [LICENSE](./LICENSE) file for licensing details.

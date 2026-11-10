# WEEX Common Types and Utilities for Python Connectors

[![Open Issues](https://img.shields.io/github/issues/weex-labs/weex-connector-python)](https://github.com/weex-labs/weex-connector-python/issues)
![Python Version](https://img.shields.io/badge/Python-%3E%3D3.9-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

English is the source of truth for this README. Languages: English | [Chinese](./README.zh-CN.md)

`weex-common` is a utility package for WEEX modular connectors, providing shared configuration, signing, transport, error handling, and WebSocket helpers for the Spot and Contract SDKs.

## Installation

To use this library, ensure your environment is running Python version **3.9** or later.

This package is currently installed from a repository checkout:

```bash
pip install -e ./common
```

Repository: [weex-labs/weex-connector-python](https://github.com/weex-labs/weex-connector-python)

## Features

- Shared utility classes for REST requests, response models, timestamps, and HMAC signatures.
- Reusable configuration objects for REST APIs, WebSocket APIs, and WebSocket Streams.
- Secure endpoint validation for REST and WebSocket URLs, limited to approved WEEX hostnames over `https` / `wss` by default.
- Lightweight runtime layer reused by both `weex-spot-sdk` and `weex-contract-sdk`.

## Contributing

Contributions are welcome.

1. Open an issue before making shared runtime changes.
2. Keep reusable behavior in `weex_common`.
3. Update connector README files or examples when shared behavior changes.

## License

See the [LICENSE](../LICENSE) file for licensing details.

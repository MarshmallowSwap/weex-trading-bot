# WEEX Common Types and Utilities for Python Connectors

[![Open Issues](https://img.shields.io/github/issues/weex-labs/weex-connector-python)](https://github.com/weex-labs/weex-connector-python/issues)
![Python Version](https://img.shields.io/badge/Python-%3E%3D3.9-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

英文原版为准。语言：[English](./README.md) | 简体中文

`weex-common` 是面向 WEEX 模块化连接器的通用工具包，为 Spot 和 Contract SDK 提供共享配置、签名、传输、错误处理以及 WebSocket 辅助能力。

## 安装

使用该库时，请确保运行环境为 Python **3.9** 或更高版本。

该包目前通过仓库源码检出安装：

```bash
pip install -e ./common
```

仓库地址：[weex-labs/weex-connector-python](https://github.com/weex-labs/weex-connector-python)

## 特性

- 提供 REST 请求、响应模型、时间戳和 HMAC 签名相关的共享工具类。
- 为 REST API、WebSocket API 和 WebSocket Streams 提供可复用的配置对象。
- 默认对 REST 和 WebSocket URL 启用安全校验，只允许通过 `https` / `wss` 访问经批准的 WEEX 主机名。
- 提供由 `weex-spot-sdk` 和 `weex-contract-sdk` 共同复用的轻量运行时层。

## 贡献

欢迎贡献。

1. 在修改共享运行时之前，请先创建 issue。
2. 将可复用行为保持在 `weex_common` 中。
3. 当共享行为发生变化时，同时更新连接器 README 或示例。

## 许可证

许可详情请参阅 [LICENSE](../LICENSE) 文件。

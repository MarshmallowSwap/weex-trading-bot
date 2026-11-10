# WEEX Python Connectors

[![Open Issues](https://img.shields.io/github/issues/weex-labs/weex-connector-python)](https://github.com/weex-labs/weex-connector-python/issues)
![Python Version](https://img.shields.io/badge/Python-%3E%3D3.9-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

英文原版为准。语言：[English](./README.md) | 简体中文

面向 WEEX API 的模块化、自动生成 Python SDK 集合。

## 前置条件

在使用 SDK 之前，请确保你具备：

- Python 3.9 或更高版本
- `pip`
- 可选：`venv` 或其它虚拟环境工具

## 可用 SDK

- [weex-common](./common/README.zh-CN.md) - 为配置、签名、传输、错误处理和 WebSocket 支持提供共享运行时工具。
- [weex-spot-sdk](./clients/spot/README.zh-CN.md) - 现货交易连接器，支持 REST API、WebSocket API 和 WebSocket Streams。
- [weex-contract-sdk](./clients/contract/README.zh-CN.md) - 合约交易连接器，支持 REST API、WebSocket API 和 WebSocket Streams。

## 文档

详细信息请参考：

- [WEEX Spot API Documentation](https://www.weex.com/api-doc/spot)
- [WEEX Contract API Documentation](https://www.weex.com/api-doc/contract)
- [WEEX Python 通用运行时](./common/README.zh-CN.md)
- [WEEX Python Spot SDK](./clients/spot/README.zh-CN.md)
- [WEEX Python Contract SDK](./clients/contract/README.zh-CN.md)

仓库地址：[weex-labs/weex-connector-python](https://github.com/weex-labs/weex-connector-python)

各连接器自身的范围说明、预发环境使用建议以及可运行示例，均记录在对应客户端的 README 中。

## 安装

每个连接器在当前仓库中都是独立的 Python 包。这些包目前通过源码方式安装，因此请先在仓库根目录安装共享运行时，再安装你需要的连接器：

```bash
pip install -e ./common
pip install -e ./clients/spot
pip install -e ./clients/contract
```

如果你只需要一个连接器，只安装 `./common` 和对应连接器包即可。

## 贡献

由于本仓库包含生成型 SDK 代码，我们建议你：

1. 在提出 API 变更建议或报告生成器与上游规范不一致的问题之前，先创建 issue。
2. 将共享运行时相关改动放在 [common](./common/README.zh-CN.md) 中。
3. 当公开行为发生变化时，同时更新对应 README、示例和测试。

## 代码风格

本仓库保持当前公开 Python SDK 接口稳定，并采用轻量级的 Python 贡献流程：

- 保持公开 import path 和 package 名称稳定。
- 保持改动符合 PEP 8，并与现有模块布局一致。
- 在交付前重新执行仓库检查：

```bash
python -m compileall ./common/src
python -m compileall ./clients/spot/src
python -m compileall ./clients/contract/src
```

如果你为某个连接器安装了可选的 `dev` 依赖，也请在变更评审中一并执行其本地测试。

## 迁移指南

如果你正从旧的独立版 WEEX Python SDK 布局升级：

- `weex_spot_sdk` 和 `weex_contract_sdk` 仍然是对外公开的导入包名。
- 共享运行时代码现在位于 [common](./common/README.zh-CN.md)，因此在使用任一连接器前都必须先安装 `weex-common`。
- 连接器特定的示例和测试仍保留在各自客户端目录中。

## 许可证

许可详情请参阅 [LICENSE](./LICENSE) 文件。

# WEEX Python Contract SDK

[![Open Issues](https://img.shields.io/github/issues/weex-labs/weex-connector-python)](https://github.com/weex-labs/weex-connector-python/issues)
![Python Version](https://img.shields.io/badge/Python-%3E%3D3.9-brightgreen)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

英文原版为准。语言：[English](./README.md) | 简体中文

这是一个面向 WEEX Contract API 的客户端库，帮助开发者通过以下三个独立入口以编程方式接入 WEEX 合约交易：

- [REST API](./src/weex_contract_sdk/rest_api/rest_api.py)
- [Websocket API](./src/weex_contract_sdk/websocket_api/websocket_api.py)
- [Websocket Stream](./src/weex_contract_sdk/websocket_streams/websocket_streams.py)

## 目录

- [支持特性](#supported-features)
- [安装](#installation)
- [文档](#documentation)
- [REST API](#rest-apis)
- [WebSocket API](#websocket-apis)
- [WebSocket Streams](#websocket-streams)
- [自动连接恢复](#automatic-connection-renewal)
- [测试](#testing)
- [迁移指南](#migration-guide)
- [贡献](#contributing)
- [许可证](#license)

<a id="supported-features"></a>

## 支持特性

- REST API 端点：
  - `/capi/*`
  - 服务分组：`AccountApi`、`MarketApi`、`TradeApi`
- WebSocket 端点：支持鉴权请求-响应流程以及公开市场数据流。
- 提供可直接运行的示例和连接器内本地测试，便于快速上手。
- 范围说明：本 SDK 有意不包含 `POST /capi/v3/batchOrders`。

<a id="installation"></a>

## 安装

使用该库时，请确保运行环境为 Python **3.9** 或更高版本。

这些包目前通过源码方式安装。请先在仓库根目录安装共享运行时，再安装 Contract 连接器：

```bash
pip install -e ./common
pip install -e ./clients/contract
```

如果你需要 Contract 专属的开发依赖，请在 `./common` 可用后，以 `dev` extra 安装该包。

常用环境变量：

- `WEEX_API_KEY`
- `WEEX_API_SECRET`
- `WEEX_API_PASSPHRASE`
- `WEEX_BASE_URL`
- `WEEX_WS_PRIVATE_URL`
- `WEEX_WS_PUBLIC_URL`

<a id="documentation"></a>

## 文档

详细信息请参考：

- [WEEX Contract API Documentation](https://www.weex.com/api-doc/contract)
- [REST API 源码](./src/weex_contract_sdk/rest_api/rest_api.py)
- [Websocket API 源码](./src/weex_contract_sdk/websocket_api/websocket_api.py)
- [Websocket Streams 源码](./src/weex_contract_sdk/websocket_streams/websocket_streams.py)
- [REST 示例](./examples/rest_example.py)
- [私有 Websocket 示例](./examples/private_ws_example.py)
- [公共 Websocket 示例](./examples/public_ws_example.py)

仓库地址：[weex-labs/weex-connector-python](https://github.com/weex-labs/weex-connector-python)

<a id="rest-apis"></a>

### REST API

所有 REST API 端点都通过 [`rest_api`](./src/weex_contract_sdk/rest_api/rest_api.py) 模块提供。REST API 可用于获取市场数据、管理仓位以及下单或撤单。部分端点需要使用你的 WEEX 凭证进行鉴权。

```python
from weex_contract_sdk import Contract

client = Contract.from_env()
response = client.rest_api.market_api.get_capi_v3_market_depth(
    {"query": {"symbol": "BTCUSDT", "limit": 15}}
)

print(response.status_code)
print(response.data)
```

更多示例可在 [`examples`](./examples/) 目录中找到。

#### 配置选项

REST API 支持以下配置项：

- `base_path`：REST 基础 URL。默认值为 `https://api-contract.weex.com`。
- `allowed_domains`：自定义 REST / WebSocket 端点允许使用的主机名或域名后缀。默认值为 `("weex.com", "weex.tech")`。
- `api_key`、`api_secret`、`passphrase`：HMAC 鉴权凭证。
- `timeout`：请求超时时间，单位为秒。默认值为 `30.0`。
- `max_retries`：重试次数。默认值为 `0`。
- `base_headers`：附加到每个请求上的额外请求头。
- `user_agent`：自定义 User-Agent 字符串。
- `session`：自定义 HTTP session 对象。

##### 基础 URL

当你需要接入不同的 WEEX 环境时，可使用 `base_path` 覆盖默认的 Contract REST 端点。
自定义 REST 端点必须使用 `https://`，且主机名需要命中 `allowed_domains` 白名单。

##### 凭证

为需要鉴权的 REST 端点提供 `api_key`、`api_secret` 和 `passphrase`。公开市场数据端点可在不提供这些凭证的情况下调用。

##### 超时

通过设置 `timeout`，控制客户端在判定 REST 请求失败前等待响应的最长时间，单位为秒。

##### 重试

使用 `max_retries` 控制失败的 REST 请求是否自动重试。

##### 基础请求头

使用 `base_headers` 为客户端生成的每个 REST 请求追加自定义请求头。

##### User-Agent

如果你需要在出站请求中使用自定义客户端标识，可设置 `user_agent`。

##### HTTP Session

当你需要复用已有的 HTTP 传输配置时，可传入自定义 `session` 对象。

#### 错误处理

REST API 提供详细的错误类型，帮助你更有效地处理问题：

- `RequiredError`
- `ClientError`
- `SignatureError`
- `NetworkError`
- `BadRequestError`
- `UnauthorizedError`
- `ForbiddenError`
- `NotFoundError`
- `TooManyRequestsError`
- `ServerError`
- `ApiBusinessError`

#### 预发环境

WEEX 当前未在外部文档中公开预发 REST 端点。如果你的 WEEX 团队为验证提供了相应地址，请在创建客户端前更新 `WEEX_BASE_URL`：

```bash
export WEEX_BASE_URL=https://<contract-staging-rest-endpoint>
```

默认情况下，自定义端点必须仍然位于 `*.weex.com` 或 `*.weex.tech` 下。如果 WEEX 提供了其他官方域名，请在创建客户端前显式构造 `ConfigurationRestAPI(..., allowed_domains=(...))`。

#### 范围说明

- `POST /capi/v3/batchOrders` 有意不包含在本 SDK 中。
- `DELETE /capi/v3/batchOrders` 依据预发环境验证结果实现，并期望接收 JSON `requestBody(orderIdList)`。

<a id="websocket-apis"></a>

### WebSocket API

WebSocket API 为订单、仓位和账户事件提供需要鉴权的请求-响应通信。使用 [`websocket_api`](./src/weex_contract_sdk/websocket_api/websocket_api.py) 模块与这些端点交互。

```python
from weex_contract_sdk import Contract

client = Contract.from_env()
ws_api = client.websocket_api
ws_api.connect()
ws_api.subscribe_orders()
print(ws_api.receive())
ws_api.close()
```

更多示例可在 [`examples`](./examples/) 目录中找到。

#### 配置选项

WebSocket API 支持以下配置项：

- `stream_url`：私有 WebSocket 端点。
- `allowed_domains`：自定义 REST / WebSocket 端点允许使用的主机名或域名后缀。默认值为 `("weex.com", "weex.tech")`。
- `api_key`、`api_secret`、`passphrase`：鉴权 WebSocket 凭证。
- `timeout`：Socket 超时时间，单位为秒。默认值为 `30.0`。
- `reconnect_delay`：断开连接后的重连等待时间。默认值为 `1.5`。
- `user_agent`：自定义 User-Agent 字符串。

##### 凭证

为需要鉴权的私有 WebSocket 请求提供 `api_key`、`api_secret` 和 `passphrase`。

##### 超时

通过设置 `timeout`，控制客户端等待 WebSocket 操作完成的最长时间，单位为秒。

##### 重连延迟

使用 `reconnect_delay` 控制私有 WebSocket 会话断开后，客户端等待多久再进行重连。

##### User-Agent

如果你需要在 WebSocket 握手期间使用自定义客户端标识，可设置 `user_agent`。

#### 预发环境

WEEX 当前未在外部文档中公开预发私有 WebSocket 端点。如果你的 WEEX 团队为验证提供了相应地址，请在创建客户端前更新 `WEEX_WS_PRIVATE_URL`：

```bash
export WEEX_WS_PRIVATE_URL=wss://<contract-staging-private-websocket-endpoint>
```

私有 WebSocket 覆盖地址必须使用 `wss://`，并且主机名需要落在 `allowed_domains` 内；只有在代码里显式扩展白名单时才会放行其他官方域名。

<a id="websocket-streams"></a>

### WebSocket Streams

WebSocket Streams 模块为 ticker、depth、trade 和类 kline 频道提供公开市场数据订阅。使用 [`websocket_streams`](./src/weex_contract_sdk/websocket_streams/websocket_streams.py) 模块与这些端点交互。

```python
from weex_contract_sdk import Contract

client = Contract.from_env()
streams = client.websocket_streams
streams.connect()
streams.subscribe_ticker("BTCUSDT")
print(streams.receive())
streams.close()
```

更多示例可在 [`examples`](./examples/) 目录中找到。

#### 配置选项

WebSocket Streams 模块支持以下配置项：

- `stream_url`：公共 WebSocket 端点。
- `allowed_domains`：自定义 REST / WebSocket 端点允许使用的主机名或域名后缀。默认值为 `("weex.com", "weex.tech")`。
- `timeout`：Socket 超时时间，单位为秒。默认值为 `30.0`。
- `reconnect_delay`：断开连接后的重连等待时间。默认值为 `1.5`。
- `user_agent`：自定义 User-Agent 字符串。

##### 流地址

使用 `stream_url` 可覆盖默认的公共市场数据 WebSocket 端点。
自定义流地址必须使用 `wss://`，且主机名需要命中 `allowed_domains` 白名单。

##### 超时

通过设置 `timeout`，控制客户端在返回错误前等待流活动的最长时间，单位为秒。

##### 重连延迟

使用 `reconnect_delay` 控制公共流连接断开后，客户端等待多久再进行重连。

##### User-Agent

如果你需要在 WebSocket 握手期间使用自定义客户端标识，可设置 `user_agent`。

#### 预发环境

WEEX 当前未在外部文档中公开预发公共 WebSocket 端点。如果你的 WEEX 团队为验证提供了相应地址，请在创建客户端前更新 `WEEX_WS_PUBLIC_URL`：

```bash
export WEEX_WS_PUBLIC_URL=wss://<contract-staging-public-websocket-endpoint>
```

公共 WebSocket 覆盖地址与私有 WebSocket 一样，沿用相同的安全默认白名单。

<a id="automatic-connection-renewal"></a>

### 自动连接恢复

WebSocket API 与 WebSocket Streams 都复用共享的 `weex_common.websocket.BaseWebSocketClient`。当发送或接收因连接不可用而失败时，客户端会等待 `reconnect_delay`，自动重连，并重新订阅现有频道。

<a id="testing"></a>

## 测试

在仓库根目录运行：

```bash
python -m compileall ./common/src
python -m compileall ./clients/contract/src
```

说明：

- Contract 签名覆盖位于 [`./tests`](./tests/)。
- 示例程序位于 [`./examples`](./examples/)。
- 如果你为 Contract 包安装了测试依赖，请在 `./tests` 中运行本地测试。

<a id="migration-guide"></a>

## 迁移指南

如果你正从旧的独立版 `weex-contract-sdk` 布局升级：

- 对外公开的导入路径仍然是 `from weex_contract_sdk import Contract`。
- 共享运行时代码现在位于 `../../common`，因此在安装 Contract 包前必须先安装 `weex-common`。
- 这类范围说明，例如 batch order 的处理方式，会继续记录在本 README 中。

<a id="contributing"></a>

## 贡献

欢迎贡献。

由于本仓库包含生成型 SDK 代码，建议先创建 issue，再讨论 API 变更或与上游规范不一致的问题。

参与贡献时请遵循：

1. 将共享运行时改动放在 [`../../common`](../../common/README.zh-CN.md)。
2. 将 Contract 专属行为保留在 [`./src/weex_contract_sdk`](./src/weex_contract_sdk)。
3. 当公开接口发生变化时，同时更新 README、示例和测试。

<a id="license"></a>

## 许可证

许可详情请参阅 [LICENSE](../../LICENSE) 文件。

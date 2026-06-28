# GizmoGuide 部署与 Langfuse 追踪指南

## 前置条件

- Docker Desktop（Windows / macOS / Linux 均可）
- Git
- 一个 DeepSeek API Key（https://platform.deepseek.com）
- 一个博查搜索 API Key（https://open.bochaai.com）——可选，不提供则 web_search 工具不启用

## 快速启动（3 步）

```bash
# 1. 克隆仓库并进入目录
git clone <repo-url> && cd GizmoGuide

# 2. 创建环境变量文件，填入你的 API Key
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY 和 BOCHA_API_KEY

# 3. 启动全部服务（首次拉镜像约需 3-5 分钟）
docker compose up -d --build
```

等 Langfuse 健康检查通过（约 90s）后，**执行一次 MinIO bucket 初始化**：

```bash
bash setup/setup-minio-bucket.sh
```

完成后：
- 应用 API：http://localhost:8000
- Langfuse UI：http://localhost:3000（已自动创建账号和项目，见下方说明）

## 为什么需要 setup-minio-bucket.sh？

Langfuse v3 将 trace event 写入 S3 兼容存储（本项目用 MinIO）。MinIO 容器首次启动时 bucket 不存在，Langfuse 会报 `NoSuchBucket` 错误。此脚本创建 `langfuse` bucket，只需执行一次。如果执行了 `docker compose down -v`（清除 volume），需重新执行。

## Langfuse 自动初始化

`docker-compose.yml` 中通过 `LANGFUSE_INIT_*` 环境变量预配置了 Langfuse：

| 配置项 | 值 |
|---|---|
| 初始用户邮箱 | `908895368@qq.com` |
| 初始用户密码 | `908895368Cwh@` |
| 项目 ID | `default-project` |
| Public Key | `pk-lf-init` |
| Secret Key | `sk-lf-init` |

这些值已经写在 `.env.example` 中，复制后无需修改即可使用。如果你想换自己的 Langfuse 账号，登录 UI 创建新项目后，把新 key 填到 `.env` 的 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY`。

## 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | - | DeepSeek API Key，留空则 LLM 降级为 rule-based |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | 可改为兼容 OpenAI 格式的代理地址 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 模型名称 |
| `LLM_TIMEOUT_SECONDS` | 否 | `25` | LLM 调用超时 |
| `BOCHA_API_KEY` | 否 | - | 博查搜索 Key，留空则 web_search 工具不启用 |
| `AGENT_MAX_TOOL_ROUNDS` | 否 | `4` | 单轮对话工具调用上限 |
| `LANGFUSE_PUBLIC_KEY` | 否 | `pk-lf-init` | Langfuse 项目公钥 |
| `LANGFUSE_SECRET_KEY` | 否 | `sk-lf-init` | Langfuse 项目密钥 |
| `LANGFUSE_HOST` | 否 | `http://langfuse-web:3000` | Docker 内部地址，勿改为 localhost |

## 架构概览

```
docker compose（7 个服务）
├── app                 ← GizmoGuide FastAPI 应用（uvicorn + --reload）
├── langfuse-web        ← Langfuse v3 Web UI + API
├── langfuse-worker     ← Langfuse 后台 worker（处理 event 写入）
├── postgres            ← Langfuse 元数据
├── clickhouse          ← Langfuse trace 数据存储
├── redis               ← Langfuse 缓存 + 队列
└── minio               ← S3 兼容对象存储（存 trace event blob）
```

## 追踪覆盖范围

`app/tracing.py` 基于 **Langfuse Python SDK v4**（`start_as_current_observation()` API），利用 OpenTelemetry 上下文自动传播父子关系。覆盖：

- `gizmoguide_request`（ROOT span）— 完整请求，含 session_id / user_id
- `purchase_agent_chat` — Agent 主循环
- `agent_loop` — pydantic-ai agent run
- `agent_run` (GENERATION) — LLM 调用，记录 input messages / output / model / usage
- `web_search` — 博查搜索，记录 query、结果数量、前 3 条结果（标题 + 摘要 + URL）
- `product_lookup` — 商品查询
- `profile_extraction` — 用户画像提取
- `scoring_guardrail` — 评分护栏
- `fallback_chat` / `fallback_ll` — 降级路径

## 常见坑点

### 1. Windows Docker Desktop 代理问题

如果你在 Windows 宿主机上跑了代理软件（监听 `127.0.0.1:7890` 之类），容器内的 HTTPS 请求会 TLS 握手失败。因为容器内的 `127.0.0.1` 指向容器自身，不是宿主机。

`docker-compose.yml` 的 app 服务已配置了代理覆盖：

```yaml
environment:
  HTTP_PROXY: ""
  HTTPS_PROXY: ""
  http_proxy: ""
  https_proxy: ""
  NO_PROXY: "*"
```

如果你新增了其他需要出网的服务，也需要加上这些覆盖。

### 2. Langfuse 健康检查等待时间长

Langfuse web 首次启动需 60-90s（要跑 DB migration）。docker-compose 已配置 `start_period: 90s`。app 服务依赖 `langfuse-web: service_healthy`，所以 app 会在 Langfuse 就绪后才启动。

### 3. Langfuse SDK 版本

本项目使用 `langfuse>=4.12.0`。SDK v4 完全重构为 OpenTelemetry 架构，旧版 API（`trace()`, `span()`, `generation()`）已移除。网上很多教程还是旧版写法，不要照搬。正确用法：

```python
# v4 正确写法
with client.start_as_current_observation(
    name="my_span", as_type="span", input={...}
) as span:
    span.update(output={...})

# v2 旧写法（已废弃，会报 AttributeError）
trace = client.trace(name="my_trace")
span = trace.span(name="my_span")
```

### 4. Langfuse worker 镜像

Langfuse v3 使用独立 worker 镜像 `langfuse/langfuse-worker:3`，不是 `langfuse/langfuse:3`。后者没有 worker 入口，会报 `Cannot find module '/app/dist/worker/index.js'`。

### 5. ClickHouse 单节点配置

`clickhouse/config.d/config.xml` 配置了 embedded keeper（单机模式），让 ReplicatedMergeTree 表引擎能在单节点上工作。不要删除此文件。

### 6. MTU 网络设置

`docker-compose.yml` 底部配置了 `com.docker.network.driver.mtu: 1400`。某些网络环境下（VPN、云服务器）默认 MTU 1500 会导致大包丢包，1400 更稳定。

## 开发模式

app 服务挂载了当前目录为 volume（`volumes: - .:/app`），并启用了 `--reload`，所以修改代码后容器会自动重载，无需重新 build。

## 停止与清理

```bash
# 停止服务（保留数据）
docker compose down

# 停止并清除所有数据（需重新跑 setup-minio-bucket.sh）
docker compose down -v
```

## 验证追踪

```bash
# 发一个测试请求
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"推荐一款适合学生的笔记本电脑","session_id":"test-001"}'

# 然后打开 http://localhost:3000 查看 trace
```

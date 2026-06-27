# GizmoGuide

GizmoGuide 是一个电子产品导购 Agent。第一版聚焦**手机二选一对比推荐**：你先选两款候选手机，再像聊天一样告诉它预算、用途和顾虑，它会结合参数、规则评分和联网口碑，给出更适合你的那一款，并讲清理由、风险和可能反转结论的条件。

## 特性

- **对话式导购**：先给结构化基础对比，之后多轮问答补充需求，像懂手机的朋友一样沟通。
- **联网证据**：通过博查（Bocha）Web Search 工具实时查询口碑、评测、续航实测、维修与价格线索，并把结果揉进回答。
- **pydantic-ai 编排**：Agent 的工具循环、tool schema、参数校验、调用对齐由 [pydantic-ai](https://ai.pydantic.dev/) 负责，业务代码只管工具实现和降级策略。
- **三档降级**：根据可用的 API Key 自动选择运行模式，缺 Key 也能跑（见下文）。
- **规则评分护栏**：本地评分引擎作为后台护栏与兜底，避免模型给出离谱推荐。
- **零构建前端**：纯 HTML/CSS/JS，由后端在 `/ui/` 直接伺服，无需 Node 构建。

## 运行模式（三档降级）

应用启动时按 `.env` 里的 Key 自动决定走哪条链路：

| 条件 | 链路 | 说明 |
| --- | --- | --- |
| 同时配置 DeepSeek + 博查 Key | pydantic-ai 联网 Agent | 模型自主决定搜什么、搜几次，结合真实证据作答 |
| 仅配置 DeepSeek Key | 单次 LLM 调用 | 不联网，基于参数与规则评分作答 |
| 都未配置 | 本地规则兜底 | 不调用大模型，纯规则评分 + 模板话术 |

## 环境要求

- Python >= 3.11

## 安装

```bash
pip install -r requirements.txt
```

建议使用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 配置

从模板创建 `.env`：

```bash
cp .env.example .env
```

主要配置项：

| 变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek（或任意 OpenAI 兼容服务）的 Key，留空则不调用大模型 |
| `DEEPSEEK_BASE_URL` | LLM 服务地址，默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名，默认 `deepseek-chat` |
| `BOCHA_API_KEY` | 博查 Web Search 的 Key，留空则不启用联网搜索。到 [open.bochaai.com](https://open.bochaai.com) 注册后在「API KEY 管理」创建 |
| `WEB_SEARCH_CACHE_TTL_SECONDS` | 联网搜索结果缓存时长（秒），默认 6 小时 |
| `AGENT_MAX_TOOL_ROUNDS` | 单轮对话里 Agent 调用工具的最大轮数护栏，防止死循环/超额消耗 |

> `.env` 已在 `.gitignore` 中，不会进入版本库，Key 不会泄露。

## 启动

```bash
uvicorn app.main:app --reload
```

启动后访问：

- 前端界面：<http://127.0.0.1:8000/ui/>（访问根路径 `/` 会自动跳转到这里）
- 健康检查：<http://127.0.0.1:8000/health>
- 接口文档（Swagger）：<http://127.0.0.1:8000/docs>

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | 多轮对话主接口，支持 `session_id` 维持上下文 |
| `POST` | `/recommend` | 单次推荐接口（无状态，内部复用对话逻辑） |
| `GET` | `/products` | 获取 mock 商品库 |
| `GET` | `/health` | 健康检查 |

`POST /chat` 请求示例：

```json
{
  "session_id": "demo-1",
  "message": "预算5000，主要拍照和日常用，想用三年，也在意维修",
  "candidate_products": ["iPhone 15", "vivo X100"]
}
```

`POST /recommend` 请求示例：

```json
{
  "user_message": "预算5000，主要拍照和日常用，想用三年，也在意维修",
  "candidate_products": ["iPhone 15", "vivo X100"]
}
```

## 测试

```bash
pytest
```

## 目录结构

```text
GizmoGuide/
├── app/
│   ├── main.py            # FastAPI 入口，挂载路由与前端静态资源
│   ├── api/               # 路由层：chat / recommend / products
│   ├── agent/             # Agent 编排、pydantic-ai 封装、LLM 客户端、prompt
│   ├── tools/             # 工具：联网搜索、商品查询、规则评分
│   ├── decision/          # 规则评分引擎与权重
│   ├── orchestrator/      # 对话编排与用户画像提取
│   ├── connectors/        # mock 商品数据接入
│   ├── schemas/           # Pydantic 数据模型
│   ├── config/            # 配置与 .env 加载
│   └── data/              # mock 商品库 JSON
├── frontend/              # 零构建前端，由后端在 /ui/ 伺服
├── tests/                 # 单元测试
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## 说明与限制

- 商品库目前为 `app/data/mock_products.json` 的 **mock 数据**，参数仅供演示。
- 联网搜索返回的是摘要片段，负责口碑「广度」；深度统计（如某平台大量评论的情感分布）需后续接入专门的数据源。
- 联网模式下回复需要真实发起多次搜索再综合，响应通常需要数秒到十几秒，属正常现象。
- 搜索结果缓存为进程内存，重启服务即清空；如需持久化可替换为 Redis，工具接口无需改动。

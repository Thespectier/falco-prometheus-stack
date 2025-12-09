# 系统架构模块说明文档

## 分层总览（最终）
- 运行时事件层：Falco、日志采集 Agent（DockerLogQueue）
- 行为建模层：Hanabi Worker（解析/画像/检测）
- 数据服务层：Prometheus Metrics Exporter、Prometheus TSDB、HBT 快照存储/缓存
- 应用层：API Gateway（FastAPI，REST + SSE）、前端控制台（React + TS + Vite）、Grafana（选配）

## 1. 模块功能说明

### 1.1 Falco Daemon
- 核心职责：采集容器/主机运行时系统调用事件，按照规则评估并输出结构化 JSON 日志；暴露健康检查与内嵌 webserver。
- 关键业务流程/数据流：内核事件 → Falco 驱动（modern_ebpf） → 规则匹配（`custom_rules.yaml`） → `output_fields` JSON（stdout）。
- 输入接口：内核 syscall 流；容器运行时元数据（container 插件）。
- 输出接口：JSON 日志（stdout）；`/healthz` 与 webserver；配置文件 `falco.yaml`、规则文件 `custom_rules.yaml`。

### 1.2 Hanabi Worker
- 核心职责：事件解析与分类、HBT 容器画像构建；预热/检测切换；检测期语义匹配一致性校验；产出告警候选与快照。
- 关键业务流程/数据流：
  - `DockerLogQueue` 增量消费 Falco stdout → `EventParser` 提取字段与分类 → `HBTBuilder` 路由到进程/网络/文件分支 → `BranchHandlers` 增量更新树节点计数与元数据。
  - 预热期：学习画像路径；检测期：进行语义匹配（命令参数、网络属性、文件路径）差异校验，形成告警候选。
- 输入接口：Falco JSON 行事件（带 `output_fields`）。
- 输出接口：HBT 快照（TreeNode JSON）；告警候选（结构化对象）；统计数据（事件速率、学习状态）。

### 1.3 Prometheus Exporter
- 核心职责：将事件与告警转化为时序指标，暴露 `/metrics` 供 Prometheus 抓取。
- 关键业务流程/数据流：消费事件 → 生成计数器与时间戳 Gauge → Prometheus 采集。
- 输入接口：事件对象（含 `output_fields`）；Hanabi 告警候选。
- 输出接口：
  - `syscall_events_total{rule,priority,container_name,image_repository,process_name,k8s_namespace,k8s_pod,rule_category}`
  - `syscall_last_event_timestamp_seconds{container_name}`
  - `security_alerts_total{container_name,rule,priority,source}`（设计新增，用于告警聚合）。

### 1.4 Prometheus TSDB
- 核心职责：时序指标存储、查询与聚合（PromQL）；作为后端与前端的统一数据源。
- 关键业务流程/数据流：定时抓取 Exporter `/metrics` → TSDB 存储 → PromQL 查询 → API 返回。
- 输入接口：Exporter 暴露的指标。
- 输出接口：Prometheus HTTP API（PromQL 查询结果）。

### 1.5 API Gateway
- 核心职责：统一 REST 与实时流接口；封装 PromQL；聚合日志与告警数据；提供画像快照访问。
- 关键业务流程/数据流：请求参数（容器ID/时间范围/优先级）→ PromQL 查询 → 结果聚合与缓存 → JSON 响应；订阅告警与事件流做实时推送。
- 输入接口：Prometheus HTTP API；Hanabi 快照读取；内部缓存。
- 输出接口：
  - `GET /api/containers`（容器列表与速率/最新时间）
  - `GET /api/containers/{id}/logs?start&end&limit`（结构化事件）
  - `GET /api/containers/{id}/alerts?start&end`（告警列表与聚合）
  - `GET /api/overview`（总体统计与分布）
  - `GET /api/hbt/{id}`（HBT 树快照 JSON）
  - `GET /api/stream/{id}`（SSE；WebSocket 按需）

### 1.6 前端控制台
- 核心职责：总览页面与两分页视图；支持容器 ID 查询、时间范围筛选、优先级过滤、实时订阅；展示 HBT 画像侧栏。
- 关键业务流程/数据流：调用 API 获取数据与订阅流，渲染指标卡片、图表、表格与画像；提供告警确认与备注等交互。
- 输入接口：API JSON；SSE（WebSocket 按需）流。
- 输出接口：用户交互动作（筛选、确认告警、导出报表）。

### 1.7 HBT 快照存储/缓存
- 核心职责：存储容器画像快照与少量告警明细，提高查询性能与用户体验。
- 输入接口：Hanabi 写入快照与告警明细。
- 输出接口：API 读取快照与明细（分页）。

---

## 2. 模块存在必要性

- Falco Daemon
  - 需求与问题：提供可靠的运行时事件来源与规则评估。
  - 缺失影响：无事件输入，系统无法监控、无法告警。
  - 业务/技术价值：统一字段格式与高性能采集，奠定全链路数据质量。

- Hanabi Worker
  - 需求与问题：将原始事件转为有意义的行为画像与异常检测逻辑。
  - 缺失影响：缺少上下文与层次化分析，告警噪声高且不可解释。
  - 业务/技术价值：容器画像与精准告警，支持可视化与后续智能分析扩展。

- Prometheus Exporter/TSDB
  - 需求与问题：标准化指标与历史趋势查询。
  - 缺失影响：无法聚合与观察态势，Grafana/报表与阈值告警依赖失效。
  - 业务/技术价值：支持监控面板、趋势分析与容量规划；行业标准生态。

- API Gateway/前端控制台
  - 需求与问题：统一访问入口与产品化体验。
  - 缺失影响：数据不可用/不可查询，难以运营与处置。
  - 业务/技术价值：提升可用性与交互效率，支撑多角色协作与审计。

- HBT 快照存储/缓存
  - 需求与问题：降低实时重建开销与接口延迟。
  - 缺失影响：高并发下响应慢，用户体验差。
  - 业务/技术价值：性能优化与数据资产沉淀，支撑跨时段对比分析。

---

## 3. 模块间关系

### 3.1 调用层级关系（分层架构，最终）
- 运行时事件层：Falco、日志采集 Agent
- 行为建模层：Hanabi（解析/画像/检测）
- 数据服务层：Exporter、Prometheus TSDB、HBT 快照/缓存
- 应用层：API Gateway（FastAPI，REST + SSE）、前端控制台（React + TS + Vite）、Grafana（选配）

### 3.2 交互方式
- Falco → Hanabi：异步流（stdout）、事件驱动。
- Hanabi → Exporter：近实时事件/告警视图映射，Exporter 暴露 HTTP `/metrics`。
- Exporter → Prometheus：拉取式（Prometheus scrape）。
- API → Prometheus：同步 HTTP（PromQL 查询）。
- API → 前端：同步 REST + 异步 SSE 实时推送（WebSocket 按需）。
- API → HBT 存储：同步读写（内存缓存/对象存储）。

### 3.3 数据流向与依赖
- 事件来源：Falco → Hanabi → Exporter → Prometheus → API/前端。
- 画像数据：Hanabi → HBT 存储 → API → 前端。
- 告警数据：Hanabi → Exporter（告警计数）/告警明细存储 → API → 前端。

### 3.4 耦合度与通信协议
- Hanabi ↔ Falco：弱耦合，stdout JSON 字段契约。
- Exporter ↔ Prometheus：弱耦合，Prometheus exposition 格式。
- API ↔ Prometheus：弱耦合，HTTP/PromQL。
- 前端 ↔ API：弱耦合，HTTP/JSON + SSE/WebSocket。
- API ↔ HBT 存储：中低耦合，读写契约与快照格式（TreeNode JSON）。

---

## 4. 架构设计原则

- 单一职责：采集/解析/指标/查询/展示分离，模块内高内聚。
- 低耦合：跨模块通过标准协议与数据契约交互（JSON、HTTP、SSE、Prometheus）。
- 可扩展性：
  - Hanabi 支持替换语义匹配模型与规则集；worker 可水平扩容按容器分片。
  - 指标维度与 PromQL 模板可增删；前端分页与图表可配置。
- 可维护性：清晰模块边界与接口契约；统一观测指标与健康检查；缓存与快照策略优化性能。
- 性能与可靠性：增量消费、队列背压、标签基数控制、查询窗口规范化（5m/15m）、降采样与批量合并；故障隔离与降级策略。

---

## 5. 与代码仓库的映射
- Falco：`falco/falco.yaml`、`falco/custom_rules.yaml`
- Hanabi：`hanabi/models/*.py`、`hanabi/utils/queue.py`、`hanabi/utils/timeCount.py`
- Prometheus：`prometheus/exporter.py`、`prometheus/prometheus.yml`
- 应用层：`api/README.md`（FastAPI 结构规划）、`web/README.md`（前端结构规划）
- 文档与图：`docs/architecture-4layer.svg`、`docs/tech-stack.md`、`docs/backend-api-contract.md`、`docs/interfaces/openapi.yaml`、`docs/frontend-setup.md`、`docs/sse-envelope.md`、`docs/promql-templates.md`、`docs/test-plan.md`、`docs/roadmap.md`
- 其他：`grafana/dashboard.json`、`docker-compose.yml`、`docker-compose.app.yml`

---

## 6. 统一参数与 SSE 约定（最终）
- REST 统一参数：`container_id`、`start`、`end`、`limit`、`priority`
- SSE Envelope：`type`（event|alert|heartbeat）、`ts`（ISO8601）、`container`、`payload`
- 心跳与重连：心跳 30s；客户端 90s 无心跳视为断线；指数退避重连（最大 30s）

---

## 7. 技术栈（最终）与版本要求
- 后端：FastAPI + Uvicorn；PromQL 通过 `httpx`；SSE（StreamingResponse）；内存 TTL 缓存；Python ≥ 3.14
- 前端：React 18 + TypeScript + Vite；Ant Design；React Router；TanStack Query；TanStack Table + `@tanstack/react-virtual`；ECharts；Zustand；Vitest；ESLint/Prettier
- 可视化复用：Grafana 嵌入与应用内 ECharts 并存

---

## 8. 参考查询（PromQL 模板）
- 总速率：`sum(rate(syscall_events_total[5m]))`
- 按优先级：`sum by(priority) (rate(syscall_events_total[5m]))`
- 按分类：`sum by(rule_category) (rate(syscall_events_total[5m]))`
- 最新时间：`max(syscall_last_event_timestamp_seconds)`
- 某容器速率：`sum(rate(syscall_events_total{container_name="$id"}[5m]))`
- 告警速率：`sum by(rule,priority) (rate(security_alerts_total{container_name="$id"}[5m]))`

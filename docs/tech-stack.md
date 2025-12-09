# Web 应用技术栈选型说明（最终版）

## 选型目标
- 满足实时数据（SSE/WebSocket）、高并发 PromQL 查询、丰富图表与数据表展示、HBT 树可视化、良好可维护性与扩展性。
- 保留 Python 版本要求：`>=3.14`。

## 前端选型（最终）
- 框架与工具：React 18 + TypeScript + Vite；UI：Ant Design；路由：React Router。
- 服务器状态：TanStack Query（请求/缓存/重试/分页/并发）。
- 本地状态：Zustand。
- 数据表：TanStack Table + `@tanstack/react-virtual`。
- 图表与画像：Apache ECharts（含 Tree/Graph，统一图表与 HBT 可视化）。
- 实时通信：SSE（封装 `useEventSource`，心跳、断线重连与批量合并刷新）。
- 测试与质量：Vitest + React Testing Library；ESLint + Prettier + TS 严格模式。

## 后端选型（最终）
- FastAPI + Uvicorn。
- Prometheus 查询：使用 `httpx` 调用 Prometheus HTTP API（`/api/v1/query_range`）；统一 5m/15m 窗口与结果缓存策略。
- 实时通道：SSE（`StreamingResponse`）。
- 缓存：内存 LRU/TTL（PromQL 结果）。
- 鉴权与治理：JWT/Token、RBAC（命名空间/容器维度）、限流与审计。
- 可观测：API 自指标（耗时、错误率、SSE连接数）暴露到 Prometheus；健康探针。

## 集成契约（摘要）
- API 路由：`/api/containers`、`/api/containers/{id}/logs`、`/api/containers/{id}/alerts`、`/api/overview`、`/api/hbt/{id}`、`/api/stream/{id}`。
- 前端数据层：`useOverviewQuery`、`useContainerLogsQuery`、`useAlertsQuery`、`useHbtQuery`；`useEventSource`（SSE）。
- PromQL 模板：统一 5m/15m 窗口；标签维度控制（容器/规则/优先级/分类）。

## 性能与可靠性
- 虚拟滚动、懒加载与分页（日志/告警）。
- SSE 背压与批量合并（如 500ms 刷新）。
- 断线重连与指数退避（SSE/WebSocket）。
- 查询结果缓存与降采样；标签基数治理。

## 最终结论
- 前端：React + TypeScript + Vite + Ant Design + TanStack Query + TanStack Table + ECharts。
- 后端：FastAPI + Uvicorn；保留 Python `>=3.14`。
- 可视化：嵌入 Grafana 面板，与应用内 ECharts 并存。

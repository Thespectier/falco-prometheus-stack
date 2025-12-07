# Web 应用技术栈选型说明

## 选型目标
- 满足实时数据（SSE/WebSocket）、高并发 PromQL 查询、丰富图表与数据表展示、HBT 树可视化、良好可维护性与扩展性。

## 前端选型（推荐：React 18 + TypeScript + Vite）
- 理由：
  - 生态成熟：图表（ECharts）、数据表（AG Grid/TanStack Table）、状态管理（Zustand/Redux）、请求缓存（TanStack Query）。
  - 类型安全：TypeScript 强约束，长期维护更可靠。
  - 实时支持：原生 EventSource 与成熟 WebSocket 生态；虚拟滚动与性能优化方案丰富。
- 组件与库：
  - UI：Ant Design 或 MUI
  - 路由：React Router
  - 数据层：TanStack Query（缓存/重试/分页）；Zustand 或 Redux Toolkit（局部状态）
  - 图表：Apache ECharts（含 Tree 图，用于 HBT 画像）
  - 数据表：AG Grid（社区版）或 TanStack Table + 虚拟滚动
  - 测试：Vitest + React Testing Library
  - 质量：ESLint + Prettier + TypeScript 严格模式
- 页面结构：
  - 总览页：指标卡片、优先级/分类分布、Top 规则；容器与时间范围筛选。
  - 容器日志页：可筛选表格、实时 SSE 追加、HBT 树侧栏。
  - 告警信息页：告警列表、趋势与 TopN、操作（确认/备注），实时订阅。

## 前端备选
- Vue 3 + TypeScript：上手快、生态完整；但复杂数据表与 TS 体验略逊。
- SvelteKit：轻量与性能好；生态与团队熟悉度存在风险，不推荐用于企业级控制台首期。

## 后端选型（API 网关）
- 推荐：FastAPI + Uvicorn
  - 理由：类型契约（Pydantic）、高性能 ASGI、原生 WebSocket 与 SSE 友好、路由清晰。
  - Prometheus 查询：HTTP API（`/api/v1/query_range`），使用 `httpx`；结果缓存（5m/15m 窗口）。
  - SSE：`StreamingResponse` 实现事件与告警实时推送；心跳与断线重连。
- 备选：Flask（仓库已有依赖）
  - 快速起步；WebSocket/SSE 需额外库，类型契约弱；中大型项目维护成本偏高。

## 集成契约
- API 路由：`/api/containers`、`/api/containers/{id}/logs`、`/api/containers/{id}/alerts`、`/api/overview`、`/api/hbt/{id}`、`/api/stream/{id}`
- 前端数据层：`useOverviewQuery`、`useContainerLogsQuery`、`useAlertsQuery`、`useHbtQuery`；`useEventSource`
- PromQL 模板：统一 5m/15m 窗口；标签维度控制（容器/规则/优先级/分类）。

## 性能与可靠性
- 虚拟滚动、懒加载与分页（日志/告警）
- SSE 背压与批量合并（500ms 刷新）
- 断线重连与指数退避（SSE/WebSocket）
- 查询结果缓存与降采样

## 最终结论
- 前端优选：React + TypeScript + Vite + Ant Design + TanStack Query + AG Grid + ECharts
- 后端优选：FastAPI + Uvicorn（或 Flask 作为备选）
- 可视化复用：支持嵌入既有 Grafana 面板，与应用内 ECharts 图表共存

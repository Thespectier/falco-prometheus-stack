# Beta 里程碑 Issues（可复制至 GitHub）

---

**标题**: [P2][Beta][api] 鉴权与 RBAC（JWT/命名空间/容器）  
**Labels**: type:task, module:api, priority:P2, milestone:Beta

**Scope**
- JWT/Token 中间件；命名空间/容器级授权策略
- 限流与审计日志（关键接口）

**Acceptance (SMART)**
- 未授权访问全部阻断；审计条目完整可查
- 策略与配置文档齐备

**KPIs**
- 未授权阻断率 = 100%；误阻断率 ≤ 0.1%

**Dependencies**
- 基础路由完成

**Estimate**
- 1 人 / 4 天

**Links**
- docs/backend-api-contract.md

---

**标题**: [P2][Beta][api] 可观测与健康探针（耗时/错误率/SSE连接数）  
**Labels**: type:task, module:api, priority:P2, milestone:Beta

**Scope**
- 导出自指标：请求耗时、错误率、SSE连接数
- 健康探针路由；Grafana 面板对齐

**Acceptance (SMART)**
- 面板数据完整；告警规则生效

**KPIs**
- 错误率 ≤ 0.1%；面板可用率 ≥ 99.9%

**Dependencies**
- 路由完成

**Estimate**
- 1 人 / 2 天

**Links**
- docs/roadmap.md

---

**标题**: [P2][Beta][data] HBT 快照存储接口（读写与分页）  
**Labels**: type:task, module:data, priority:P2, milestone:Beta

**Scope**
- 快照读写契约；最近 N 条告警明细分页

**Acceptance (SMART)**
- 查询延迟 ≤ 100ms（内存缓存场景）；契约文档齐备

**KPIs**
- 分页 p95 ≤ 200ms

**Dependencies**
- Hanabi 输出稳定

**Estimate**
- 1 人 / 3 天

**Links**
- docs/system-architecture.md

---

**标题**: [P2][Beta][frontend] 容器日志分页与 HBT 侧栏（联动）  
**Labels**: type:task, module:frontend, priority:P2, milestone:Beta

**Scope**
- 虚拟滚动表格与实时 SSE 追加
- HBT 树展示；告警→日志联动跳转

**Acceptance (SMART)**
- 滚动流畅；联动正确；首屏 ≤ 2.5s

**KPIs**
- 滚动卡顿 < 100ms

**Dependencies**
- 日志接口与 SSE 可用

**Estimate**
- 1 人 / 5 天

**Links**
- docs/frontend-setup.md

---

**标题**: [P2][Beta][frontend] 公共组件与测试（Query/ECharts/SSE/单测）  
**Labels**: type:task, module:frontend, priority:P2, milestone:Beta

**Scope**
- 封装 TanStack Query、ECharts、`useEventSource`
- Vitest + RTL 单测补齐

**Acceptance (SMART)**
- 单测覆盖 ≥ 75%；组件复用性良好

**KPIs**
- 构建时间 ≤ 60s

**Dependencies**
- 页面基础完成

**Estimate**
- 1 人 / 4 天

**Links**
- docs/test-plan.md

---

**标题**: [P2][Beta][devops] CI/CD 草案完善（前端/后端流水线与门禁）  
**Labels**: type:task, module:devops, priority:P2, milestone:Beta

**Scope**
- 前端 lint/test/build；后端 ruff/pytest；镜像构建草案
- 合并门槛（测试通过、文档更新、契约不破坏）

**Acceptance (SMART)**
- 目录变更触发；流程稳定通过

**KPIs**
- CI 失败率 ≤ 5%

**Dependencies**
- 工程结构稳定

**Estimate**
- 0.5 人 / 2 天

**Links**
- .github/workflows/*.yml

---

**标题**: [P2][Beta][data] Prometheus 抓取与窗口对齐  
**Labels**: type:task, module:data, priority:P2, milestone:Beta

**Scope**
- `prometheus.yml` 抓取间隔与 5m/15m 窗口对齐

**Acceptance (SMART)**
- 查询与抓取配置一致；面板可用

**KPIs**
- 抓取错误率 ≤ 0.1%

**Dependencies**
- Exporter 稳定

**Estimate**
- 0.5 人 / 2 天

**Links**
- docs/promql-templates.md

---

**标题**: [P2][Beta][frontend] Grafana 嵌入统一（总览页）  
**Labels**: type:task, module:frontend, priority:P2, milestone:Beta

**Scope**
- 总览页 iframe 嵌入既有面板；统一色板与时间窗口

**Acceptance (SMART)**
- 嵌入稳定；数据一致；交互无阻塞

**KPIs**
- 首屏 p95 ≤ 2.5s

**Dependencies**
- TSDB 面板可用

**Estimate**
- 0.5 人 / 2 天

**Links**
- docs/roadmap.md

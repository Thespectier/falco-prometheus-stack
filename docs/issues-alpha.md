# Alpha 里程碑首批 Issues（可复制至 GitHub）

---

**标题**: [P1][Alpha][data] Exporter 告警视图与标签治理  
**Labels**: type:task, module:data, priority:P1, milestone:Alpha

**Scope**
- 统一 `security_alerts_total{container_name,rule,priority,source}`
- 标签白名单与基数控制策略（限制高基数维度）

**Acceptance (SMART)**
- PromQL 告警聚合稳定；查询结果与契约一致
- 输出标签与白名单对齐，基数监控面板可用

**KPIs**
- 告警聚合命中率 ≥ 95%
- 标签基数维持在阈值内；错误率 ≤ 0.1%

**Dependencies**
- Hanabi 告警候选视图（结构化对象）

**Estimate**
- 1 人 / 2 天

**Links**
- docs/roadmap.md（任务5）
- docs/promql-templates.md

---

**标题**: [P1][Alpha][data] PromQL 告警模板与 TTL 缓存  
**Labels**: type:task, module:data, priority:P1, milestone:Alpha

**Scope**
- 告警趋势与 TopN 模板（统一 5m/15m）
- TTL 缓存与命名规范（基于 Query Key）

**Acceptance (SMART)**
- 趋势与 TopN 查询 p95 ≤ 600ms（未命中）
- 缓存命中查询 p95 ≤ 300ms；错误处理与降级策略生效

**KPIs**
- 缓存命中率 ≥ 70%
- 查询错误率 ≤ 0.1%

**Dependencies**
- TSDB（Prometheus）与 Exporter 稳定

**Estimate**
- 1 人 / 3 天

**Links**
- docs/promql-templates.md

---

**标题**: [P1][Alpha][api] 告警路由与聚合接口  
**Labels**: type:task, module:api, priority:P1, milestone:Alpha

**Scope**
- `GET /api/containers/{id}/alerts?start&end&priority`
- 总览告警聚合接口（态势卡片与趋势数据）

**Acceptance (SMART)**
- OpenAPI 契约一致；参数校验与错误码规范完整
- 响应 p95 ≤ 300ms（缓存命中）

**KPIs**
- 接口错误率 ≤ 0.1%
- 接口成功率 ≥ 99.9%

**Dependencies**
- PromQL 模板与缓存（告警相关）

**Estimate**
- 1 人 / 4 天

**Links**
- docs/backend-api-contract.md
- docs/interfaces/openapi.yaml

---

**标题**: [P1][Alpha][api] SSE 告警优先策略（优先队列 + 合并）  
**Labels**: type:task, module:api, priority:P1, milestone:Alpha

**Scope**
- `/api/stream/{id}` 内部优先队列与 500ms 批量合并策略（告警优先）
- 心跳与断线重连（指数退避 ≤ 30s）

**Acceptance (SMART)**
- 告警到达优先于事件；端到端延迟 ≤ 800ms
- 保活 ≥ 1h；重连成功率 ≥ 99%

**KPIs**
- SSE 保活与重连达标；事件丢失率=0

**Dependencies**
- 告警视图（Exporter/TSDB 可用）

**Estimate**
- 1 人 / 2 天

**Links**
- docs/sse-envelope.md

---

**标题**: [P1][Alpha][frontend] 告警信息分页（列表/趋势/TopN/确认）  
**Labels**: type:task, module:frontend, priority:P1, milestone:Alpha

**Scope**
- 列表（过滤/排序/分页）、趋势与 TopN 图表
- 告警确认与备注交互；首屏性能优化

**Acceptance (SMART)**
- 首屏 ≤ 2s；SSE 推送延迟 ≤ 800ms
- 交互成功率 ≥ 99.9%；错误率 ≤ 0.1%

**KPIs**
- 页面错误率 ≤ 0.1%
- 交互成功率与响应时间达标

**Dependencies**
- 告警接口与 SSE 优先策略

**Estimate**
- 1 人 / 6 天

**Links**
- docs/frontend-setup.md

---

**标题**: [P1][Alpha][frontend] 总览页面（告警态势优先）  
**Labels**: type:task, module:frontend, priority:P1, milestone:Alpha

**Scope**
- 告警态势卡片、趋势图；事件分布与 TopN 辅助

**Acceptance (SMART)**
- 首屏 ≤ 2s；图表加载与交互流畅
- 与后端契约一致；异常处理到位

**KPIs**
- 首屏 p95 ≤ 2s；交互无阻塞

**Dependencies**
- 告警聚合接口

**Estimate**
- 1 人 / 4 天

**Links**
- docs/roadmap.md

---

**标题**: [P1][Alpha][api] 日志路由基础（不影响告警）  
**Labels**: type:task, module:api, priority:P1, milestone:Alpha

**Scope**
- `GET /api/containers/{id}/logs?start&end&limit`
- 保证与告警路由无性能互斥

**Acceptance (SMART)**
- 表格加载流畅；参数校验与错误码规范
- p95 ≤ 600ms（未命中）

**KPIs**
- 接口错误率 ≤ 0.1%；响应时间达标

**Dependencies**
- PromQL 封装（基础）

**Estimate**
- 1 人 / 3 天

**Links**
- docs/backend-api-contract.md

---

**标题**: [P1][Alpha][devops] Compose 联调环境（合并启动说明）  
**Labels**: type:task, module:devops, priority:P1, milestone:Alpha

**Scope**
- 合并 `docker-compose.yml` 与 `docker-compose.app.yml`
- 联调启动与连接说明（TSDB、API、前端）

**Acceptance (SMART)**
- 一键启动联调；说明文档齐备
- 启动失败率 ≤ 1%

**KPIs**
- 联调成功率 ≥ 99%

**Dependencies**
- API/前端占位结构

**Estimate**
- 0.5 人 / 2 天

**Links**
- docker-compose.app.yml
- docs/roadmap.md

---

**标题**: [P1→P2][Alpha→Beta][qa] 测试计划与用例执行（单测/集成/性能）  
**Labels**: type:task, module:qa, priority:P1, milestone:Alpha

**Scope**
- 编写并执行单测/集成/性能用例；Beta 阶段扩充与回归
- 告警相关性能与稳定性用例优先保障

**Acceptance (SMART)**
- Alpha ≥ 60% 覆盖；Beta ≥ 75%；RC ≥ 85%
- 缺陷收敛与回归通过

**KPIs**
- 缺陷漏检率 ≤ 5%

**Dependencies**
- 各模块接口与页面完成

**Estimate**
- QA 1 人 / 贯穿

**Links**
- docs/test-plan.md

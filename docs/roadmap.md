# 技术开发路线图（Alpha/Beta/RC）

## 阶段目标
- Alpha：端到端闭环与核心页面上线，SSE 基本稳定，性能达 Alpha 阈值
- Beta：性能与 RBAC、Grafana 嵌入、全面测试与文档完善
- RC：压测与安全审查、发布与回滚演练、问题收敛

## KPI 指标
- API p95：Alpha ≤ 800ms，Beta ≤ 600ms，RC ≤ 200ms（缓存命中）
- SSE 延迟：Alpha ≤ 2s，Beta ≤ 1.5s，RC ≤ 1s
- 首屏加载：Alpha ≤ 3s，Beta ≤ 2.5s，RC ≤ 2s
- 单测覆盖：≥ 60% / ≥ 75% / ≥ 85%；集成用例：≥ 30 / ≥ 60 / ≥ 100

## 时间线（示例周划分）
- W1-W2：后端路由与 PromQL 封装、SSE 基本通道、前端总览框架
- W3-W4：日志分页与 HBT 侧栏、告警分页、RBAC 与可观测、快照存储
- W5：联调与性能优化、Grafana 嵌入、Alpha 发布与反馈
- W6-W7：缺陷修复与功能增强、Beta 发布
- W8：压测与安全审查、RC 发布准备

## 甘特图（ASCII）
```
后端API   |■■■■■■■■■■|■■■■■■■■|■■■|
PromQL封装|■■■■■■■■■■|        |   |
前端总览   |■■■■■■■■  |        |   |
日志/告警  |    ■■■■■■■■■■■■|   |
SSE通道    |■■■■■      |  ■■   |   |
RBAC/观测  |      ■■■■■■|  ■■   |   |
快照存储   |      ■■■■  |  ■■   |   |
联调/优化  |            |■■■■■■■|■■ |
发布Alpha  |            |   ■    |   |
发布Beta   |                 ■     |
发布RC     |                      ■ |
```

## 交付物
- 接口契约（OpenAPI）、SSE envelope、PromQL 模板、测试计划、发布说明

---

## 告警优先版任务拆解（附加）

### 目标与KPI
- 告警列表加载 p95 ≤ 300ms（缓存命中），实时推送延迟 ≤ 800ms
- 告警确认/备注成功率 ≥ 99.9%；交互错误率 ≤ 0.1%
- 告警趋势与 TopN p95 ≤ 600ms（未命中 ≤ 900ms）

### 里程碑（调整）
- Alpha：告警分页与 SSE 告警流优先上线；总览突出告警态势
- Beta：告警交互完善与日志联动；性能与降级策略优化
- RC：压测、安全审查与发布回滚演练；告警相关 P1=0

### 任务清单（模块/优先级/估时/验收）
- 数据服务层（P1）：Exporter 告警视图治理（1人/2天；聚合稳定）
- 数据服务层（P1）：PromQL 告警模板与缓存（1人/3天；趋势/TopN达标）
- 应用后端（P1）：告警路由与聚合（1人/4天；p95≤300ms）
- 应用后端（P1）：SSE 告警优先策略（1人/2天；≤800ms）
- 应用前端（P1）：告警分页页面（1人/6天；首屏≤2s、交互成功率≥99.9%）
- 应用前端（P1）：总览告警优先展示（1人/4天；首屏≤2s）
- 运行时/建模（P2）：Hanabi 告警候选稳定（1人/4天；准确率≥90%）
- DevOps/QA（P1→P2）：联调脚本与测试用例（贯穿）

### 风险与缓解
- 资源争抢：内部优先队列与批量合并；提升缓存命中率
- 峰值抖动：降级策略（降低推送频率、窗口扩展）

---

## 完整开发任务拆解（按模块/优先级/里程碑）

### 运行时事件层
- 任务1 Falco规则与输出字段校准
  - Module: runtime; Milestone: Alpha; Priority: P1
  - Scope: 校准 evt/proc/fd/container/k8s 字段；覆盖示例场景
  - Acceptance: 字段契约匹配率≥95%，变更文档齐备
  - KPIs: 采集场景覆盖≥90%; Dependencies: 无; Estimate: 0.5人/2天
- 任务2 日志采集Agent稳定性核查
  - Module: runtime; Milestone: Alpha; Priority: P2
  - Scope: 队列背压/超时策略；错误统计与告警
  - Acceptance: 高吞吐压测无阻塞/丢失
  - KPIs: 峰值丢失率=0；阻塞≤100ms; Dependencies: Falco输出稳定; Estimate: 0.5人/2天

### 行为建模层（Hanabi）
- 任务3 画像构建与状态指标化
  - Module: modeling; Milestone: Alpha; Priority: P1
  - Scope: 预热/检测状态、事件速率/异常计数指标化
  - Acceptance: 状态切换正确；指标在TSDB可查询
  - KPIs: 状态切换延迟≤500ms；速率误差≤5%; Dependencies: 采集Agent; Estimate: 1人/4天
- 任务4 异常事件标注策略强化
  - Module: modeling; Milestone: Beta; Priority: P2
  - Scope: 命令参数/网络属性/文件路径语义不一致检测；置信度阈值
  - Acceptance: 准确率≥90%，误报≤5%
  - KPIs: P/R/F1 达标; Dependencies: 画像完成; Estimate: 1人/4天

### 数据服务层
- 任务5 Exporter告警视图与标签治理
  - Module: data; Milestone: Alpha; Priority: P1
  - Scope: 统一 `security_alerts_total{container_name,rule,priority,source}`；标签白名单与基数控制
  - Acceptance: 告警聚合稳定；标签基数受控
  - KPIs: 告警聚合命中率≥95%; Dependencies: Hanabi告警候选; Estimate: 1人/2天
- 任务6 PromQL告警模板与TTL缓存
  - Module: data; Milestone: Alpha; Priority: P1
  - Scope: 趋势与TopN模板（5m/15m）；TTL缓存与命名规范
  - Acceptance: 趋势/TopN p95≤600ms；命中 p95≤300ms
  - KPIs: 缓存命中率≥70%; Dependencies: TSDB/Exporter; Estimate: 1人/3天
- 任务7 Prometheus抓取与窗口对齐
  - Module: data; Milestone: Beta; Priority: P2
  - Scope: `prometheus.yml` 抓取间隔与窗口对齐
  - Acceptance: 查询/抓取一致；面板可用
  - KPIs: 抓取错误率≤0.1%; Dependencies: Exporter稳定; Estimate: 0.5人/2天
- 任务8 HBT快照存储接口
  - Module: data; Milestone: Beta; Priority: P2
  - Scope: 快照读写、分页明细（最近N条告警）
  - Acceptance: 查询延迟≤100ms（内存缓存）
  - KPIs: 分页响应 p95≤200ms; Dependencies: Hanabi输出; Estimate: 1人/3天

### 应用层—后端（FastAPI）
- 任务9 告警路由与聚合接口
  - Module: api; Milestone: Alpha; Priority: P1
  - Scope: `GET /api/containers/{id}/alerts?start&end&priority` 与总览告警聚合接口
  - Acceptance: 契约一致；响应 p95≤300ms（命中）
  - KPIs: 错误率≤0.1%；成功率≥99.9%; Dependencies: PromQL模板与缓存; Estimate: 1人/4天
- 任务10 SSE流告警优先策略
  - Module: api; Milestone: Alpha; Priority: P1
  - Scope: `/api/stream/{id}` 优先队列与500ms批量合并；心跳与重连（≤30s）
  - Acceptance: 告警到达优先；端到端延迟≤800ms
  - KPIs: 保活≥1h；重连成功率≥99%; Dependencies: 事件源与告警视图; Estimate: 1人/2天
- 任务11 日志路由基础（不影响告警）
  - Module: api; Milestone: Alpha; Priority: P1（并行）
  - Scope: `GET /api/containers/{id}/logs?start&end&limit`
  - Acceptance: 表格加载流畅；与告警路由无互斥
  - KPIs: p95≤600ms（未命中）; Dependencies: PromQL封装; Estimate: 1人/3天
- 任务12 总览路由（告警优先展示）
  - Module: api; Milestone: Alpha; Priority: P1
  - Scope: `GET /api/overview`（先返回告警态势与趋势）
  - Acceptance: 首屏数据稳定；契约一致
  - KPIs: p95≤300ms（命中）; Dependencies: 告警聚合接口; Estimate: 1人/2天
- 任务13 鉴权与RBAC
  - Module: api; Milestone: Beta; Priority: P2
  - Scope: JWT/Token；命名空间/容器级授权；限流与审计
  - Acceptance: 敏感接口受控；审计完整
  - KPIs: 未授权访问阻断率=100%; Dependencies: 路由完成; Estimate: 1人/4天
- 任务14 可观测与健康探针
  - Module: api; Milestone: Beta; Priority: P2
  - Scope: 自指标（耗时/错误率/SSE连接数）；探针
  - Acceptance: 面板可用；告警有效
  - KPIs: 错误率≤0.1%; Dependencies: 路由完成; Estimate: 1人/2天

### 应用层—前端（React）
- 任务15 告警信息分页
  - Module: frontend; Milestone: Alpha; Priority: P1
  - Scope: 列表（过滤/排序/分页）、趋势与TopN、确认/备注、首屏优化
  - Acceptance: 首屏≤2s；推送延迟≤800ms；交互成功率≥99.9%
  - KPIs: 错误率≤0.1%; Dependencies: 告警接口与SSE优先策略; Estimate: 1人/6天
- 任务16 总览页面（告警优先）
  - Module: frontend; Milestone: Alpha; Priority: P1
  - Scope: 告警态势卡片与趋势图；事件分布与TopN辅
  - Acceptance: 首屏≤2s；图表正确
  - KPIs: p95≤2s; Dependencies: 告警聚合接口; Estimate: 1人/4天
- 任务17 容器日志分页与HBT侧栏
  - Module: frontend; Milestone: Beta; Priority: P2
  - Scope: 虚拟滚动与实时SSE追加；告警→日志联动；HBT树展示
  - Acceptance: 滚动流畅；联动正确
  - KPIs: 滚动卡顿<100ms; Dependencies: 日志接口/SSE; Estimate: 1人/5天
- 任务18 公共组件与测试
  - Module: frontend; Milestone: Beta; Priority: P2
  - Scope: `useEventSource`、ECharts封装、TanStack Query封装；Vitest+RTL
  - Acceptance: 单测覆盖≥60%；组件复用性良好
  - KPIs: 构建时间≤60s; Dependencies: 页面基础完成; Estimate: 1人/4天

### DevOps / QA
- 任务19 Compose与联调环境
  - Module: devops; Milestone: Alpha; Priority: P1
  - Scope: 合并 `docker-compose.yml` 与 `docker-compose.app.yml` 的联调说明与脚本
  - Acceptance: 一键启动联调；文档齐备
  - KPIs: 启动失败率≤1%; Dependencies: API/前端占位; Estimate: 0.5人/2天
- 任务20 CI/CD草案完善
  - Module: devops; Milestone: Beta; Priority: P2
  - Scope: 前端 lint/test/build；后端 ruff/pytest；镜像构建草案
  - Acceptance: 目录变更触发，流程通过
  - KPIs: CI失败率≤5%; Dependencies: 工程结构稳定; Estimate: 0.5人/2天
- 任务21 测试计划与用例执行
  - Module: qa; Milestone: Alpha→Beta; Priority: P1→P2
  - Scope: 单测/集成/性能用例编写与执行
  - Acceptance: Alpha≥60%覆盖；Beta≥75%；RC≥85%
  - KPIs: 缺陷漏检率≤5%; Dependencies: 各模块完成; Estimate: QA 1人/贯穿

### 标签与模板建议
- 标签：`module:data|api|frontend|runtime|modeling|devops|qa`、`priority:P1|P2|P3`、`milestone:Alpha|Beta|RC`、`type:task`
- 模板：`Task (Alerts)`、`Task (Logs)`、`Task (Shared Capability)`

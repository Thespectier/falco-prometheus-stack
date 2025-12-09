# Issues 总览导航（Alpha/Beta/RC）

## Alpha（首批 9 条）
- [data][P1] Exporter 告警视图与标签治理 — 1人/2天  
  文件：`docs/issues-alpha.md`
- [data][P1] PromQL 告警模板与 TTL 缓存 — 1人/3天  
  文件：`docs/issues-alpha.md`
- [api][P1] 告警路由与聚合接口 — 1人/4天  
  文件：`docs/issues-alpha.md`
- [api][P1] SSE 告警优先策略（优先队列+合并） — 1人/2天  
  文件：`docs/issues-alpha.md`
- [frontend][P1] 告警信息分页（列表/趋势/TopN/确认） — 1人/6天  
  文件：`docs/issues-alpha.md`
- [frontend][P1] 总览页面（告警态势优先） — 1人/4天  
  文件：`docs/issues-alpha.md`
- [api][P1] 日志路由基础（不影响告警） — 1人/3天  
  文件：`docs/issues-alpha.md`
- [devops][P1] Compose 联调环境（合并启动说明） — 0.5人/2天  
  文件：`docs/issues-alpha.md`
- [qa][P1→P2] 测试计划与用例执行（单测/集成/性能） — QA 1人/贯穿  
  文件：`docs/issues-alpha.md`

## Beta（关键任务）
- [api][P2] 鉴权与 RBAC（JWT/命名空间/容器） — 1人/4天  
  文件：`docs/issues-beta.md`
- [api][P2] 可观测与健康探针（耗时/错误率/SSE连接数） — 1人/2天  
  文件：`docs/issues-beta.md`
- [data][P2] HBT 快照存储接口（读写与分页） — 1人/3天  
  文件：`docs/issues-beta.md`
- [frontend][P2] 容器日志分页与 HBT 侧栏（联动） — 1人/5天  
  文件：`docs/issues-beta.md`
- [frontend][P2] 公共组件与测试（Query/ECharts/SSE/单测） — 1人/4天  
  文件：`docs/issues-beta.md`
- [devops][P2] CI/CD 草案完善（前端/后端流水线与门禁） — 0.5人/2天  
  文件：`docs/issues-beta.md`
- [data][P2] Prometheus 抓取与窗口对齐 — 0.5人/2天  
  文件：`docs/issues-beta.md`
- [frontend][P2] Grafana 嵌入统一（总览页） — 0.5人/2天  
  文件：`docs/issues-beta.md`

## RC（收尾与验收）
- [qa][P1] 压测与性能验收（API/SSE/前端首屏） — QA 1人/3天  
  文件：`docs/issues-rc.md`
- [api][P1] 安全审查与合规（鉴权/RBAC/审计） — 1人/2天  
  文件：`docs/issues-rc.md`
- [devops][P1] 发布与回滚演练（文档与脚本） — 0.5人/2天  
  文件：`docs/issues-rc.md`
- [qa][P1] 缺陷收敛与最终验收（告警相关 P1=0） — QA 1人/2天  
  文件：`docs/issues-rc.md`

---

说明
- 创建 Issue 时，选择对应集合文件中的条目复制，添加标签：`module:*`、`priority:P*`、`milestone:*`、`type:task`
- 将 Issue 分配到 Projects 看板管理流转（Backlog → In Progress → Review → Done）

## 任务进度表模板

| Issue # | Title | Module | Priority | Milestone | Assignee | Status | Start | Due | Actual (days) | Notes |
|---------|-------|--------|----------|-----------|----------|--------|-------|-----|---------------|-------|
|         |       |        | P1/P2    | Alpha     |          | Backlog/In Progress/Review/Done/Blocked |       |     |               |       |
|         |       |        |          | Beta      |          |                                        |       |     |               |       |
|         |       |        |          | RC        |          |                                        |       |     |               |       |

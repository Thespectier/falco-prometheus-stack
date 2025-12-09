# 后端 API 契约与 PromQL 封装（建议）

## 总览
- 框架：FastAPI + Uvicorn
- Python 版本：保留 `>=3.14`
- 通道：REST + SSE（WebSocket 按需）

## 路由与契约
- `GET /api/containers`
  - 返回：容器列表、事件速率、最新事件时间
- `GET /api/containers/{id}/logs?start&end&limit&priority`
  - 返回：结构化事件列表（时间、rule、priority、evt.type、proc.name、fd.*、k8s.*）
- `GET /api/containers/{id}/alerts?start&end&priority`
  - 返回：告警明细与聚合统计
- `GET /api/overview`
  - 返回：总速率、优先级/分类分布、Top 规则
- `GET /api/hbt/{id}`
  - 返回：HBT 树快照（TreeNode JSON）与元信息
- `GET /api/stream/{id}`（SSE）
  - 事件与告警实时流（心跳与保活）

## PromQL 封装
- 统一时间窗口：5m/15m；Query Key 基于容器ID与窗口
- 模板示例：
  - 总速率：`sum(rate(syscall_events_total[5m]))`
  - 按优先级：`sum by(priority) (rate(syscall_events_total[5m]))`
  - 按分类：`sum by(rule_category) (rate(syscall_events_total[5m]))`
  - 最新时间：`max(syscall_last_event_timestamp_seconds)`
  - 容器速率：`sum(rate(syscall_events_total{container_name="$id"}[5m]))`
  - 告警速率：`sum by(rule,priority) (rate(security_alerts_total{container_name="$id"}[5m]))`

## 缓存与治理
- 缓存：内存 LRU/TTL（PromQL 结果）；高并发可选 Redis
- 鉴权与 RBAC：JWT/Token；按命名空间/容器授权
- 限流与审计：接口速率限制、访问日志与异常审计
- 可观测指标：请求耗时、错误率、SSE连接数；健康探针

## SSE 设计
- 服务端批量合并（如 500ms）；心跳与断线重连；客户端 backoff 策略

## 错误处理
- 统一错误码与信息；边界参数校验；超时与降级（关闭高成本查询）

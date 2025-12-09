# PromQL 模板与标签治理

## 时间窗口
- 统一：5m/15m；API 层提供 TTL 缓存（命中 ≤ 200ms）

## 模板示例
- 总速率：`sum(rate(syscall_events_total[5m]))`
- 按优先级：`sum by(priority) (rate(syscall_events_total[5m]))`
- 按分类：`sum by(rule_category) (rate(syscall_events_total[5m]))`
- 最新时间：`max(syscall_last_event_timestamp_seconds)`
- 容器速率：`sum(rate(syscall_events_total{container_name="$id"}[5m]))`
- 告警速率：`sum by(rule,priority) (rate(security_alerts_total{container_name="$id"}[5m]))`

## 标签治理
- 控制维度：`container_name`、`rule`、`priority`、`rule_category`、`process_name`、`image_repository`、`k8s.*`
- 避免高基数：审查新标签引入与去重策略；必要时下线高基数维度

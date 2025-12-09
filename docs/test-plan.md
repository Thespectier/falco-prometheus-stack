# 测试计划（单测/集成/性能）

## 单元测试
- 前端：hooks/组件（useEventSource、图表封装、表格交互）
- 后端：PromQL 封装、路由参数校验、SSE 推送逻辑
- 覆盖率目标：Alpha ≥ 60%，Beta ≥ 75%，RC ≥ 85%

## 集成测试
- 端到端：Falco→Exporter→TSDB→API→前端（模拟事件与查询）
- 安全：JWT/RBAC、限流与审计
- 稳定性：SSE 心跳与重连、合并刷新正确性

## 性能与基准
- API p95 延迟与首屏时间；SSE 端到端延迟
- 压测：并发连接与事件突发场景；降级策略验证

## 验收
- Alpha/Beta/RC 对应 KPI 达成；缺陷收敛要求；发布与回滚演练通过

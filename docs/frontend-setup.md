# 前端初始化与项目结构（建议）

## 依赖清单（最终）
- react, react-dom, typescript, vite
- antd, @ant-design/icons
- @tanstack/react-query, @tanstack/react-table, @tanstack/react-virtual
- echarts, echarts-for-react
- react-router-dom
- 状态：zustand
- 测试：vitest, @testing-library/react
- 质量：eslint, prettier

## 项目结构（建议）
```
web/
  src/
    pages/
      overview/
      logs/
      alerts/
    components/
      hbt-tree/
      charts/
      tables/
    hooks/
      useEventSource.ts
    api/
      client.ts
      queries/
        overview.ts
        logs.ts
        alerts.ts
        hbt.ts
    state/
      filtersStore.ts
    tests/
  vite.config.ts
  package.json
```

## 数据契约与交互（最终）
- REST：`/api/containers`、`/api/overview`、`/api/containers/{id}/logs`、`/api/containers/{id}/alerts`、`/api/hbt/{id}`。
- SSE：`/api/stream/{id}`（事件与告警实时追加）。
- 筛选与分页：统一参数 `container_id`、`start`、`end`、`limit`、`priority`。

## 性能策略（最终）
- 表格虚拟滚动与分页；查询结果缓存（Query Key 基于容器ID与时间窗口）；
- SSE 客户端批量合并刷新（如 500ms）；断线重连与 backoff；
- 图表懒加载与数据量阈值控制；

## UI 视图（最终）
- 总览：指标卡片（速率、最新时间、当日告警），优先级/分类分布，Top 规则。
- 容器日志：表格（时间、rule、priority、evt.type、proc.name、fd.*、k8s.*），HBT 树侧栏，实时追加。
- 告警信息：列表、趋势与 TopN、操作（确认/备注），实时订阅。

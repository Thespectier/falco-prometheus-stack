# SSE 事件封装（Envelope）

## 事件结构
- `type`: event|alert|heartbeat
- `ts`: ISO8601 时间
- `container`: 容器名称或ID
- `payload`: 事件或告警明细（与 REST 字段一致）

## 心跳与重连
- 心跳间隔：30s；客户端在 90s 无心跳时视为断线
- 重连策略：指数退避（1s/2s/4s/8s，最大 30s）

## 批量合并刷新
- 服务端在 500ms 窗口内聚合事件后推送，降低高频抖动

## 错误与告警
- 统一错误码与信息；异常事件带 `severity` 字段（info/warn/error）

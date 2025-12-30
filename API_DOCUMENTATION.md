# Falco/Hanabi Monitoring API 文档

本文档详细介绍了 Falco/Hanabi 监控系统的 API 接口。

## 基础信息

- **版本**: 0.1.0
- **基础路径 (Base URL)**: `/` 或 `/infrasecurity` (所有接口均支持两种前缀)
- **文档地址**: `/docs` (Swagger UI), `/redoc` (ReDoc)
- **OpenAPI 规范**: `/openapi.json`

## 认证

部分接口可能需要通过 `ACCESS_CONTROL_ENABLED` 环境变量控制的访问控制。
验证 Token 接口位于 `/clientsecurity/verifyToken`。

## 接口列表

### 1. 系统概览 (Overview)

#### 获取系统概览指标
获取系统的整体监控指标，包括事件率、分布情况和活跃容器数。

- **Endpoint**: `/api/overview`
- **Method**: `GET`
- **Query Parameters**: 无
- **Response**:
  ```json
  {
    "total_events_rate": 12.5,
    "priority_distribution": [
      {
        "priority": "Error",
        "value": 5.2
      }
    ],
    "category_distribution": [
      {
        "category": "Network",
        "value": 3.1
      }
    ],
    "active_containers_count": 8,
    "funnel_stats": {
        // 漏斗统计数据 (日志 -> 警报 -> 事件)
    }
  }
  ```

### 2. 容器管理 (Containers)

#### 列出所有容器
列出所有被监控的容器及其当前状态和指标（基于 Prometheus 数据）。

- **Endpoint**: `/api/containers`
- **Method**: `GET`
- **Query Parameters**: 无
- **Response**:
  ```json
  [
    {
      "id": "falco",
      "name": "falco",
      "last_seen": 1672531200.0,
      "event_rate": 1.5
    }
  ]
  ```

#### 获取容器日志
从存储中获取指定容器的历史日志。

- **Endpoint**: `/api/containers/{id}/logs`
- **Method**: `GET`
- **Path Parameters**:
  - `id` (string): 容器 ID 或名称
- **Query Parameters**:
  - `start` (int, optional): 开始时间戳
  - `end` (int, optional): 结束时间戳
  - `limit` (int, default: 100): 返回条数限制
  - `offset` (int, default: 0): 分页偏移量
- **Response**:
  ```json
  {
    "container_id": "falco",
    "logs": [
      // 日志对象列表
    ]
  }
  ```

### 3. 警报 (Alerts)

#### 获取容器警报
获取指定容器的警报信息。

- **Endpoint**: `/api/containers/{id}/alerts`
- **Method**: `GET`
- **Path Parameters**:
  - `id` (string): 容器 ID 或名称
- **Query Parameters**:
  - `window_seconds` (int, default: 0): 时间窗口（秒）
  - `limit` (int, default: 500): 返回条数限制
  - `offset` (int, default: 0): 分页偏移量
- **Response**:
  ```json
  {
    "container_id": "falco",
    "alerts": [
      // 警报对象列表
    ]
  }
  ```

### 4. 行为树 (HBT)

#### 获取 HBT 快照
获取指定容器的最新行为树（Hierarchical Behavior Tree）快照。

- **Endpoint**: `/api/hbt/{id}`
- **Method**: `GET`
- **Path Parameters**:
  - `id` (string): 容器 ID 或名称
- **Query Parameters**: 无
- **Response**: JSON 对象，包含完整的 HBT 结构数据。
- **Errors**:
  - 404: 找不到该容器的 HBT 快照
  - 500: 读取快照失败

### 5. 实时流 (Stream)

#### 实时事件流
通过 Server-Sent Events (SSE) 获取指定容器的实时事件和警报。

- **Endpoint**: `/api/stream/{id}`
- **Method**: `GET`
- **Path Parameters**:
  - `id` (string): 容器 ID 或名称
- **Response Type**: `text/event-stream`
- **Data Format**:
  ```
  data: {'type': 'heartbeat', 'container': 'falco'}
  ```

### 6. 安全事件 (Incidents)

#### 列出安全事件
列出系统中的安全事件（Incidents）。安全事件是经过缩减和分析后的高危警报集合。

- **Endpoint**: `/api/incidents`
- **Method**: `GET`
- **Query Parameters**:
  - `container_id` (string, optional): 按容器 ID 筛选
  - `window_seconds` (int, default: 0): 时间窗口（秒）
  - `limit` (int, default: 500): 返回条数限制
  - `offset` (int, default: 0): 分页偏移量
- **Response**: 安全事件对象列表（结构同下）。

#### 获取特定容器的安全事件
获取指定容器的安全事件。

- **Endpoint**: `/api/containers/{id}/incidents`
- **Method**: `GET`
- **Path Parameters**:
  - `id` (string): 容器 ID 或名称
- **Query Parameters**:
  - `window_seconds` (int, default: 0): 时间窗口（秒）
  - `limit` (int, default: 500): 返回条数限制
  - `offset` (int, default: 0): 分页偏移量
- **Response**:
  ```json
  {
    "container_id": "falco",
    "incidents": [
      {
        "id": 101,
        "container_id": "falco",
        "timestamp": "2023-01-01T12:00:00+08:00",
        "threat_score": 8.5,             // 威胁评分
        "cluster_id": 1,                 // 聚类 ID
        "attribute_name": "proc.name",   // 关键属性名
        "attribute_value": "nc",         // 关键属性值
        "event_type": "connect",         // 事件类型
        "process_name": "nc",            // 进程名
        "alert_content": "Netcat detected", // 警报内容
        "details": "...",                // 详细信息
        "analysis_window": 300,          // 分析窗口大小
        "similarity_threshold": 0.8,     // 相似度阈值
        "created_at": "2023-01-01T12:05:00+08:00", // 创建时间
        "analysis": "LLM Analysis Result..." // LLM 分析结果
      }
    ]
  }
  ```

### 7. 配置 (Config)

#### 获取 LLM 配置
获取当前的大语言模型（LLM）配置信息。API Key 会被掩码处理。

- **Endpoint**: `/api/config/llm`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "api_key": "********",
    "endpoint": "https://api.deepseek.com",
    "model": "deepseek-chat"
  }
  ```

#### 设置 LLM 配置
更新 LLM 配置信息。

- **Endpoint**: `/api/config/llm`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "api_key": "your-api-key",  // 可选，若为 "********" 则不更新
    "endpoint": "https://api.deepseek.com",
    "model": "deepseek-chat"
  }
  ```
- **Response**:
  ```json
  {
    "status": "ok"
  }
  ```

### 8. 其他接口

#### 健康检查
检查 API 服务状态。

- **Endpoint**: `/healthz`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "ok"
  }
  ```

#### 验证 Token
验证用户 Token 有效性（用于集成认证）。

- **Endpoint**: `/clientsecurity/verifyToken`
- **Method**: `GET`
- **Query Parameters**:
  - `token` (string, optional): 待验证的 Token
- **Response**:
  ```json
  {
    "success": true,
    "user": {
        // 用户信息
    }
  }
  ```

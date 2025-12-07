# Falco Prometheus Stack

一个基于 Falco 的安全监控系统，集成 Prometheus、和自定义 Python 分析工具，用于实时监控和分析容器安全事件。

## 📋 项目简介

本项目提供了一套完整的容器安全监控解决方案：

- **Falco**: 云原生运行时安全工具，实时检测异常行为和威胁
- **Prometheus**: 时序数据库，存储和查询安全事件指标
- **Hanabi**: 自定义 Python 工具，实时读取和分析 Falco 日志流

## 🏗️ 架构

```
┌─────────────┐
│   Falco     │ 监控系统调用和容器事件
└──────┬──────┘
       │ JSON logs
       ↓
┌─────────────┐
│DockerLogQueue│ Python 实时日志流处理
└─────────────┘
       │ Metrics
       ↓
┌─────────────┐
│ Prometheus  │ 指标存储和查询
└─────────────┘
```

架构分层图（SVG）：

![Layered Architecture](docs/architecture-layered.svg)

更多细节请参见 `ARCHITECTURE.md`（模块职责、数据流与配置要点）。

## 🚀 快速开始

### 前置要求

- Docker 和 Docker Compose
- Python 3.14+
- Linux 内核（用于 Falco 驱动）

### 安装步骤

1. **克隆仓库**
```bash
git clone <repository-url>
cd falco-prometheus-stack
```

2. **安装 Python 依赖**
```bash
# 使用 uv（推荐）
uv sync


## 📖 使用方法

### 使用 DockerLogQueue 实时读取 Falco 日志

```python
from hanabi.utils.queue import DockerLogQueue
import json

# 创建日志队列
log_queue = DockerLogQueue(container_name="falco", max_queue_size=10000)

try:
    # 启动日志流
    log_queue.start()
    
    # 持续读取日志
    while True:
        json_obj = log_queue.get(timeout=1)
        if json_obj:
            print(json.dumps(json_obj, ensure_ascii=False))
            # 在这里添加你的业务逻辑
            
except KeyboardInterrupt:
    print("\n停止监控")
finally:
    log_queue.stop()
```

### 运行示例程序

```bash
python main.py
```

或使用一键栈（需要 Docker）：

```bash
docker compose up -d
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000  (默认密码 admin/admin)
```

### 查看 Prometheus 指标

访问 `http://localhost:9090` 打开 Prometheus Web UI，查询安全事件指标。

示例查询：
- 事件总数：`sum(rate(syscall_events_total[5m]))`
- 按优先级：`sum by(priority) (rate(syscall_events_total[5m]))`
- 最新事件时间：`syscall_last_event_timestamp_seconds`
- 分类维度（rule_category）：`sum by(rule_category) (rate(syscall_events_total[5m]))`


## 🔧 核心组件

### DockerLogQueue

一个线程安全的队列类，用于从 Docker 容器的 stdout 实时读取 JSON 日志流。

**特性**：
- ✅ 后台线程异步采集日志
- ✅ 自动 JSON 解析和验证
- ✅ 线程安全的队列操作
- ✅ 可配置的队列大小（防止内存溢出）
- ✅ 统计信息（处理行数、错误数）
- ✅ 优雅的启动和停止机制
- ✅ 只读取实时日志（从 `start()` 之后的新日志）

**API**：
```python
# 初始化
queue = DockerLogQueue(container_name="falco", max_queue_size=10000)

# 启动采集
queue.start()

# 获取日志（阻塞式，带超时）
json_obj = queue.get(timeout=1)

# 获取日志（非阻塞式）
json_obj = queue.get_nowait()

# 检查队列状态
is_empty = queue.is_empty()
size = queue.size()

# 获取统计信息
stats = queue.get_stats()

# 停止采集
queue.stop()
```

## 🛠️ 配置

### Falco 配置

编辑 `falco/falco.yaml` 自定义 Falco 行为：
- `json_output: true` - 启用 JSON 格式输出
- `json_include_output_property: true` - 包含完整输出字段
- 自定义规则：在 `falco/rules/custom_rules.yaml` 中添加


### Prometheus 配置

编辑 `prometheus/prometheus.yml` 配置抓取目标和规则。

## 📊 监控示例

### Falco 事件类型统计

```promql
sum by(priority) (rate(falco_events_total[5m]))
```

### 检测到的威胁数量

```promql
increase(falco_events_total{priority="Critical"}[1h])
```

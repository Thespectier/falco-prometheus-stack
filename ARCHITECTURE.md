# 架构与模块说明

## 总览
- 数据流：`Falco → DockerLogQueue → (Hanabi HBT / Prometheus Exporter) → Prometheus → Grafana`
- 运行方式：本地 Docker 容器输出 JSON 日志；Python 组件消费并构建模型或导出指标。

## 目录结构
- `falco/`：Falco 主配置 `falco.yaml` 与自定义规则 `custom_rules.yaml`
- `hanabi/`：Python 分析与画像构建
  - `utils/queue.py`：`DockerLogQueue`，后台线程从容器实时拉取 JSON 日志
  - `utils/timeCount.py`：`EventCounter`，10 秒窗口事件速率与预热控制
  - `models/hbt.py`：`HBTModel`，一个容器对应一个层次化行为树
  - `models/hbt_builder.py`：`HBTBuilder`，根下三大分支（进程/网络/文件）及路由
  - `models/branch_handlers.py`：分支处理器，负责节点增量与学习/检测切换
  - `models/tree_node.py`：树节点结构与 `to_dict`
  - `models/event_parser.py`：事件解析、分类与输出字段提取
  - `models/embedding.py`：语义匹配（HF 模型）
- `prometheus/`：指标导出与配置
  - `exporter.py`：将 Falco 事件转为 Prometheus 指标
  - `prometheus.yml`：抓取 `localhost:9876` 指标端口
- `main.py`：示例入口，构建 HBT 并以 Rich Tree 可视化
- `README.md`：使用说明与示例

## 关键数据流
- Falco 输出：`falco.yaml` 设置 `json_output=true`、`json_include_output_fields_property=true`
- 规则字段：`custom_rules.yaml` 输出 `evt.type / proc.* / fd.* / container.* / k8s.*`
- 队列消费：`DockerLogQueue.start()` 连接 `falco` 容器，采用 `since=now` 只读新日志
- HBT 构建：`HBTBuilder.add_event()` 依据分类路由到 `Process/Network/FileBranchHandler`
- 学习/检测：`EventCounter` 预热后根据 10s 速率低于阈值切换为检测，语义匹配仅在检测期进行一致性校验
- 指标导出：`prometheus/exporter.py` 将事件映射至 `Counter` 与时间戳 `Gauge`

## 组件职责
- Falco：实时采集系统调用事件，按规则输出结构化 JSON
- Hanabi：
  - 解析事件并构建 HBT 树，按操作层/进程层/属性层组织
  - 预热期学习典型模式，检测期进行语义匹配校验并输出告警日志
- Prometheus Exporter：
  - 以标签维度统计事件（规则、优先级、容器、镜像、进程、K8s）
  - 暴露最新事件时间戳与可选事件速率指标
- Prometheus：抓取并存储指标，供查询与可视化
- Grafana：仪表盘展示核心安全态势（可新增 dashboard）

## 运行与配置要点
- Falco 驱动：`engine.kind=modern_ebpf`，生产可视负载做缓冲与丢包策略调优
- 队列：`max_queue_size` 防止内存膨胀；仅消费 `start()` 后的增量日志
- 事件分类：优先基于 `rule`，回退至 `evt.type`
- Prometheus 指标：启动端口 `9876`；`prometheus.yml` 静态抓取

## 待改进项
- 修复时间戳指标类型：`evt.time.iso8601` 为字符串，应统一转换为秒级数值
- 增强可观测性：输出事件速率、学习状态切换指示
- 可视化闭环：补充 Grafana dashboard 与一键启动栈


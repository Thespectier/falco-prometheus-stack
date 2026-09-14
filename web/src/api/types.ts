/**
 * 接口数据结构。
 *
 * 字段名与后端返回逐字对应（后端侧有黄金输出保证），因此只能新增、不能改名；
 * 可选字段对应后端可能缺省的列（例如事件里未回填的分析结论）。
 */

// ── 总览 ────────────────────────────────────────────────────────────────────

/** 优先级维度的采样值 */
export interface PriorityDistribution {
  priority: string;
  value: number;
}

/** 规则类别维度的采样值 */
export interface CategoryDistribution {
  category: string;
  value: number;
}

/** 漏斗三段计数：日志 → 告警 → 事件 */
export interface FunnelStats {
  logs: number;
  alerts: number;
  incidents: number;
}

/** 总览页一次请求拿到的全部指标 */
export interface OverviewMetrics {
  total_events_rate: number;
  priority_distribution: PriorityDistribution[];
  category_distribution: CategoryDistribution[];
  active_containers_count: number;
  funnel_stats: FunnelStats;
}

// ── 容器 ────────────────────────────────────────────────────────────────────

/** 容器列表项；`last_seen` 是 Unix 秒 */
export interface ContainerSummary {
  id: string;
  name: string;
  last_seen: number;
  event_rate: number;
}

/** 告警按类别聚合后的速率 */
export interface AlertStat {
  rule: string;
  priority: string;
  rate: number;
}

// ── 告警 ────────────────────────────────────────────────────────────────────

/** 单条告警明细 */
export interface AlertDetail {
  container_id: string;
  timestamp: string;
  category: string;
  reason: string;
  evt_type: string;
  proc_name: string;
  fd_name: string;
  output: string;
}

/** 某容器的告警列表响应 */
export interface ContainerAlerts {
  container_id: string;
  alerts: AlertDetail[];
}

// ── 行为画像 ────────────────────────────────────────────────────────────────

/**
 * HBT 快照。
 *
 * `hbt_structure` 是递归的树（节点含 name/type/events_count/metadata/children），
 * 前端只用它做可视化遍历，这里保持 `any` 以免把后端树结构固化在前端类型里。
 */
export interface HbtSnapshot {
  container_id: string;
  hbt_structure: any;
}

// ── 日志 ────────────────────────────────────────────────────────────────────

/** WebSocket 与历史接口共用的日志条目 */
export interface LogEvent {
  timestamp: string;
  rule: string;
  priority: string;
  output: string;
  source: string;
  tags: string[];
}

/** 历史日志响应 */
export interface ContainerLogsResponse {
  container_id: string;
  logs: LogEvent[];
  warning?: string;
}

// ── 事件（incident） ────────────────────────────────────────────────────────

/** 消减后的事件；带分析结论时 `analysis` 非空 */
export interface Incident {
  container_id: string;
  timestamp: string;
  threat_score: number;
  cluster_id?: number;
  attribute_name?: string;
  attribute_value?: string;
  event_type?: string;
  process_name?: string;
  alert_content?: string;
  details?: string;
  analysis_window?: number;
  similarity_threshold?: number;
  created_at?: string;
  analysis?: string;
}

export interface PriorityDistribution {
  priority: string;
  value: number;
}

export interface CategoryDistribution {
  category: string;
  value: number;
}

export interface OverviewMetrics {
  total_events_rate: number;
  priority_distribution: PriorityDistribution[];
  category_distribution: CategoryDistribution[];
  active_containers_count: number;
}

export interface ContainerSummary {
  id: string;
  name: string;
  last_seen: number;
  event_rate: number;
}

export interface AlertStat {
  rule: string;
  priority: string;
  rate: number;
}

export interface ContainerAlerts {
  container_id: string;
  alerts: AlertDetail[];
}

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

export interface HbtSnapshot {
  container_id: string;
  hbt_structure: any; // Using any for the complex tree structure for now
}

export interface LogEvent {
  timestamp: string;
  rule: string;
  priority: string;
  output: string;
  source: string;
  tags: string[];
}

export interface ContainerLogsResponse {
    container_id: string;
    logs: LogEvent[];
    warning?: string;
}

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
}

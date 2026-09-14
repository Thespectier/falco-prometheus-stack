/**
 * 后端接口客户端。
 *
 * 地址前缀跟着 Vite 注入的 `BASE_URL` 走：网关部署时前端挂在 `/infrasecurity/` 下，
 * 接口也带同一前缀，所以基地址由环境推导而不是写死。
 *
 * 查询参数按原样拼接、不做 URL 编码——容器名与事件字段都是安全字符，后端也按原样
 * 匹配；改成编码反而会让带空格的容器名与后端日志对不上。
 */

import {
  ContainerAlerts,
  ContainerLogsResponse,
  ContainerSummary,
  HbtSnapshot,
  Incident,
  OverviewMetrics,
} from './types';

const apiPrefix = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
const API_BASE = `${apiPrefix}/api`;

/** 查询参数：值为 undefined / null / 空串时整条丢弃（与"未传该参数"等价） */
type QueryParam = [string, string | number | undefined | null];

/** 把参数表拼成 `?a=1&b=2`；没有有效参数时返回空串 */
function buildQuery(params: QueryParam[]): string {
  const pairs = params
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([name, value]) => `${name}=${value}`);
  return pairs.length > 0 ? `?${pairs.join('&')}` : '';
}

class ApiClient {
  public baseURL = API_BASE;

  /** 统一处理请求与错误：非 2xx 抛 `API Error: <状态文本>` */
  private async request<T>(endpoint: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, init);
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    return response.json();
  }

  private get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint);
  }

  /** 总览：事件速率、优先级与类别分布、活跃容器数、漏斗统计 */
  async getOverview(): Promise<OverviewMetrics> {
    return this.get<OverviewMetrics>('/overview');
  }

  /** 被监控容器列表（含最近上报时间与事件速率） */
  async listContainers(): Promise<ContainerSummary[]> {
    return this.get<ContainerSummary[]>('/containers');
  }

  /** 某容器的告警；window_seconds=0 表示不限窗口 */
  async getContainerAlerts(
    id: string,
    windowSeconds: number = 0,
    limit: number = 500,
    offset: number = 0,
  ): Promise<ContainerAlerts> {
    const query = buildQuery([
      ['window_seconds', windowSeconds],
      ['limit', limit],
      ['offset', offset],
    ]);
    return this.get<ContainerAlerts>(`/containers/${id}/alerts${query}`);
  }

  /** 某容器最新的 HBT 快照 */
  async getHbtSnapshot(id: string): Promise<HbtSnapshot> {
    return this.get<HbtSnapshot>(`/hbt/${id}`);
  }

  /** 某容器的历史日志 */
  async getContainerLogs(id: string): Promise<ContainerLogsResponse> {
    return this.get<ContainerLogsResponse>(`/containers/${id}/logs`);
  }

  /** 事件列表；不传 container_id 时返回全部容器 */
  async getIncidents(
    container_id?: string,
    windowSeconds: number = 0,
    limit: number = 500,
    offset: number = 0,
  ): Promise<Incident[]> {
    const query = buildQuery([
      ['container_id', container_id],
      ['window_seconds', windowSeconds],
      ['limit', limit],
      ['offset', offset],
    ]);
    return this.get<Incident[]>(`/incidents${query}`);
  }

  /** 读取大模型配置（key 只回掩码） */
  async getLLMConfig(): Promise<any> {
    return this.get<any>('/config/llm');
  }

  /** 写入大模型配置 */
  async setLLMConfig(config: any): Promise<any> {
    return this.request<any>('/config/llm', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
  }
}

export const api = new ApiClient();

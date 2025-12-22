import { 
  OverviewMetrics, 
  ContainerSummary, 
  ContainerAlerts, 
  HbtSnapshot,
  ContainerLogsResponse,
  Incident
} from './types';

const API_BASE = '/api';

class ApiClient {
  private async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    return response.json();
  }

  async getOverview(): Promise<OverviewMetrics> {
    return this.get<OverviewMetrics>('/overview');
  }

  async listContainers(): Promise<ContainerSummary[]> {
    return this.get<ContainerSummary[]>('/containers');
  }

  async getContainerAlerts(id: string, windowSeconds: number = 0, limit: number = 500, offset: number = 0): Promise<ContainerAlerts> {
    const params: string[] = [];
    params.push(`window_seconds=${windowSeconds}`);
    params.push(`limit=${limit}`);
    params.push(`offset=${offset}`);
    const query = `?${params.join('&')}`;
    return this.get<ContainerAlerts>(`/containers/${id}/alerts${query}`);
  }

  async getHbtSnapshot(id: string): Promise<HbtSnapshot> {
    return this.get<HbtSnapshot>(`/hbt/${id}`);
  }

  async getContainerLogs(id: string): Promise<ContainerLogsResponse> {
      return this.get<ContainerLogsResponse>(`/containers/${id}/logs`);
  }

  async getIncidents(container_id?: string, windowSeconds: number = 0, limit: number = 500, offset: number = 0): Promise<Incident[]> {
    const params: string[] = [];
    if (container_id) params.push(`container_id=${container_id}`);
    params.push(`window_seconds=${windowSeconds}`);
    params.push(`limit=${limit}`);
    params.push(`offset=${offset}`);
    const query = `?${params.join('&')}`;
    return this.get<Incident[]>(`/incidents${query}`);
  }

  async getLLMConfig(): Promise<any> {
    return this.get<any>('/config/llm');
  }

  async setLLMConfig(config: any): Promise<any> {
    const response = await fetch(`${API_BASE}/config/llm`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    return response.json();
  }
}

export const api = new ApiClient();

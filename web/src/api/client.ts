import { 
  OverviewMetrics, 
  ContainerSummary, 
  ContainerAlerts, 
  HbtSnapshot,
  ContainerLogsResponse 
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

  async getContainerAlerts(id: string, priority?: string): Promise<ContainerAlerts> {
    const query = priority ? `?priority=${priority}` : '';
    return this.get<ContainerAlerts>(`/containers/${id}/alerts${query}`);
  }

  async getHbtSnapshot(id: string): Promise<HbtSnapshot> {
    return this.get<HbtSnapshot>(`/hbt/${id}`);
  }

  async getContainerLogs(id: string): Promise<ContainerLogsResponse> {
      return this.get<ContainerLogsResponse>(`/containers/${id}/logs`);
  }
}

export const api = new ApiClient();

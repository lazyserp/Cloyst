import type {
  AirgapSettings,
  ApiKeyItem,
  AuditLogItem,
  AuditVerifyResult,
  CreatedApiKeyResponse,
  DeploymentItem,
  MetricsOverview,
  NodeItem,
  OllamaModel,
  ProjectItem,
} from './types';

const TOKEN_STORAGE_KEY = 'CLOYST_ADMIN_TOKEN';

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_STORAGE_KEY) || '';
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token.trim());
}

export function getGatewayBase(): string {
  const host = window.location.hostname || '127.0.0.1';
  return `${window.location.protocol}//${host}:8000`;
}

export class AuthError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });

  if (res.status === 401 || res.status === 403) {
    throw new AuthError(res.status, 'Invalid or missing Admin Token');
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      // ignore json parse error
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  getOverview: () => apiRequest<MetricsOverview>('/api/v1/metrics/overview'),
  getNodes: () => apiRequest<NodeItem[]>('/api/v1/nodes'),
  registerNode: (payload: {
    id: string;
    hostname: string;
    ip_address: string;
    gpu_name?: string;
    total_vram_mb: number;
    free_vram_mb: number;
  }) =>
    apiRequest<{ status: string; node_id: string }>('/api/v1/nodes/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getDeployments: () => apiRequest<DeploymentItem[]>('/api/v1/deployments'),
  createDeployment: (payload: {
    model_id: string;
    name?: string;
    engine_type: string;
    host?: string;
    port?: number;
    node_id?: string;
  }) =>
    apiRequest<DeploymentItem>('/api/v1/deployments', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  verifyDeployment: (payload: { host: string; port: number; engine_type: string }) =>
    apiRequest<{ status: string; endpoint: string; latency_ms: number; models_found: string[] }>(
      '/api/v1/deployments/verify',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),
  deleteDeployment: (id: string) =>
    apiRequest<{ status: string }>(`/api/v1/deployments/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),
  discoverOllama: () => apiRequest<OllamaModel[]>('/api/v1/discover/ollama'),

  getKeys: () => apiRequest<ApiKeyItem[]>('/api/v1/api-keys'),
  createKey: (payload: { name: string; role: string; project_id?: string | null; expires_in_days?: number | null }) =>
    apiRequest<CreatedApiKeyResponse>('/api/v1/api-keys', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  revokeKey: (id: string) =>
    apiRequest<{ status: string }>(`/api/v1/api-keys/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),

  getProjects: () => apiRequest<ProjectItem[]>('/api/v1/projects'),
  createProject: (payload: { name: string; description?: string }) =>
    apiRequest<ProjectItem>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getAuditLogs: (limit = 100) => apiRequest<AuditLogItem[]>(`/api/v1/audit-logs?limit=${limit}`),
  verifyAuditChain: () => apiRequest<AuditVerifyResult>('/api/v1/audit/verify', { method: 'POST' }),
  getAirgapSettings: () => apiRequest<AirgapSettings>('/api/v1/settings/airgap'),
};

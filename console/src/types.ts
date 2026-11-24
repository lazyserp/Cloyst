export interface MetricsOverview {
  total_requests: number;
  total_tokens: number;
  avg_latency_ms: number;
  error_count: number;
  active_nodes: number;
  total_projects: number;
  total_keys: number;
  data_egress_bytes: number;
  air_gapped: boolean;
}

export interface NodeItem {
  id: string;
  hostname: string;
  ip_address: string;
  status: string;
  gpu_name: string | null;
  total_vram_mb: number;
  free_vram_mb: number;
  last_heartbeat: string | null;
}

export interface DeploymentItem {
  id: string;
  model_id: string;
  model_name: string;
  engine_type: string;
  node_id: string;
  node_hostname: string;
  port: number;
  status: string;
  created_at: string | null;
}

export interface ProjectItem {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface ApiKeyItem {
  id: string;
  name: string;
  prefix: string;
  is_active: boolean;
  role: string;
  project_id: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface CreatedApiKeyResponse {
  id: string;
  name: string;
  api_key: string;
  project_id: string | null;
  role: string;
  prefix: string;
  created_at: string;
  expires_at: string | null;
}

export interface AuditLogItem {
  id: string;
  api_key_id: string | null;
  project_id: string | null;
  model_id: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status_code: number;
  error_message: string | null;
  created_at: string;
}

export interface AuditVerifyResult {
  valid: boolean;
  verified_record_count: number;
  error: string | null;
}

export interface AirgapSettings {
  air_gap_mode: boolean;
  egress_allowlist: string[];
  environment: string;
}

export interface OllamaModel {
  name: string;
  size_bytes: number;
  modified_at: string | null;
}

export type TabId =
  | 'overview'
  | 'keys'
  | 'models'
  | 'nodes'
  | 'projects'
  | 'playground'
  | 'trust';

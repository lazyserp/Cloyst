import { useState } from 'react';
import { Check, Copy, KeyRound, Plus, Trash2, X } from 'lucide-react';
import { api, getGatewayBase } from '../api';
import type { ApiKeyItem, CreatedApiKeyResponse, ProjectItem } from '../types';

interface Props {
  keys: ApiKeyItem[];
  projects: ProjectItem[];
  onRefresh: () => void;
  onToast: (msg: string, type?: 'success' | 'error') => void;
}

export function KeysTab({ keys, projects, onRefresh, onToast }: Props) {
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [role, setRole] = useState('inference');
  const [projectId, setProjectId] = useState('');
  const [expiresDays, setExpiresDays] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [createdKey, setCreatedKey] = useState<CreatedApiKeyResponse | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const projectMap = new Map(projects.map((p) => [p.id, p.name]));

  const copyText = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 1800);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const res = await api.createKey({
        name: name.trim(),
        role,
        project_id: projectId || null,
        expires_in_days: expiresDays ? Number(expiresDays) : null,
      });
      setCreatedKey(res);
      setShowCreate(false);
      setName('');
      setExpiresDays('');
      onToast('Virtual API key minted', 'success');
      onRefresh();
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Failed to create key', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async (id: string, keyName: string) => {
    if (!confirm(`Revoke API key "${keyName}" immediately?`)) return;
    try {
      await api.revokeKey(id);
      onToast(`Key "${keyName}" revoked`, 'success');
      onRefresh();
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Failed to revoke key', 'error');
    }
  };

  const gatewayBase = getGatewayBase();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Virtual Keys</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            HMAC-SHA256 peppered API keys with role-based scoping and zero-latency in-memory validation.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 shadow-xs transition-colors"
        >
          <Plus className="w-4 h-4" /> Create New Key
        </button>
      </div>

      {/* Keys Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                <th className="py-3 px-5">Key Alias</th>
                <th className="py-3 px-4">Prefix</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Project</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Created</th>
                <th className="py-3 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {keys.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center">
                    <KeyRound className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-sm font-medium text-slate-700">No virtual keys yet</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Create a key to connect OpenAI SDKs, Cursor, or Claude Code to Cloyst.
                    </p>
                  </td>
                </tr>
              ) : (
                keys.map((k) => (
                  <tr key={k.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-5 font-medium text-slate-900">{k.name}</td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-600">
                      <span className="bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                        {k.prefix}…
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex px-2 py-0.5 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {k.role}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">
                      {k.project_id ? projectMap.get(k.project_id) || k.project_id : 'Global'}
                    </td>
                    <td className="py-3.5 px-4">
                      {k.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
                          Revoked
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-500 whitespace-nowrap">
                      {new Date(k.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-5 text-right">
                      {k.is_active && (
                        <button
                          onClick={() => handleRevoke(k.id, k.name)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Key Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">Create Virtual Key</h3>
              <button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Key Name *</label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. claude-code-engineering"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Role</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  >
                    <option value="inference">inference</option>
                    <option value="operator">operator</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Expires (Days)</label>
                  <input
                    type="number"
                    min="1"
                    value={expiresDays}
                    onChange={(e) => setExpiresDays(e.target.value)}
                    placeholder="Never"
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Project Scope</label>
                <select
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                >
                  <option value="">Global (Unscoped)</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
                >
                  {submitting ? 'Minting…' : 'Create Key'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* One-Time Key Reveal Modal */}
      {createdKey && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-emerald-50/60">
              <div>
                <h3 className="text-base font-semibold text-emerald-950">API Key Created</h3>
                <p className="text-xs text-emerald-700">Copy this secret now — it will never be shown again.</p>
              </div>
              <button onClick={() => setCreatedKey(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Secret Key</label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 rounded-lg bg-slate-900 text-emerald-300 font-mono text-xs break-all">
                    {createdKey.api_key}
                  </code>
                  <button
                    onClick={() => copyText(createdKey.api_key, 'key')}
                    className="px-3 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 inline-flex items-center gap-1.5"
                  >
                    {copiedField === 'key' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedField === 'key' ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-slate-600">Quick Connect (Claude Code / OpenAI SDK)</label>
                  <button
                    onClick={() =>
                      copyText(
                        `export OPENAI_BASE_URL="${gatewayBase}/v1"\nexport OPENAI_API_KEY="${createdKey.api_key}"\nexport ANTHROPIC_BASE_URL="${gatewayBase}"\nexport ANTHROPIC_AUTH_TOKEN="${createdKey.api_key}"`,
                        'env'
                      )
                    }
                    className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
                  >
                    {copiedField === 'env' ? 'Copied!' : 'Copy env snippet'}
                  </button>
                </div>
                <pre className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] font-mono text-slate-700 overflow-x-auto">
{`export OPENAI_BASE_URL="${gatewayBase}/v1"
export OPENAI_API_KEY="${createdKey.api_key}"
export ANTHROPIC_BASE_URL="${gatewayBase}"
export ANTHROPIC_AUTH_TOKEN="${createdKey.api_key}"`}
                </pre>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={() => setCreatedKey(null)}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { Box, CheckCircle2, Plus, Radar, Trash2, X } from 'lucide-react';
import { api } from '../api';
import type { DeploymentItem, NodeItem, OllamaModel } from '../types';

interface Props {
  deployments: DeploymentItem[];
  nodes: NodeItem[];
  onRefresh: () => void;
  onToast: (msg: string, type?: 'success' | 'error') => void;
}

export function ModelsTab({ deployments, nodes, onRefresh, onToast }: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [modelId, setModelId] = useState('');
  const [engineType, setEngineType] = useState('vllm');
  const [host, setHost] = useState('127.0.0.1');
  const [port, setPort] = useState('8000');
  const [nodeId, setNodeId] = useState('');
  const [probing, setProbing] = useState(false);
  const [probeMsg, setProbeMsg] = useState<string | null>(null);
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [scanning, setScanning] = useState(false);

  const handleDiscoverOllama = async () => {
    setScanning(true);
    try {
      const found = await api.discoverOllama();
      setOllamaModels(found);
      if (found.length === 0) {
        onToast('No local Ollama models found on port 11434', 'error');
      } else {
        onToast(`Discovered ${found.length} Ollama model(s)`, 'success');
      }
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Discovery failed', 'error');
    } finally {
      setScanning(false);
    }
  };

  const handleProbe = async () => {
    setProbing(true);
    setProbeMsg(null);
    try {
      const res = await api.verifyDeployment({
        host,
        port: Number(port) || 8000,
        engine_type: engineType,
      });
      setProbeMsg(`Healthy (${res.latency_ms} ms) — ${res.endpoint}`);
      if (!modelId && res.models_found.length > 0) {
        setModelId(res.models_found[0]);
      }
    } catch (err) {
      setProbeMsg(err instanceof Error ? err.message : 'Endpoint unreachable');
    } finally {
      setProbing(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelId.trim()) return;
    try {
      await api.createDeployment({
        model_id: modelId.trim(),
        name: modelId.trim(),
        engine_type: engineType,
        host: host.trim() || '127.0.0.1',
        port: Number(port) || 8000,
        node_id: nodeId || undefined,
      });
      setShowAdd(false);
      setModelId('');
      setProbeMsg(null);
      onToast('Model deployment registered', 'success');
      onRefresh();
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Deployment failed', 'error');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`Remove deployment "${id}"?`)) return;
    try {
      await api.deleteDeployment(id);
      onToast('Deployment removed', 'success');
      onRefresh();
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Delete failed', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Models & Endpoints</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Local vLLM, Ollama, llama.cpp, SGLang, and TGI endpoints served through OpenAI & Anthropic APIs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDiscoverOllama}
            disabled={scanning}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            <Radar className={`w-4 h-4 text-indigo-600 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning…' : 'Discover Ollama'}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 shadow-xs transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Model
          </button>
        </div>
      </div>

      {ollamaModels.length > 0 && (
        <div className="bg-indigo-50/60 border border-indigo-200 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-indigo-900 uppercase tracking-wider">
              Discovered Local Ollama Models
            </span>
            <button onClick={() => setOllamaModels([])} className="text-xs text-indigo-600 hover:underline">
              Dismiss
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {ollamaModels.map((m) => (
              <button
                key={m.name}
                onClick={() => {
                  setModelId(m.name);
                  setEngineType('ollama');
                  setPort('11434');
                  setShowAdd(true);
                }}
                className="px-3 py-1.5 rounded-lg bg-white border border-indigo-200 text-xs font-medium text-indigo-900 hover:bg-indigo-100 transition-colors"
              >
                + Deploy {m.name} ({(m.size_bytes / 1e9).toFixed(1)} GB)
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                <th className="py-3 px-5">Model ID</th>
                <th className="py-3 px-4">Engine</th>
                <th className="py-3 px-4">Compute Node</th>
                <th className="py-3 px-4">Port</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {deployments.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center">
                    <Box className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="text-sm font-medium text-slate-700">No models deployed yet</p>
                    <p className="text-xs text-slate-500 mt-1">
                      Register a local vLLM/Ollama endpoint or enroll a compute node first.
                    </p>
                  </td>
                </tr>
              ) : (
                deployments.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-5 font-mono text-xs font-semibold text-slate-900">
                      {d.model_id}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200 uppercase">
                        {d.engine_type}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600">{d.node_hostname}</td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-600">:{d.port}</td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> {d.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-5 text-right">
                      <button
                        onClick={() => handleDelete(d.id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-rose-600 hover:bg-rose-50 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Remove
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Model Modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">Add Model Deployment</h3>
              <button onClick={() => setShowAdd(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Model Identifier *</label>
                <input
                  required
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  placeholder="e.g. qwen2.5-coder:7b or deepseek-r1"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Engine</label>
                  <select
                    value={engineType}
                    onChange={(e) => {
                      setEngineType(e.target.value);
                      if (e.target.value === 'ollama') setPort('11434');
                      else if (e.target.value === 'vllm') setPort('8000');
                    }}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                  >
                    <option value="vllm">vLLM</option>
                    <option value="ollama">Ollama</option>
                    <option value="llamacpp">llama.cpp</option>
                    <option value="sglang">SGLang</option>
                    <option value="tgi">TGI</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Port</label>
                  <input
                    type="number"
                    value={port}
                    onChange={(e) => setPort(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Host IP</label>
                  <input
                    value={host}
                    onChange={(e) => setHost(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Target Node</label>
                  <select
                    value={nodeId}
                    onChange={(e) => setNodeId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
                  >
                    <option value="">Auto-match by IP</option>
                    {nodes.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.hostname} ({n.ip_address})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={handleProbe}
                  disabled={probing}
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-700 inline-flex items-center gap-1"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" /> {probing ? 'Probing…' : 'Test Connection'}
                </button>
                {probeMsg && <span className="text-xs text-slate-600 truncate max-w-[240px]">{probeMsg}</span>}
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAdd(false)}
                  className="px-4 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
                >
                  Deploy Model
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

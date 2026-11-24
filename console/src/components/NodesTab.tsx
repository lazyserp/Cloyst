import { useState } from 'react';
import { Cpu, HardDrive, Plus, Server, X } from 'lucide-react';
import { api } from '../api';
import type { NodeItem } from '../types';

interface Props {
  nodes: NodeItem[];
  onRefresh: () => void;
  onToast: (msg: string, type?: 'success' | 'error') => void;
}

export function NodesTab({ nodes, onRefresh, onToast }: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [hostname, setHostname] = useState('gpu-node-alpha');
  const [ip, setIp] = useState('127.0.0.1');
  const [gpuName, setGpuName] = useState('NVIDIA RTX 4090 (24GB)');
  const [totalVram, setTotalVram] = useState('24576');
  const [freeVram, setFreeVram] = useState('20480');

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.registerNode({
        id: `node-${hostname.toLowerCase().replace(/[^a-z0-9-]/g, '-')}`,
        hostname: hostname.trim(),
        ip_address: ip.trim(),
        gpu_name: gpuName.trim(),
        total_vram_mb: Number(totalVram) || 24576,
        free_vram_mb: Number(freeVram) || 20480,
      });
      setShowAdd(false);
      onToast(`Node "${hostname}" enrolled`, 'success');
      onRefresh();
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Failed to enroll node', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Compute Fleet</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Mixed-hardware GPU inventory across NVIDIA NVML servers, Apple Silicon Macs, and Linux workstations.
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 shadow-xs transition-colors"
        >
          <Plus className="w-4 h-4" /> Enroll Node
        </button>
      </div>

      {nodes.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-xs">
          <Server className="w-9 h-9 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-800">No compute nodes enrolled</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Run <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">python scripts/run_agent.py</code> on a GPU machine, or click <strong>Enroll Node</strong> to register a local/demo node right now.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {nodes.map((n) => {
            const used = Math.max(0, (n.total_vram_mb || 0) - (n.free_vram_mb || 0));
            const pct = n.total_vram_mb > 0 ? Math.min(100, Math.round((used / n.total_vram_mb) * 100)) : 0;
            const online = n.status === 'online';
            return (
              <div key={n.id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-lg ${online ? 'bg-indigo-50 text-indigo-600' : 'bg-slate-100 text-slate-400'}`}>
                      <Cpu className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-900">{n.hostname}</h3>
                      <p className="text-xs font-mono text-slate-500">{n.ip_address}</p>
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${
                      online
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                    {n.status}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-xs text-slate-600 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100">
                  <HardDrive className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate">{n.gpu_name || 'Generic Compute Node'}</span>
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-slate-500">VRAM Utilization</span>
                    <span className="font-mono font-medium text-slate-700">
                      {(used / 1024).toFixed(1)} / {(n.total_vram_mb / 1024).toFixed(1)} GB ({pct}%)
                    </span>
                  </div>
                  <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        pct > 85 ? 'bg-rose-500' : pct > 65 ? 'bg-amber-500' : 'bg-indigo-600'
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="font-mono">{n.id}</span>
                  <span>
                    {n.last_heartbeat ? `HB: ${new Date(n.last_heartbeat).toLocaleTimeString()}` : 'No heartbeat'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">Enroll Compute Node</h3>
              <button onClick={() => setShowAdd(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleRegister} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Hostname</label>
                  <input
                    required
                    value={hostname}
                    onChange={(e) => setHostname(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">IP Address</label>
                  <input
                    required
                    value={ip}
                    onChange={(e) => setIp(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">GPU / Accelerator</label>
                <input
                  value={gpuName}
                  onChange={(e) => setGpuName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Total VRAM (MB)</label>
                  <input
                    type="number"
                    value={totalVram}
                    onChange={(e) => setTotalVram(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Free VRAM (MB)</label>
                  <input
                    type="number"
                    value={freeVram}
                    onChange={(e) => setFreeVram(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
                  />
                </div>
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
                  Enroll Node
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

import { useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  Clock,
  DollarSign,
  Zap,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { AuditLogItem, MetricsOverview } from '../types';

interface Props {
  overview: MetricsOverview | null;
  logs: AuditLogItem[];
  onNavigate: (tab: 'keys' | 'models' | 'nodes' | 'trust') => void;
}

// Blended frontier cloud API reference rate (~$3/1M prompt, $15/1M completion)
function estimateCloudCost(promptTokens: number, completionTokens: number): number {
  return (promptTokens * 3 + completionTokens * 15) / 1_000_000;
}

export function OverviewTab({ overview, logs, onNavigate }: Props) {
  const { promptTotal, completionTotal, cloudSaved } = useMemo(() => {
    let p = 0;
    let c = 0;
    for (const l of logs) {
      p += l.prompt_tokens || 0;
      c += l.completion_tokens || 0;
    }
    // Fallback to overview total_tokens if logs are truncated
    if (p + c === 0 && overview?.total_tokens) {
      p = Math.round(overview.total_tokens * 0.7);
      c = overview.total_tokens - p;
    }
    return {
      promptTotal: p,
      completionTotal: c,
      cloudSaved: estimateCloudCost(p, c),
    };
  }, [logs, overview]);

  const timelineData = useMemo(() => {
    if (!logs.length) return [];
    const sorted = [...logs].reverse().slice(-30);
    return sorted.map((log, idx) => ({
      label:
        new Date(log.created_at).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
        }) || `#${idx + 1}`,
      tokens: log.total_tokens || 0,
      latency: Math.round(log.latency_ms || 0),
    }));
  }, [logs]);

  const modelStats = useMemo(() => {
    const acc = new Map<
      string,
      { requests: number; prompt: number; completion: number; totalLatency: number }
    >();
    for (const l of logs) {
      const cur = acc.get(l.model_id) || {
        requests: 0,
        prompt: 0,
        completion: 0,
        totalLatency: 0,
      };
      cur.requests += 1;
      cur.prompt += l.prompt_tokens || 0;
      cur.completion += l.completion_tokens || 0;
      cur.totalLatency += l.latency_ms || 0;
      acc.set(l.model_id, cur);
    }
    return Array.from(acc.entries())
      .map(([model, v]) => ({
        model,
        requests: v.requests,
        tokens: v.prompt + v.completion,
        avgLatency: Math.round(v.totalLatency / v.requests),
        cloudEquiv: estimateCloudCost(v.prompt, v.completion),
      }))
      .sort((a, b) => b.tokens - a.tokens);
  }, [logs]);

  const successRate =
    overview && overview.total_requests > 0
      ? (
          ((overview.total_requests - overview.error_count) /
            overview.total_requests) *
          100
        ).toFixed(1)
      : '100.0';

  return (
    <div className="space-y-6">
      {/* 4 Essential LiteLLM-style KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Spend
            </span>
            <span className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <DollarSign className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">$0.00</span>
            <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
              Saved ~${cloudSaved.toFixed(4)}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Local inference · vs cloud API rate
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Requests
            </span>
            <span className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <Activity className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {(overview?.total_requests ?? 0).toLocaleString()}
            </span>
            <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
              {successRate}% OK
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {overview?.error_count ?? 0} failed · {overview?.total_keys ?? 0} active keys
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Tokens
            </span>
            <span className="p-2 rounded-lg bg-violet-50 text-violet-600">
              <Zap className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <span className="text-2xl font-bold text-slate-900">
              {(overview?.total_tokens ?? 0).toLocaleString()}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {promptTotal.toLocaleString()} in · {completionTotal.toLocaleString()} out
          </p>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Avg Latency
            </span>
            <span className="p-2 rounded-lg bg-sky-50 text-sky-600">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-slate-900">
              {overview?.avg_latency_ms ?? 0}
            </span>
            <span className="text-sm font-medium text-slate-500">ms</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {overview?.active_nodes ?? 0} online node(s) · 0 B egress
          </p>
        </div>
      </div>

      {/* Usage Chart + Model Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Token Usage</h3>
              <p className="text-xs text-slate-500">Tokens processed across recent gateway calls</p>
            </div>
            <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
              {timelineData.length} events
            </span>
          </div>
          {timelineData.length > 0 ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timelineData} margin={{ top: 6, right: 10, left: -16, bottom: 0 }}>
                  <defs>
                    <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="tokens"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#tokenGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 flex flex-col items-center justify-center text-center border border-dashed border-slate-200 rounded-lg bg-slate-50/50 p-6">
              <p className="text-sm font-medium text-slate-700">No requests yet</p>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Create a Virtual Key and send a request to <code className="font-mono bg-slate-100 px-1 rounded">:8000/v1</code>.
              </p>
              <button
                onClick={() => onNavigate('keys')}
                className="mt-3 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
              >
                Create Virtual Key
              </button>
            </div>
          )}
        </div>

        {/* Spend & Usage by Model Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200">
            <h3 className="text-sm font-semibold text-slate-900">Usage by Model</h3>
            <p className="text-xs text-slate-500">Requests, tokens, and cloud-equivalent savings</p>
          </div>
          <div className="flex-1 overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  <th className="py-2.5 px-4">Model</th>
                  <th className="py-2.5 px-3 text-right">Reqs</th>
                  <th className="py-2.5 px-3 text-right">Tokens</th>
                  <th className="py-2.5 px-4 text-right">Saved</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {modelStats.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-10 text-center text-slate-400">
                      No model traffic recorded.
                    </td>
                  </tr>
                ) : (
                  modelStats.slice(0, 6).map((m) => (
                    <tr key={m.model} className="hover:bg-slate-50/70">
                      <td className="py-2.5 px-4 font-mono font-medium text-slate-800 truncate max-w-[140px]">
                        {m.model}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-600">
                        {m.requests}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-700">
                        {m.tokens.toLocaleString()}
                      </td>
                      <td className="py-2.5 px-4 text-right font-mono text-emerald-700 font-medium">
                        ${m.cloudEquiv.toFixed(4)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Recent Request Logs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Recent Requests</h3>
            <p className="text-xs text-slate-500">Metadata-only audit trail (prompts are never stored)</p>
          </div>
          <span className="text-xs text-slate-500">{logs.length} records</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                <th className="py-3 px-5">Time</th>
                <th className="py-3 px-4">Model</th>
                <th className="py-3 px-4">Tokens (In / Out / Total)</th>
                <th className="py-3 px-4">Latency</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-xs text-slate-500">
                    No requests recorded yet.
                  </td>
                </tr>
              ) : (
                logs.slice(0, 15).map((log) => {
                  const ok = log.status_code < 400;
                  return (
                    <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-5 text-xs text-slate-500 font-mono whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-900 font-mono text-xs">
                        {log.model_id}
                      </td>
                      <td className="py-3 px-4 text-xs font-mono text-slate-600">
                        {log.prompt_tokens} / {log.completion_tokens} /{' '}
                        <span className="font-semibold text-slate-900">{log.total_tokens}</span>
                      </td>
                      <td className="py-3 px-4 text-xs font-mono text-slate-600">
                        {log.latency_ms} ms
                      </td>
                      <td className="py-3 px-4">
                        {ok ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {log.status_code} OK
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
                            <AlertTriangle className="w-3 h-3" /> {log.status_code}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

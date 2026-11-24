import { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  Box,
  Cpu,
  FolderKanban,
  KeyRound,
  Lock,
  RefreshCw,
  Shield,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { api, AuthError, getStoredToken, setStoredToken } from './api';
import { KeysTab } from './components/KeysTab';
import { ModelsTab } from './components/ModelsTab';
import { NodesTab } from './components/NodesTab';
import { OverviewTab } from './components/OverviewTab';
import { PlaygroundTab } from './components/PlaygroundTab';
import { ProjectsTab } from './components/ProjectsTab';
import { TrustTab } from './components/TrustTab';
import type {
  AirgapSettings,
  ApiKeyItem,
  AuditLogItem,
  DeploymentItem,
  MetricsOverview,
  NodeItem,
  ProjectItem,
  TabId,
} from './types';

const NAV_ITEMS: { section: string; items: { id: TabId; label: string; icon: typeof BarChart3 }[] }[] = [
  {
    section: 'Workspace',
    items: [
      { id: 'overview', label: 'Usage & Metrics', icon: BarChart3 },
      { id: 'keys', label: 'Virtual Keys', icon: KeyRound },
      { id: 'models', label: 'Models & Endpoints', icon: Box },
      { id: 'nodes', label: 'Compute Fleet', icon: Cpu },
      { id: 'projects', label: 'Teams & Projects', icon: FolderKanban },
    ],
  },
  {
    section: 'Developer & Security',
    items: [
      { id: 'playground', label: 'Test Playground', icon: Sparkles },
      { id: 'trust', label: 'Trust & Air-Gap', icon: ShieldCheck },
    ],
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [tokenInput, setTokenInput] = useState(() => getStoredToken());
  const [authRequired, setAuthRequired] = useState(false);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const [overview, setOverview] = useState<MetricsOverview | null>(null);
  const [nodes, setNodes] = useState<NodeItem[]>([]);
  const [deployments, setDeployments] = useState<DeploymentItem[]>([]);
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [airgap, setAirgap] = useState<AirgapSettings | null>(null);

  const showToast = useCallback((msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3200);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ov, nd, dp, ky, pr, lg, ag] = await Promise.all([
        api.getOverview(),
        api.getNodes(),
        api.getDeployments(),
        api.getKeys(),
        api.getProjects(),
        api.getAuditLogs(100),
        api.getAirgapSettings(),
      ]);
      setOverview(ov);
      setNodes(nd);
      setDeployments(dp);
      setKeys(ky);
      setProjects(pr);
      setLogs(lg);
      setAirgap(ag);
      setAuthRequired(false);
    } catch (err) {
      if (err instanceof AuthError) {
        setAuthRequired(true);
      } else {
        showToast(err instanceof Error ? err.message : 'Failed to load control plane data', 'error');
      }
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleSaveToken = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setStoredToken(tokenInput);
    showToast('Admin token updated', 'success');
    loadAll();
  };

  const currentTitle =
    NAV_ITEMS.flatMap((g) => g.items).find((i) => i.id === activeTab)?.label || 'Overview';

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900">
      {/* Left Sidebar (LiteLLM-style crisp white) */}
      <aside className="w-60 shrink-0 bg-white border-r border-slate-200 flex flex-col justify-between">
        <div>
          {/* Brand */}
          <div className="h-14 px-5 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shadow-xs">
                <Shield className="w-4 h-4" />
              </div>
              <span className="font-bold text-base tracking-tight text-slate-900">Cloyst</span>
            </div>
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              Air-Gap
            </span>
          </div>

          {/* Nav */}
          <nav className="p-3 space-y-5">
            {NAV_ITEMS.map((group) => (
              <div key={group.section}>
                <div className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {group.section}
                </div>
                <div className="space-y-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = activeTab === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                          active
                            ? 'bg-indigo-50 text-indigo-700'
                            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                        }`}
                      >
                        <Icon className={`w-4 h-4 ${active ? 'text-indigo-600' : 'text-slate-400'}`} />
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50/60">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-700">Gateway</span>
            <span className="inline-flex items-center gap-1.5 text-emerald-700 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> :8000
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
            <span>External Egress</span>
            <span className="font-mono text-emerald-700 font-medium">0 Bytes</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-14 bg-white border-b border-slate-200 sticky top-0 z-30 px-6 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-semibold text-slate-900">{currentTitle}</h1>
            <span className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <ShieldCheck className="w-3.5 h-3.5" /> Zero-Egress Active
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            <form onSubmit={handleSaveToken} className="flex items-center gap-1.5">
              <input
                id="adminTokenInput"
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Admin Token"
                aria-label="Admin Token"
                className="w-48 sm:w-56 px-3 py-1.5 rounded-lg border border-slate-200 bg-slate-50 text-xs text-slate-800 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-xs font-medium hover:bg-slate-800 transition-colors"
              >
                Connect
              </button>
            </form>

            <button
              onClick={loadAll}
              disabled={loading}
              title="Refresh data"
              className="p-2 rounded-lg border border-slate-200 bg-white text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </header>

        {/* Page Workspace */}
        <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
          {authRequired ? (
            <div className="max-w-md mx-auto mt-16 bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center">
              <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4">
                <Lock className="w-6 h-6" />
              </div>
              <h2 className="text-lg font-semibold text-slate-900">Unlock Cloyst Control Plane</h2>
              <p className="text-xs text-slate-500 mt-1.5">
                Enter your <code className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">CLOYST_ADMIN_TOKEN</code> to manage virtual keys, GPU nodes, and cryptographic audit logs.
              </p>
              <form onSubmit={handleSaveToken} className="mt-6 space-y-3 text-left">
                <input
                  type="password"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="Paste CLOYST_ADMIN_TOKEN..."
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
                >
                  Authenticate & Open Console
                </button>
              </form>
            </div>
          ) : (
            <>
              {activeTab === 'overview' && (
                <OverviewTab
                  overview={overview}
                  logs={logs}
                  onNavigate={(t) => setActiveTab(t)}
                />
              )}
              {activeTab === 'keys' && (
                <KeysTab
                  keys={keys}
                  projects={projects}
                  onRefresh={loadAll}
                  onToast={showToast}
                />
              )}
              {activeTab === 'models' && (
                <ModelsTab
                  deployments={deployments}
                  nodes={nodes}
                  onRefresh={loadAll}
                  onToast={showToast}
                />
              )}
              {activeTab === 'nodes' && (
                <NodesTab nodes={nodes} onRefresh={loadAll} onToast={showToast} />
              )}
              {activeTab === 'projects' && (
                <ProjectsTab projects={projects} onRefresh={loadAll} onToast={showToast} />
              )}
              {activeTab === 'playground' && <PlaygroundTab deployments={deployments} />}
              {activeTab === 'trust' && <TrustTab airgap={airgap} onToast={showToast} />}
            </>
          )}
        </main>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-5 right-5 z-50 px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium border ${
            toast.type === 'error'
              ? 'bg-rose-600 text-white border-rose-700'
              : 'bg-slate-900 text-white border-slate-800'
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { FolderKanban, Plus, X } from 'lucide-react';
import { api } from '../api';
import type { ProjectItem } from '../types';

interface Props {
  projects: ProjectItem[];
  onRefresh: () => void;
  onToast: (msg: string, type?: 'success' | 'error') => void;
}

export function ProjectsTab({ projects, onRefresh, onToast }: Props) {
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createProject({ name: name.trim(), description: description.trim() || undefined });
      setShowCreate(false);
      setName('');
      setDescription('');
      onToast('Project created', 'success');
      onRefresh();
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Failed to create project', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Teams & Projects</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Multi-tenant isolation boundaries for API keys, response caches, and audit attribution.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 shadow-xs transition-colors"
        >
          <Plus className="w-4 h-4" /> New Project
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-xs">
          <FolderKanban className="w-9 h-9 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-800">No projects created yet</h3>
          <p className="text-xs text-slate-500 mt-1">
            Group virtual keys and isolate exact-match caches by team or application.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {projects.map((p) => (
            <div key={p.id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
                      <FolderKanban className="w-4 h-4" />
                    </span>
                    <h3 className="text-sm font-semibold text-slate-900">{p.name}</h3>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">{p.id.slice(0, 8)}</span>
                </div>
                <p className="text-xs text-slate-500 mt-3">
                  {p.description || 'Isolated tenant workspace with scoped API keys and audit logs.'}
                </p>
              </div>
              <div className="pt-4 mt-4 border-t border-slate-100 text-[11px] text-slate-400">
                Created {new Date(p.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-[1px] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">Create Project</h3>
              <button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Project Name *</label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Core Engineering"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Description</label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional scope or cost-center notes"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                />
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
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { Send, Sparkles, Terminal } from 'lucide-react';
import { getGatewayBase } from '../api';
import type { DeploymentItem } from '../types';

interface Props {
  deployments: DeploymentItem[];
}

interface ChatMsg {
  role: 'user' | 'assistant' | 'error';
  content: string;
  meta?: string;
}

export function PlaygroundTab({ deployments }: Props) {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState(deployments[0]?.model_id || 'qwen2.5-airgap-demo');
  const [protocol, setProtocol] = useState<'openai' | 'anthropic'>('openai');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);

  const gatewayBase = getGatewayBase();

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || loading) return;
    const text = prompt.trim();
    setPrompt('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    const start = performance.now();

    try {
      const endpoint =
        protocol === 'openai'
          ? `${gatewayBase}/v1/chat/completions`
          : `${gatewayBase}/v1/messages`;

      const body =
        protocol === 'openai'
          ? { model, messages: [{ role: 'user', content: text }], stream: false }
          : { model, max_tokens: 512, messages: [{ role: 'user', content: text }] };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { Authorization: `Bearer ${apiKey.trim()}` } : {}),
        },
        body: JSON.stringify(body),
      });

      const elapsed = Math.round(performance.now() - start);
      const cacheHeader = res.headers.get('x-cloyst-cache');
      const data = await res.json();

      if (!res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'error',
            content: typeof data?.detail === 'string' ? data.detail : JSON.stringify(data),
            meta: `HTTP ${res.status} · ${elapsed} ms`,
          },
        ]);
      } else {
        const reply =
          protocol === 'openai'
            ? data?.choices?.[0]?.message?.content || JSON.stringify(data)
            : data?.content?.[0]?.text || JSON.stringify(data);
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: reply,
            meta: `${protocol.toUpperCase()} · ${elapsed} ms${cacheHeader ? ` · Cache: ${cacheHeader}` : ''}`,
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'error',
          content: err instanceof Error ? err.message : 'Network error reaching gateway',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Config Panel */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4 h-fit">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-slate-900">Gateway Connection</h3>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">API Protocol</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setProtocol('openai')}
              className={`py-2 px-3 rounded-lg text-xs font-medium border transition-colors ${
                protocol === 'openai'
                  ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              OpenAI (/v1/chat)
            </button>
            <button
              type="button"
              onClick={() => setProtocol('anthropic')}
              className={`py-2 px-3 rounded-lg text-xs font-medium border transition-colors ${
                protocol === 'anthropic'
                  ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              Anthropic (/v1/messages)
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Model</label>
          {deployments.length > 0 ? (
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white font-mono"
            >
              {deployments.map((d) => (
                <option key={d.id} value={d.model_id}>
                  {d.model_id}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono"
            />
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Virtual API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="cloyst_sk_live_..."
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm font-mono"
          />
          <p className="text-[11px] text-slate-400 mt-1">
            Mint a key in the <strong>Virtual Keys</strong> tab first.
          </p>
        </div>

        <div className="pt-2 border-t border-slate-100 text-[11px] font-mono text-slate-500">
          Target: {gatewayBase}
        </div>
      </div>

      {/* Chat Area */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col h-[540px] overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span className="text-sm font-semibold text-slate-900">Test Key & Inference Playground</span>
          </div>
          <button
            onClick={() => setMessages([])}
            className="text-xs text-slate-500 hover:text-slate-800"
          >
            Clear
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-slate-50/40">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-slate-400">
              <Sparkles className="w-8 h-8 text-slate-300 mb-2" />
              <p className="text-sm font-medium text-slate-600">Send a test prompt through the Gateway</p>
              <p className="text-xs text-slate-400 mt-1 max-w-sm">
                Exercises HMAC key auth, offline PII guardrails, exact-match cache, and bidirectional OpenAI ↔ Anthropic translation.
              </p>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[82%] rounded-xl px-4 py-3 text-sm ${
                    m.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : m.role === 'error'
                      ? 'bg-rose-50 border border-rose-200 text-rose-800'
                      : 'bg-white border border-slate-200 text-slate-800 shadow-2xs'
                  }`}
                >
                  <div className="whitespace-pre-wrap break-words">{m.content}</div>
                  {m.meta && (
                    <div
                      className={`mt-1.5 text-[10px] font-mono ${
                        m.role === 'error' ? 'text-rose-500' : 'text-slate-400'
                      }`}
                    >
                      {m.meta}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <form onSubmit={handleSend} className="p-3 border-t border-slate-200 bg-white flex items-center gap-2">
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Type a prompt (try including an email or SSN to test offline PII redaction)..."
            className="flex-1 px-3.5 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={loading || !prompt.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            <Send className="w-4 h-4" /> {loading ? 'Sending…' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  );
}

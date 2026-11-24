import { useState } from 'react';
import {
  CheckCircle2,
  Fingerprint,
  GlobeLock,
  Lock,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../api';
import type { AirgapSettings, AuditVerifyResult } from '../types';

interface Props {
  airgap: AirgapSettings | null;
  onToast: (msg: string, type?: 'success' | 'error') => void;
}

export function TrustTab({ airgap, onToast }: Props) {
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<AuditVerifyResult | null>(null);

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await api.verifyAuditChain();
      setVerifyResult(res);
      onToast(
        res.valid
          ? `Cryptographic chain verified (${res.verified_record_count} records)`
          : 'Audit chain integrity violation detected!',
        res.valid ? 'success' : 'error'
      );
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Verification failed', 'error');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Trust, Air-Gap & Compliance</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Zero-egress boundary enforcement, cryptographic SHA-256 audit log verification, and offline safety guardrails.
        </p>
      </div>

      {/* Audit Chain Verifier Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
              <Fingerprint className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                Immutable SHA-256 Hash-Chained Audit Log
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-xl">
                Every inference event is cryptographically chained to its predecessor (<code className="font-mono bg-slate-100 px-1 rounded">prev_record_hash</code>). Run live verification to prove zero post-hoc tampering for NIST AU-9 / SOC 2 audits.
              </p>
            </div>
          </div>
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 shadow-xs shrink-0 disabled:opacity-50"
          >
            <ShieldCheck className="w-4 h-4" />
            {verifying ? 'Verifying Chain…' : 'Verify Audit Chain'}
          </button>
        </div>

        {verifyResult && (
          <div
            className={`mt-5 p-4 rounded-lg border flex items-start gap-3 ${
              verifyResult.valid
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50 border-rose-200 text-rose-900'
            }`}
          >
            {verifyResult.valid ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            )}
            <div className="text-sm">
              <p className="font-semibold">
                {verifyResult.valid
                  ? `Integrity Confirmed — ${verifyResult.verified_record_count} chained record(s) verified`
                  : 'Tampering Detected in Audit Chain'}
              </p>
              {verifyResult.error && (
                <p className="text-xs font-mono mt-1 text-rose-700">{verifyResult.error}</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Air-Gap & Guardrails Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Air-Gap Status */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
                <GlobeLock className="w-5 h-5" />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Runtime Egress Guard</h3>
                <p className="text-xs text-slate-500">Application-layer air-gap enforcement (NIST SC-7)</p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              {airgap?.air_gap_mode ? 'ENFORCED' : 'PERMISSIVE'}
            </span>
          </div>

          <div>
            <div className="text-xs font-medium text-slate-600 mb-2">Permitted Local Egress Allowlist</div>
            <div className="flex flex-wrap gap-2">
              {(airgap?.egress_allowlist || ['127.0.0.1', 'localhost', 'host.docker.internal']).map((host) => (
                <span
                  key={host}
                  className="px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200 font-mono text-xs text-slate-700"
                >
                  {host}
                </span>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Runtime Environment</span>
            <span className="font-mono font-medium text-slate-800">{airgap?.environment || 'development'}</span>
          </div>
        </div>

        {/* Offline Guardrails */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-lg bg-violet-50 text-violet-600">
                <Lock className="w-5 h-5" />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">100% Offline Safety Guardrails</h3>
                <p className="text-xs text-slate-500">Zero third-party SaaS calls — runs locally in-process</p>
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
              ACTIVE
            </span>
          </div>

          <div className="space-y-2.5">
            {[
              {
                name: 'PII Redaction (HIPAA 164.312)',
                desc: 'Automatically masks SSNs, credit cards, phone numbers, and email addresses.',
              },
              {
                name: 'Credential & Secret Scanning',
                desc: 'Detects and strips AWS keys, private keys, and Bearer tokens before inference.',
              },
              {
                name: 'Prompt Injection Heuristics',
                desc: 'Blocks common system-prompt override and jailbreak patterns locally.',
              },
            ].map((g) => (
              <div key={g.name} className="p-3 rounded-lg bg-slate-50 border border-slate-100 flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="text-xs font-semibold text-slate-800">{g.name}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{g.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { Empty, ErrorBanner, Loading, Shell } from "@/components/ui";
import type { AuditEntry } from "@/types";

function AuditInner() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await api.audit());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Shell title="Audit log">
      {error ? (
        <ErrorBanner error={error} onRetry={load} />
      ) : loading ? (
        <Loading />
      ) : entries.length === 0 ? (
        <Empty label="No audit entries." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400">
              <th>At</th><th>Action</th><th>Resource</th><th>Request</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((a, i) => (
              <tr key={i} className="border-t border-slate-800">
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td className="font-mono">{a.action}</td>
                <td>{a.resource_type ?? "—"}</td>
                <td className="font-mono text-xs">{a.request_id ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Shell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <AuditInner />
    </RequireAuth>
  );
}

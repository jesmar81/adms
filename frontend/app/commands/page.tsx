"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { Badge, Empty, ErrorBanner, Loading, Shell, inputCls, statusTone } from "@/components/ui";
import type { DeviceCommand } from "@/types";

function CommandsInner() {
  const [commands, setCommands] = useState<DeviceCommand[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCommands(await api.commands(status || undefined));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Shell title="Commands">
      <div className="mb-3">
        <select aria-label="status filter" className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["pending", "sent", "confirmed", "failed", "expired", "cancelled"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      {error ? (
        <ErrorBanner error={error} onRetry={load} />
      ) : loading ? (
        <Loading />
      ) : commands.length === 0 ? (
        <Empty label="No commands." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400">
              <th>Wire ID</th><th>Type</th><th>Status</th><th>Return</th><th>Queued</th><th>Confirmed</th>
            </tr>
          </thead>
          <tbody>
            {commands.map((c) => (
              <tr key={c.id} className="border-t border-slate-800">
                <td className="font-mono">{c.protocol_command_id}</td>
                <td>{c.command_type}</td>
                <td><Badge tone={statusTone(c.status)}>{c.status}</Badge></td>
                <td>{c.return_code ?? "—"}</td>
                <td>{new Date(c.queued_at).toLocaleString()}</td>
                <td>{c.confirmed_at ? new Date(c.confirmed_at).toLocaleString() : "—"}</td>
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
      <CommandsInner />
    </RequireAuth>
  );
}

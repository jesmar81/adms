"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RequireAuth, useAuth } from "@/lib/auth";
import { Badge, Empty, ErrorBanner, Loading, Shell, btnCls, statusTone } from "@/components/ui";
import type { AttendanceRow, DeviceCommand } from "@/types";

function DashboardInner() {
  const { logout } = useAuth();
  const router = useRouter();
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const [recent, setRecent] = useState<AttendanceRow[]>([]);
  const [pending, setPending] = useState<DeviceCommand[]>([]);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, r, p] = await Promise.all([
        api.summary(),
        api.attendance({ limit: "10" }),
        api.commands("pending"),
      ]);
      setSummary(s);
      setRecent(r);
      setPending(p.slice(0, 10));
    } catch (err) {
      setError(err);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  return (
    <Shell title="Dashboard">
      <div className="mb-4 flex justify-end">
        <button className={btnCls} onClick={signOut}>
          Sign out
        </button>
      </div>
      {error ? (
        <ErrorBanner error={error} onRetry={load} />
      ) : !summary ? (
        <Loading />
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              ["Devices", summary.total ?? 0],
              ["Online", summary.online ?? 0],
              ["Offline", summary.offline ?? 0],
              ["Pending cmds", summary.pending_commands ?? 0],
              ["Failed cmds", summary.failed_commands ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="rounded border border-slate-800 bg-slate-900 p-4">
                <p className="text-2xl font-bold">{value}</p>
                <p className="text-sm text-slate-400">{label}</p>
              </div>
            ))}
          </div>
          <h2 className="mb-2 text-lg font-semibold">Recent attendance</h2>
          {recent.length === 0 ? (
            <Empty label="No attendance yet." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400">
                  <th>PIN</th>
                  <th>Recorded at</th>
                  <th>Status</th>
                  <th>Verify</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r) => (
                  <tr key={r.id} className="border-t border-slate-800">
                    <td>{r.device_user_pin}</td>
                    <td>{new Date(r.recorded_at).toLocaleString()}</td>
                    <td>{r.status}</td>
                    <td>{r.verify_mode}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <h2 className="mb-2 mt-6 text-lg font-semibold">Pending commands</h2>
          {pending.length === 0 ? (
            <Empty label="No pending commands." />
          ) : (
            <ul className="flex flex-col gap-1 text-sm">
              {pending.map((c) => (
                <li key={c.id} className="flex gap-2">
                  <Badge tone={statusTone(c.status)}>{c.status}</Badge>
                  <span className="font-mono">
                    C:{c.protocol_command_id}:{c.command_type}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Shell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <DashboardInner />
    </RequireAuth>
  );
}

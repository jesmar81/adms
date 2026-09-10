"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { Badge, Empty, ErrorBanner, Loading, Shell, inputCls, statusTone } from "@/components/ui";
import type { Device } from "@/types";

function DevicesInner() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDevices(await api.devices(status ? { status } : {}));
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
    <Shell title="Devices">
      <div className="mb-3">
        <select aria-label="status filter" className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="unknown">unknown</option>
          <option value="disabled">disabled</option>
        </select>
      </div>
      {error ? (
        <ErrorBanner error={error} onRetry={load} />
      ) : loading ? (
        <Loading />
      ) : devices.length === 0 ? (
        <Empty label="No devices registered yet. Point a SpeedFace-V5LP at /iclock/*." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400">
              <th>Serial</th>
              <th>Name</th>
              <th>Firmware</th>
              <th>IP</th>
              <th>Status</th>
              <th>Last activity</th>
            </tr>
          </thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id} className="border-t border-slate-800">
                <td>
                  <Link className="text-sky-400 underline" href={`/devices/${d.id}`}>
                    {d.serial_number}
                  </Link>
                </td>
                <td>{d.name ?? "—"}</td>
                <td>{d.firmware_version ?? "—"}</td>
                <td>{d.ip_address ?? "—"}</td>
                <td>
                  <Badge tone={statusTone(d.derived_status ?? d.status)}>
                    {d.derived_status ?? d.status}
                  </Badge>
                </td>
                <td>{d.last_activity_at ? new Date(d.last_activity_at).toLocaleString() : "—"}</td>
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
      <DevicesInner />
    </RequireAuth>
  );
}

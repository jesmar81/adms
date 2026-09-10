"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RequireAuth } from "@/lib/auth";
import { Empty, ErrorBanner, Loading, Pagination, Shell, inputCls } from "@/components/ui";
import type { AttendanceRow, Device } from "@/types";

const LIMIT = 50;

function AttendanceInner() {
  const [rows, setRows] = useState<AttendanceRow[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [filters, setFilters] = useState({ device_id: "", pin: "", date_from: "", date_to: "", status: "", verify_mode: "", work_code: "" });
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { limit: String(LIMIT), offset: String(offset) };
      if (filters.device_id) params.device_id = filters.device_id;
      if (filters.pin) params.pin = filters.pin;
      if (filters.date_from) params.date_from = new Date(filters.date_from).toISOString();
      if (filters.date_to) params.date_to = new Date(filters.date_to).toISOString();
      if (filters.status) params.status = filters.status;
      if (filters.verify_mode) params.verify_mode = filters.verify_mode;
      if (filters.work_code) params.work_code = filters.work_code;
      setRows(await api.attendance(params));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    void api.devices().then(setDevices).catch(() => undefined);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function set<K extends keyof typeof filters>(k: K, v: string) {
    setOffset(0);
    setFilters((f) => ({ ...f, [k]: v }));
  }

  return (
    <Shell title="Attendance">
      <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-4">
        <select aria-label="device" className={inputCls} value={filters.device_id} onChange={(e) => set("device_id", e.target.value)}>
          <option value="">All devices</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>{d.serial_number}</option>
          ))}
        </select>
        <input aria-label="pin" className={inputCls} placeholder="PIN" value={filters.pin} onChange={(e) => set("pin", e.target.value)} />
        <input aria-label="from" className={inputCls} type="datetime-local" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} />
        <input aria-label="to" className={inputCls} type="datetime-local" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} />
        <input aria-label="status" className={inputCls} placeholder="Status" value={filters.status} onChange={(e) => set("status", e.target.value)} />
        <input aria-label="verify mode" className={inputCls} placeholder="Verify mode" value={filters.verify_mode} onChange={(e) => set("verify_mode", e.target.value)} />
        <input aria-label="work code" className={inputCls} placeholder="Work code" value={filters.work_code} onChange={(e) => set("work_code", e.target.value)} />
      </div>
      {error ? (
        <ErrorBanner error={error} onRetry={load} />
      ) : loading ? (
        <Loading />
      ) : rows.length === 0 ? (
        <Empty label="No records for these filters." />
      ) : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400">
                <th>PIN</th><th>Recorded at</th><th>Status</th><th>Verify</th><th>Work code</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-800">
                  <td>{r.device_user_pin}</td>
                  <td>{new Date(r.recorded_at).toLocaleString()}</td>
                  <td>{r.status}</td>
                  <td>{r.verify_mode}</td>
                  <td>{r.work_code ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination offset={offset} limit={LIMIT} hasMore={rows.length === LIMIT} onPage={setOffset} />
        </>
      )}
    </Shell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <AttendanceInner />
    </RequireAuth>
  );
}

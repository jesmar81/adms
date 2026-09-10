"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Can, RequireAuth } from "@/lib/auth";
import {
  Badge,
  Empty,
  ErrorBanner,
  Loading,
  Shell,
  btnCls,
  inputCls,
  statusTone,
} from "@/components/ui";
import type { AttendanceRow, Device, DeviceCommand, DeviceEvent, DeviceUser } from "@/types";

const COUNTERS = [
  "UserCount",
  "FPCount",
  "FaceCount",
  "AttLogCount",
  "TransactionCount",
  "MaxUserCount",
  "MaxAttLogCount",
  "MaxFingerCount",
  "MaxFaceCount",
];

const COMMAND_TYPES = [
  "INFO",
  "CHECK",
  "LOG",
  "QUERY_USERINFO",
  "GET_OPTION",
  "UPDATE_USERINFO",
  "DELETE_USERINFO",
];

function DetailInner({ id }: { id: string }) {
  const [device, setDevice] = useState<Device | null>(null);
  const [tab, setTab] = useState<"users" | "attendance" | "commands" | "events">("users");
  const [users, setUsers] = useState<DeviceUser[]>([]);
  const [attendance, setAttendance] = useState<AttendanceRow[]>([]);
  const [commands, setCommands] = useState<DeviceCommand[]>([]);
  const [events, setEvents] = useState<DeviceEvent[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [tz, setTz] = useState("");
  const [cmdType, setCmdType] = useState("CHECK");
  const [cmdParams, setCmdParams] = useState("{}");
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await api.device(id);
      setDevice(d);
      const [u, a, c, e] = await Promise.all([
        api.deviceUsers(id),
        api.attendance({ device_id: id, limit: "20" }),
        api.deviceCommands(id),
        api.deviceEvents(id),
      ]);
      setUsers(u);
      setAttendance(a);
      setCommands(c);
      setEvents(e);
    } catch (err) {
      setError(err);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveTz() {
    setNotice(null);
    try {
      const d = await api.patchDevice(id, { timezone: tz });
      setDevice(d);
      setNotice("Timezone updated.");
    } catch (err) {
      setError(err);
    }
  }

  async function queue() {
    setNotice(null);
    let params: Record<string, string> = {};
    try {
      params = cmdParams.trim() ? (JSON.parse(cmdParams) as Record<string, string>) : {};
    } catch {
      setError(new Error("Command params must be valid JSON."));
      return;
    }
    try {
      await api.queueCommand(id, cmdType, params);
      setNotice(`Queued ${cmdType}.`);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  if (error && !device) return <Shell title="Device"><ErrorBanner error={error} onRetry={load} /></Shell>;
  if (!device) return <Shell title="Device"><Loading /></Shell>;

  return (
    <Shell title={`Device ${device.serial_number}`}>
      {error ? <ErrorBanner error={error} onRetry={load} /> : null}
      {notice && <p className="mb-2 text-sm text-green-300">{notice}</p>}
      <div className="mb-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
        {[
          ["Name", device.name ?? "—"],
          ["Model", device.model ?? "—"],
          ["Firmware", device.firmware_version ?? "—"],
          ["Platform", device.platform ?? "—"],
          ["IP", device.ip_address ?? "—"],
          ["MAC", device.mac_address ?? "—"],
          ["Timezone", device.timezone],
          ["Status", device.derived_status ?? device.status],
          ["Last activity", device.last_activity_at ? new Date(device.last_activity_at).toLocaleString() : "—"],
        ].map(([k, v]) => (
          <div key={k} className="rounded border border-slate-800 bg-slate-900 p-2">
            <p className="text-xs text-slate-400">{k}</p>
            <p>{v}</p>
          </div>
        ))}
      </div>
      <div className="mb-4 rounded border border-slate-800 bg-slate-900 p-3 text-sm">
        <p className="mb-2 font-semibold">Device counters (from GET OPTION)</p>
        <div className="grid grid-cols-3 gap-2 md:grid-cols-5">
          {COUNTERS.map((k) => (
            <div key={k}>
              <p className="text-xs text-slate-400">{k}</p>
              <p>{device.options[k] ?? "—"}</p>
            </div>
          ))}
        </div>
      </div>
      <Can permission="devices.write">
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <input aria-label="timezone" className={inputCls} placeholder="America/Mexico_City" value={tz} onChange={(e) => setTz(e.target.value)} />
          <button className={btnCls} onClick={saveTz}>Set timezone</button>
        </div>
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <select aria-label="command type" className={inputCls} value={cmdType} onChange={(e) => setCmdType(e.target.value)}>
            {COMMAND_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <input aria-label="command params JSON" className={inputCls} value={cmdParams} onChange={(e) => setCmdParams(e.target.value)} placeholder='{"key":"DeviceName"}' />
          <button className={btnCls} onClick={queue}>Queue command</button>
        </div>
      </Can>
      <div className="mb-2 flex gap-2 text-sm">
        {(["users", "attendance", "commands", "events"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded border px-3 py-1 ${tab === t ? "border-sky-600 bg-sky-950" : "border-slate-700"}`}>
            {t}
          </button>
        ))}
      </div>
      {tab === "users" &&
        (users.length === 0 ? <Empty label="No users synced." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-slate-400"><th>PIN</th><th>Name</th><th>Priv</th><th>Sync</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-800">
                  <td>{u.pin}</td><td>{u.name}</td><td>{u.privilege}</td>
                  <td><Badge tone={statusTone(u.sync_state)}>{u.sync_state}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      {tab === "attendance" &&
        (attendance.length === 0 ? <Empty label="No attendance." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-slate-400"><th>PIN</th><th>At</th><th>Status</th><th>Verify</th><th>Work</th></tr></thead>
            <tbody>
              {attendance.map((r) => (
                <tr key={r.id} className="border-t border-slate-800">
                  <td>{r.device_user_pin}</td><td>{new Date(r.recorded_at).toLocaleString()}</td>
                  <td>{r.status}</td><td>{r.verify_mode}</td><td>{r.work_code ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      {tab === "commands" &&
        (commands.length === 0 ? <Empty label="No commands." /> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-slate-400"><th>ID</th><th>Type</th><th>Status</th><th>Return</th><th>Queued</th></tr></thead>
            <tbody>
              {commands.map((c) => (
                <tr key={c.id} className="border-t border-slate-800">
                  <td className="font-mono">{c.protocol_command_id}</td><td>{c.command_type}</td>
                  <td><Badge tone={statusTone(c.status)}>{c.status}</Badge></td>
                  <td>{c.return_code ?? "—"}</td><td>{new Date(c.queued_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      {tab === "events" &&
        (events.length === 0 ? <Empty label="No events." /> : (
          <ul className="flex flex-col gap-1 text-sm">
            {events.map((e, i) => (
              <li key={i} className="flex gap-2">
                <Badge tone={e.severity === "warning" || e.severity === "error" ? "red" : "gray"}>{e.type}</Badge>
                <span className="text-slate-400">{new Date(e.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        ))}
    </Shell>
  );
}

export default function Page({ params }: { params: { id: string } }) {
  return (
    <RequireAuth>
      <DetailInner id={params.id} />
    </RequireAuth>
  );
}

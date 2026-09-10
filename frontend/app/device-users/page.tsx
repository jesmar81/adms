"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Can, RequireAuth } from "@/lib/auth";
import { Badge, Empty, ErrorBanner, Loading, Shell, btnCls, inputCls, statusTone } from "@/components/ui";
import type { Device, DeviceUser } from "@/types";

function UsersInner() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [users, setUsers] = useState<DeviceUser[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [pin, setPin] = useState("");
  const [name, setName] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await api.deviceUsers(deviceId || undefined));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  useEffect(() => {
    void api.devices().then((d) => {
      setDevices(d);
      if (d.length > 0) setDeviceId(d[0].id);
    }).catch((err: unknown) => setError(err));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    setNotice(null);
    try {
      await api.createDeviceUser(deviceId, { pin, name, privilege: 0, card: "" });
      setNotice(`User ${pin} queued (pending device confirmation).`);
      setPin("");
      setName("");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function remove(id: string) {
    setNotice(null);
    try {
      await api.deleteDeviceUser(id);
      setNotice("Delete requested (pending device confirmation).");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function queryUsers() {
    setNotice(null);
    try {
      await api.queueCommand(deviceId, "QUERY_USERINFO", {});
      setNotice("User query queued — the device will push USERINFO.");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Shell title="Device users">
      {error ? <ErrorBanner error={error} onRetry={load} /> : null}
      {notice && <p className="mb-2 text-sm text-green-300">{notice}</p>}
      <div className="mb-3 flex flex-wrap gap-2">
        <select aria-label="device" className={inputCls} value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>{d.serial_number}</option>
          ))}
        </select>
        <Can permission="commands.execute">
          <button className={btnCls} onClick={queryUsers}>Query users on device</button>
        </Can>
      </div>
      <Can permission="device_users.write">
        <div className="mb-4 flex flex-wrap gap-2">
          <input aria-label="pin" className={inputCls} placeholder="PIN" value={pin} onChange={(e) => setPin(e.target.value)} />
          <input aria-label="name" className={inputCls} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <button className={btnCls} onClick={create}>Create + queue</button>
        </div>
      </Can>
      {loading ? (
        <Loading />
      ) : users.length === 0 ? (
        <Empty label="No users on this device yet." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400">
              <th>PIN</th><th>Name</th><th>Priv</th><th>Card</th><th>Sync</th><th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-800">
                <td>{u.pin}</td><td>{u.name}</td><td>{u.privilege}</td>
                <td>{u.card_number ?? "—"}</td>
                <td><Badge tone={statusTone(u.sync_state)}>{u.sync_state}</Badge></td>
                <td>
                  <Can permission="device_users.delete">
                    <button className="text-red-300 underline" onClick={() => void remove(u.id)}>
                      Delete
                    </button>
                  </Can>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-3 text-xs text-slate-500">
        Rows are desired-state: <em>pending</em> means the command is queued, <em>synced</em> means the device confirmed.
      </p>
    </Shell>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <UsersInner />
    </RequireAuth>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Can, RequireAuth } from "@/lib/auth";
import { Badge, Empty, ErrorBanner, Loading, Shell, btnCls, inputCls } from "@/components/ui";
import type { AdminUser } from "@/types";

function UsersInner() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await api.users());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    setNotice(null);
    try {
      await api.createUser({ username, email, password });
      setNotice(`User ${username} created.`);
      setUsername("");
      setEmail("");
      setPassword("");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function toggleActive(u: AdminUser) {
    setNotice(null);
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function remove(id: string) {
    setNotice(null);
    try {
      await api.deleteUser(id);
      setNotice("User disabled.");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <Shell title="Application users">
      {error ? <ErrorBanner error={error} onRetry={load} /> : null}
      {notice && <p className="mb-2 text-sm text-green-300">{notice}</p>}
      <Can permission="users.write">
        <div className="mb-4 flex flex-wrap gap-2">
          <input aria-label="username" className={inputCls} placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <input aria-label="email" className={inputCls} placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input aria-label="password" className={inputCls} type="password" placeholder="Password (10+ chars)" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className={btnCls} onClick={create}>Create user</button>
        </div>
      </Can>
      {loading ? (
        <Loading />
      ) : users.length === 0 ? (
        <Empty label="No users." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400">
              <th>Username</th><th>Email</th><th>Roles</th><th>Active</th><th>Superuser</th><th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-slate-800">
                <td>{u.username}</td><td>{u.email}</td>
                <td>{u.roles.join(", ") || "—"}</td>
                <td><Badge tone={u.is_active ? "green" : "red"}>{u.is_active ? "yes" : "no"}</Badge></td>
                <td>{u.is_superuser ? "yes" : "no"}</td>
                <td className="flex gap-2">
                  <Can permission="users.write">
                    <button className="underline" onClick={() => void toggleActive(u)}>
                      {u.is_active ? "Disable" : "Enable"}
                    </button>
                  </Can>
                  <Can permission="users.delete">
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

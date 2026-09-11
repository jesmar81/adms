"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import type { AdminUser } from "@/types";

const COLUMNS: Column<AdminUser>[] = [
  {
    key: "user",
    header: "Usuario",
    render: (u) => (
      <span>
        <span className="block font-medium">{u.username}</span>
        <span className="mt-0.5 block text-[13px] text-zinc-500">{u.email}</span>
      </span>
    ),
  },
  {
    key: "roles",
    header: "Roles",
    render: (u) =>
      u.roles.length > 0 ? (
        <span className="flex flex-wrap gap-1.5">
          {u.roles.map((r) => (
            <Badge key={r} tone="zinc">
              {r}
            </Badge>
          ))}
        </span>
      ) : (
        <span className="text-zinc-500">—</span>
      ),
  },
  {
    key: "active",
    header: "Activo",
    render: (u) => <Badge tone={u.is_active ? "emerald" : "red"}>{u.is_active ? "Sí" : "No"}</Badge>,
  },
  {
    key: "super",
    header: "Superusuario",
    render: (u) => <span className="text-zinc-600">{u.is_superuser ? "Sí" : "No"}</span>,
  },
];

export default function Page() {
  const { notify } = useToast();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState(false);

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
    if (creating) return;
    setCreating(true);
    try {
      await api.createUser({ username: username.trim(), email: email.trim(), password });
      notify(`Usuario ${username.trim()} creado`, { tone: "success" });
      setUsername("");
      setEmail("");
      setPassword("");
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(u: AdminUser) {
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      notify(u.is_active ? `Usuario ${u.username} deshabilitado` : `Usuario ${u.username} habilitado`, {
        tone: "success",
      });
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    try {
      await api.deleteUser(pendingDelete.id);
      notify(`Usuario ${pendingDelete.username} deshabilitado`, { tone: "success" });
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Usuarios"
        description="Cuentas de acceso a la plataforma. La eliminación deshabilita la cuenta, nunca la borra."
        crumbs={[{ label: "Usuarios" }]}
      />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}

      <Can permission="users.write">
        <Card className="mb-4 p-5">
          <h2 className="text-[15px] font-semibold tracking-tight">Crear usuario</h2>
          <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_auto]">
            <Field label="Usuario">
              {(id) => (
                <Input id={id} placeholder="Nombre de usuario" value={username} onChange={(e) => setUsername(e.target.value)} />
              )}
            </Field>
            <Field label="Correo">
              {(id) => (
                <Input id={id} type="email" placeholder="usuario@ejemplo.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              )}
            </Field>
            <Field label="Contraseña" hint="Mínimo 10 caracteres">
              {(id) => (
                <Input id={id} type="password" placeholder="••••••••••" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              )}
            </Field>
            <div className="flex items-end">
              <Button variant="primary" onClick={() => void create()} loading={creating}>
                Crear usuario
              </Button>
            </div>
          </div>
        </Card>
      </Can>

      {loading ? (
        <LoadingState rows={5} />
      ) : (
        <DataTable
          ariaLabel="Usuarios de la aplicación"
          columns={[
            ...COLUMNS,
            {
              key: "actions",
              header: "",
              render: (u) => (
                <span className="flex justify-end gap-3">
                  <Can permission="users.write">
                    <button
                      onClick={() => void toggleActive(u)}
                      className="text-[13px] text-zinc-600 transition-colors hover:text-zinc-900"
                    >
                      {u.is_active ? "Deshabilitar" : "Habilitar"}
                    </button>
                  </Can>
                  <Can permission="users.delete">
                    <button
                      onClick={() => setPendingDelete(u)}
                      className="text-[13px] text-red-600 transition-colors hover:text-red-700"
                    >
                      Eliminar
                    </button>
                  </Can>
                </span>
              ),
            },
          ]}
          data={users}
          keyOf={(u) => u.id}
          renderCard={(u) => (
            <div>
              <div className="flex items-center justify-between gap-3">
                <p className="truncate text-sm font-medium">{u.username}</p>
                <Badge tone={u.is_active ? "emerald" : "red"}>{u.is_active ? "Activo" : "Inactivo"}</Badge>
              </div>
              <p className="mt-0.5 truncate text-[13px] text-zinc-500">{u.email}</p>
              <div className="mt-2.5 flex gap-3">
                <Can permission="users.write">
                  <button
                    onClick={() => void toggleActive(u)}
                    className="text-[13px] text-zinc-600 transition-colors hover:text-zinc-900"
                  >
                    {u.is_active ? "Deshabilitar" : "Habilitar"}
                  </button>
                </Can>
                <Can permission="users.delete">
                  <button
                    onClick={() => setPendingDelete(u)}
                    className="text-[13px] text-red-600 transition-colors hover:text-red-700"
                  >
                    Eliminar
                  </button>
                </Can>
              </div>
            </div>
          )}
          empty={<EmptyState title="Sin usuarios" description="Aún no hay cuentas registradas." />}
        />
      )}

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Deshabilitar usuario"
        description={`La cuenta ${pendingDelete?.username ?? ""} perderá el acceso, pero su historial se conserva.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={() => void confirmDelete()} loading={deleting}>
              Deshabilitar
            </Button>
          </>
        }
      >
        <p className="text-sm text-zinc-500">Esta acción puede revertirse volviendo a habilitar la cuenta.</p>
      </Modal>
    </>
  );
}

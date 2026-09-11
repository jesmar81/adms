"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import { StatusDot } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import type { Device, DeviceUser } from "@/types";

const COLUMNS: Column<DeviceUser>[] = [
  { key: "pin", header: "PIN", render: (u) => <span className="font-mono font-medium">{u.pin}</span> },
  { key: "name", header: "Nombre", render: (u) => u.name || "—" },
  {
    key: "priv",
    header: "Privilegio",
    render: (u) => <span className="tabular-nums">{u.privilege}</span>,
  },
  { key: "card", header: "Tarjeta", render: (u) => <span className="font-mono text-[13px]">{u.card_number ?? "—"}</span> },
  {
    key: "sync",
    header: "Sincronización",
    render: (u) => <StatusDot status={u.sync_state} />,
  },
];

export default function Page() {
  const { notify } = useToast();
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [users, setUsers] = useState<DeviceUser[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [pin, setPin] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DeviceUser | null>(null);
  const [deleting, setDeleting] = useState(false);

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
    void api
      .devices()
      .then((d) => {
        setDevices(d);
        if (d.length > 0) setDeviceId(d[0].id);
      })
      .catch((err: unknown) => setError(err));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create() {
    if (creating || !deviceId || !pin.trim()) return;
    setCreating(true);
    try {
      await api.createDeviceUser(deviceId, { pin: pin.trim(), name: name.trim(), privilege: 0, card: "" });
      notify(`Usuario ${pin.trim()} encolado`, {
        message: "Pendiente de confirmación del reloj.",
        tone: "success",
      });
      setPin("");
      setName("");
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setCreating(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    try {
      await api.deleteDeviceUser(pendingDelete.id);
      notify("Eliminación solicitada", {
        message: "Pendiente de confirmación del reloj.",
        tone: "success",
      });
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setDeleting(false);
    }
  }

  async function queryUsers() {
    if (!deviceId) return;
    try {
      await api.queueCommand(deviceId, "QUERY_USERINFO", {});
      notify("Consulta encolada", { message: "El reloj enviará su lista de usuarios.", tone: "success" });
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <PageHeader
        title="Personal en reloj"
        description="Usuarios dados de alta en cada dispositivo y su estado de sincronización."
        crumbs={[{ label: "Personal en reloj" }]}
      />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}

      <Card className="mb-4 p-5">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-end">
          <div className="sm:w-64">
            <Field label="Reloj">
              {(id) => (
                <Select id={id} value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name ?? d.serial_number}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Can permission="commands.execute">
            <Button onClick={() => void queryUsers()} disabled={!deviceId}>
              Consultar usuarios del reloj
            </Button>
          </Can>
        </div>
        <Can permission="device_users.write">
          <div className="mt-4 grid grid-cols-1 gap-2.5 border-t border-line-subtle pt-4 sm:grid-cols-[1fr_1fr_auto]">
            <Field label="PIN">
              {(id) => (
                <Input id={id} placeholder="Ej. 2001" value={pin} onChange={(e) => setPin(e.target.value)} />
              )}
            </Field>
            <Field label="Nombre">
              {(id) => (
                <Input id={id} placeholder="Nombre del empleado" value={name} onChange={(e) => setName(e.target.value)} />
              )}
            </Field>
            <div className="flex items-end">
              <Button variant="primary" onClick={() => void create()} loading={creating} disabled={!pin.trim()}>
                Crear y encolar
              </Button>
            </div>
          </div>
        </Can>
      </Card>

      {loading ? (
        <LoadingState rows={6} />
      ) : (
        <DataTable
          ariaLabel="Personal en el reloj"
          columns={[
            ...COLUMNS,
            {
              key: "actions",
              header: "",
              render: (u) => (
                <Can permission="device_users.delete">
                  <button
                    onClick={() => setPendingDelete(u)}
                    className="text-[13px] text-red-600 transition-colors hover:text-red-700"
                  >
                    Eliminar
                  </button>
                </Can>
              ),
            },
          ]}
          data={users}
          keyOf={(u) => u.id}
          renderCard={(u) => (
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-sm font-medium">{u.pin}</p>
                <p className="mt-0.5 truncate text-[13px] text-zinc-500">{u.name || "Sin nombre"}</p>
              </div>
              <StatusDot status={u.sync_state} />
            </div>
          )}
          empty={
            <EmptyState
              title="Sin personal en este reloj"
              description="Crea el primer usuario o consulta los que ya tiene el dispositivo."
            />
          }
        />
      )}
      <p className="mt-4 text-xs leading-relaxed text-zinc-500">
        Las filas representan el estado deseado: <em>pendiente</em> significa que el comando está
        encolado y <em>sincronizado</em> que el reloj ya lo confirmó.
      </p>

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Eliminar usuario del reloj"
        description={`Se solicitará al dispositivo eliminar el PIN ${pendingDelete?.pin ?? ""}. El registro desaparece cuando el reloj lo confirme.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={() => void confirmDelete()} loading={deleting}>
              Solicitar eliminación
            </Button>
          </>
        }
      >
        <p className="text-sm text-zinc-500">
          Estado actual: <span className="font-medium text-zinc-700">{pendingDelete?.sync_state}</span>
        </p>
      </Modal>
    </>
  );
}

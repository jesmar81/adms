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
import type { Device, DeviceUser, Person } from "@/types";

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
  const [people, setPeople] = useState<Person[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [pin, setPin] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DeviceUser | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [linkingUser, setLinkingUser] = useState<DeviceUser | null>(null);
  const [personId, setPersonId] = useState("");
  const [linking, setLinking] = useState(false);

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
    void api
      .corporateGroups()
      .then(async (groups) => {
        setPeople((await Promise.all(groups.map((group) => api.people(group.id)))).flat());
      })
      .catch(() => setPeople([]));
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

  function openLink(user: DeviceUser) {
    setLinkingUser(user);
    setPersonId(user.person_id ?? "");
  }

  async function saveLink() {
    if (!linkingUser || linking) return;
    setLinking(true);
    try {
      await api.updateDeviceUser(linkingUser.id, { person_id: personId || null });
      notify(personId ? "PIN vinculado a persona" : "Vinculación eliminada", {
        message: "Las checadas de este PIN aparecerán en el expediente correspondiente.",
        tone: "success",
      });
      setLinkingUser(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setLinking(false);
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
        <p className="mt-3 text-xs leading-relaxed text-sky-800">Modo de validación activo: consulta, alta, cambio y baja quedan encolados para el reloj. Usa sólo un PIN de laboratorio y captura su respuesta.</p>
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
              key: "person",
              header: "Persona",
              render: (u) => {
                const person = people.find((candidate) => candidate.id === u.person_id);
                return person
                  ? [person.first_name, person.last_name, person.second_last_name].filter(Boolean).join(" ")
                  : u.person_id ? "Vinculada" : "Sin vincular";
              },
            },
            {
              key: "actions",
              header: "",
              render: (u) => (
                <div className="flex items-center gap-3">
                  <Can permission="device_users.write">
                    <button onClick={() => openLink(u)} className="text-[13px] text-accent-700 transition-colors hover:text-accent-900">
                      Vincular
                    </button>
                  </Can>
                  <Can permission="device_users.delete">
                    <button
                      onClick={() => setPendingDelete(u)}
                      className="text-[13px] text-red-600 transition-colors hover:text-red-700"
                    >
                      Eliminar
                    </button>
                  </Can>
                </div>
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
                <p className="mt-1 text-xs text-zinc-500">{u.person_id ? "Vinculado a persona" : "Sin vincular"}</p>
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

      <Modal
        open={linkingUser !== null}
        onClose={() => setLinkingUser(null)}
        title="Vincular PIN a una persona"
        description={`El PIN ${linkingUser?.pin ?? ""} conservará su identidad en el reloj. Esta relación permite consultar sus checadas en el expediente.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setLinkingUser(null)}>Cancelar</Button>
            <Button variant="primary" onClick={() => void saveLink()} loading={linking}>Guardar vinculación</Button>
          </>
        }
      >
        <Field label="Persona">
          {(id) => (
            <Select id={id} value={personId} onChange={(event) => setPersonId(event.target.value)}>
              <option value="">Sin vincular</option>
              {people.map((person) => <option key={person.id} value={person.id}>{[person.first_name, person.last_name, person.second_last_name].filter(Boolean).join(" ")}</option>)}
            </Select>
          )}
        </Field>
        {!people.length ? <p className="mt-3 text-xs text-zinc-500">No hay personas disponibles o tu usuario no tiene permiso para consultarlas.</p> : null}
      </Modal>
    </>
  );
}

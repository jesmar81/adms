"use client";

import { Link2, Radio, ShieldAlert, Trash2 } from "lucide-react";
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
import type { Device, DeviceCapabilityProfile, DeviceUser, Person } from "@/types";

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
  {
    key: "received",
    header: "Último recibido",
    render: (u) => <span className="text-xs text-muted">{u.last_synced_at ? new Date(u.last_synced_at).toLocaleString("es-MX") : "Sin confirmar"}</span>,
  },
];

export default function Page() {
  const { notify } = useToast();
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [capabilities, setCapabilities] = useState<DeviceCapabilityProfile | null>(null);
  const [capabilityError, setCapabilityError] = useState<unknown>(null);
  const [users, setUsers] = useState<DeviceUser[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [pin, setPin] = useState("");
  const [name, setName] = useState("");
  const [createPersonId, setCreatePersonId] = useState("");
  const [creating, setCreating] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DeviceUser | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [linkingUser, setLinkingUser] = useState<DeviceUser | null>(null);
  const [personId, setPersonId] = useState("");
  const [linking, setLinking] = useState(false);

  const load = useCallback(async (showLoading = false) => {
    if (!deviceId) {
      setUsers([]);
      setLoading(false);
      return;
    }
    if (showLoading) setLoading(true);
    setError(null);
    try {
      setUsers(await api.deviceUsers(deviceId || undefined));
      setRefreshedAt(new Date());
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
        setDeviceId((current) => d.some((device) => device.id === current) ? current : d[0]?.id ?? "");
      })
      .catch((err: unknown) => setError(err));
  }, []);

  useEffect(() => {
    setCapabilities(null);
    setCapabilityError(null);
    if (!deviceId) return;
    void api.deviceCapabilities(deviceId).then(setCapabilities).catch(setCapabilityError);
  }, [deviceId]);

  useEffect(() => {
    void api
      .corporateGroups()
      .then(async (groups) => {
        setPeople((await Promise.all(groups.map((group) => api.people(group.id)))).flat());
      })
      .catch(() => setPeople([]));
  }, []);

  useEffect(() => {
    void load(true);
  }, [load]);

  useEffect(() => {
    if (!deviceId) return;
    const refresh = () => {
      if (document.visibilityState === "visible") void load();
    };
    const interval = window.setInterval(refresh, 10_000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [deviceId, load]);

  const canQueryUsers = capabilities?.safe_commands.includes("QUERY_USERINFO") ?? false;
  const canWriteUsers = capabilities?.safe_commands.includes("UPDATE_USERINFO") ?? false;
  const selectedDevice = devices.find((device) => device.id === deviceId);

  async function create() {
    if (creating || !deviceId || !pin.trim()) return;
    setCreating(true);
    try {
      await api.createDeviceUser(deviceId, { person_id: createPersonId || null, pin: pin.trim(), name: name.trim(), privilege: 0, card: "" });
      notify(`Usuario ${pin.trim()} encolado`, {
        message: createPersonId ? "PIN vinculado al trabajador; pendiente de confirmación del reloj." : "Pendiente de confirmación del reloj.",
        tone: "success",
      });
      setPin("");
      setName("");
      setCreatePersonId("");
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
    if (!deviceId || !canQueryUsers) return;
    try {
      await api.queueCommand(deviceId, "QUERY_USERINFO", {});
      notify("Consulta encolada", { message: "Esperando que el reloj entregue su catálogo; el panel se actualiza automáticamente.", tone: "success" });
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <PageHeader
        title="Personal en reloj"
        description="Catálogo recibido de cada reloj, PIN vinculado al trabajador y estado confirmado por el dispositivo."
        crumbs={[{ label: "Personal en reloj" }]}
      />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}

      <Card className="mb-4 p-5">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-end">
          <div className="w-full sm:max-w-sm">
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
          <div className="flex flex-col gap-2 sm:items-end">
            <Can permission="commands.execute">
            <Button onClick={() => void queryUsers()} disabled={!deviceId || !canQueryUsers}>
              Consultar usuarios del reloj
            </Button>
            </Can>
            <p className="inline-flex items-center gap-1.5 text-[11px] text-muted" aria-live="polite"><Radio className="h-3.5 w-3.5 text-emerald-400" aria-hidden />Actualización automática · {refreshedAt ? `consulta al servidor ${refreshedAt.toLocaleTimeString("es-MX")}` : "conectando"}</p>
          </div>
        </div>
        {capabilityError ? <p className="mt-3 text-xs text-amber-300">No se pudo validar el perfil del reloj; las operaciones de consulta y escritura quedan deshabilitadas por seguridad.</p> : null}
        {capabilities && !canQueryUsers ? <div className="mt-4 flex gap-3 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3.5 text-sm"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" aria-hidden /><div><p className="font-medium text-foreground">Consulta remota pendiente de validar para este reloj</p><p className="mt-1 leading-relaxed text-muted">{capabilities.profile === "security_push_acc" ? `${selectedDevice?.model || "Este dispositivo"} se identifica como A&C / Security PUSH. Las capturas disponibles confirman checadas en vivo, pero aún no una respuesta con usuarios. No se enviará el comando legacy hasta validar el protocolo real. Cuando el reloj entregue USERINFO, el catálogo aparecerá aquí automáticamente.` : "El perfil del reloj no confirma todavía el comando de consulta de usuarios."}</p></div></div> : null}
        <Can permission="device_users.write">
          <div className="mt-4 grid grid-cols-1 gap-2.5 border-t border-line-subtle pt-4 sm:grid-cols-2 xl:grid-cols-[1fr_1.4fr_1.4fr_auto]">
            <Field label="PIN">
              {(id) => (
                <Input id={id} placeholder="Ej. 2001" value={pin} onChange={(e) => setPin(e.target.value)} />
              )}
            </Field>
            <Field label="Trabajador">
              {(id) => (
                <Select id={id} value={createPersonId} onChange={(event) => {
                  const selectedId = event.target.value;
                  setCreatePersonId(selectedId);
                  const selectedPerson = people.find((person) => person.id === selectedId);
                  if (selectedPerson) setName([selectedPerson.first_name, selectedPerson.last_name, selectedPerson.second_last_name].filter(Boolean).join(" "));
                }}>
                  <option value="">Sin vincular</option>
                  {people.map((person) => <option key={person.id} value={person.id}>{[person.first_name, person.last_name, person.second_last_name].filter(Boolean).join(" ")}</option>)}
                </Select>
              )}
            </Field>
            <Field label="Nombre enviado al reloj" hint="Se propone como nombres + apellido paterno + materno; puedes ajustarlo al límite del dispositivo.">
              {(id) => (
                <Input id={id} placeholder="Nombre para el reloj" maxLength={255} value={name} onChange={(e) => setName(e.target.value)} />
              )}
            </Field>
            <div className="flex items-end">
              <Button variant="primary" onClick={() => void create()} loading={creating} disabled={!pin.trim() || !canWriteUsers}>
                Encolar alta
              </Button>
            </div>
          </div>
          {capabilities && !canWriteUsers ? <p className="mt-2 text-xs text-muted">El alta desde este sistema permanece bloqueada hasta validar la escritura de usuarios en el firmware.</p> : null}
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
          renderCard={(u) => {
            const linkedPerson = people.find((person) => person.id === u.person_id);
            const linkedName = linkedPerson ? [linkedPerson.first_name, linkedPerson.last_name, linkedPerson.second_last_name].filter(Boolean).join(" ") : null;
            return <div>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-sm font-medium">PIN {u.pin}</p>
                  <p className="mt-0.5 truncate text-[13px] text-zinc-500">{u.name || "Sin nombre"}</p>
                  <p className="mt-1 truncate text-xs text-zinc-500">{linkedName ?? (u.person_id ? "Vinculado a persona" : "Sin vincular")}</p>
                </div>
                <StatusDot status={u.sync_state} />
              </div>
              <div className="mt-3 flex gap-2 border-t border-line-subtle pt-2">
                <Can permission="device_users.write"><Button size="sm" variant="secondary" icon={<Link2 className="h-4 w-4" />} onClick={() => openLink(u)}>Vincular persona</Button></Can>
                <Can permission="device_users.delete"><Button size="sm" variant="ghost" icon={<Trash2 className="h-4 w-4" />} className="text-red-600" onClick={() => setPendingDelete(u)}>Eliminar</Button></Can>
              </div>
            </div>;
          }}
          empty={
            <EmptyState
              title="Sin personal en este reloj"
              description={canQueryUsers ? "Solicita la consulta para importar el catálogo que el reloj confirme." : "Cuando el dispositivo transmita su catálogo de usuarios al servidor, aparecerá aquí y podrás vincular cada PIN."}
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

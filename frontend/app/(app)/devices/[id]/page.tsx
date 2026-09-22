"use client";

import { use, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { StatusDot, Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import type { AttendanceRow, Device, DeviceCapabilityProfile, DeviceCommand, DeviceEvent, DeviceUser } from "@/types";

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

const TABS = [
  { id: "users", label: "Personal" },
  { id: "attendance", label: "Marcaciones" },
  { id: "commands", label: "Comandos" },
  { id: "events", label: "Eventos" },
] as const;

const CAPABILITY_LABELS: Record<string, string> = {
  realtime_attendance: "Checadas en tiempo real",
  realtime_state: "Estado del equipo",
  command_poll: "Consulta de comandos",
  info_command: "Inventario del equipo",
  user_querydata_received: "Consulta de usuarios",
};

type Tab = (typeof TABS)[number]["id"];

const USER_COLUMNS: Column<DeviceUser>[] = [
  { key: "pin", header: "PIN", render: (u) => <span className="font-mono">{u.pin}</span> },
  { key: "name", header: "Nombre", render: (u) => u.name || "—" },
  {
    key: "priv",
    header: "Privilegio",
    render: (u) => <span className="tabular-nums">{u.privilege}</span>,
  },
  {
    key: "sync",
    header: "Sincronización",
    render: (u) => <StatusDot status={u.sync_state} />,
  },
];

const ATT_COLUMNS: Column<AttendanceRow>[] = [
  { key: "pin", header: "PIN", render: (r) => <span className="font-mono">{r.device_user_pin}</span> },
  { key: "at", header: "Fecha", render: (r) => formatDateTime(r.recorded_at) },
  {
    key: "status",
    header: "Estado",
    render: (r) => <span className="tabular-nums">{r.status}</span>,
  },
  {
    key: "verify",
    header: "Verificación",
    render: (r) => <span className="tabular-nums">{r.verify_mode}</span>,
  },
  { key: "work", header: "Código", render: (r) => r.work_code ?? "—" },
];

const CMD_COLUMNS: Column<DeviceCommand>[] = [
  {
    key: "id",
    header: "ID",
    render: (c) => <span className="font-mono tabular-nums">#{c.protocol_command_id}</span>,
  },
  { key: "type", header: "Tipo", render: (c) => <span className="font-mono text-[13px]">{c.command_type}</span> },
  {
    key: "status",
    header: "Estado",
    render: (c) => <StatusDot status={c.status} />,
  },
  { key: "ret", header: "Retorno", render: (c) => c.return_code ?? "—" },
  { key: "queued", header: "Encolado", render: (c) => formatDateTime(c.queued_at) },
];

function DetailInner({ id }: { id: string }) {
  const { notify } = useToast();
  const [device, setDevice] = useState<Device | null>(null);
  const [capabilities, setCapabilities] = useState<DeviceCapabilityProfile | null>(null);
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<DeviceUser[]>([]);
  const [attendance, setAttendance] = useState<AttendanceRow[]>([]);
  const [commands, setCommands] = useState<DeviceCommand[]>([]);
  const [events, setEvents] = useState<DeviceEvent[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [tz, setTz] = useState("");
  const [cmdType, setCmdType] = useState("CHECK");
  const [cmdParams, setCmdParams] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [queuing, setQueuing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const d = await api.device(id);
      setDevice(d);
      const [u, a, c, e, profile] = await Promise.all([
        api.deviceUsers(id),
        api.attendance({ device_id: id, limit: "20" }),
        api.deviceCommands(id),
        api.deviceEvents(id),
        api.deviceCapabilities(id),
      ]);
      setUsers(u);
      setAttendance(a);
      setCommands(c);
      setEvents(e);
      setCapabilities(profile);
    } catch (err) {
      setError(err);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveTz() {
    if (saving) return;
    setSaving(true);
    try {
      const d = await api.patchDevice(id, { timezone: tz });
      setDevice(d);
      setTz("");
      notify("Zona horaria actualizada", { tone: "success" });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function queue() {
    if (queuing) return;
    let params: Record<string, string> = {};
    try {
      params = cmdParams.trim() ? (JSON.parse(cmdParams) as Record<string, string>) : {};
    } catch {
      setError(new Error("Los parámetros del comando deben ser JSON válido."));
      return;
    }
    setQueuing(true);
    try {
      await api.queueCommand(id, cmdType, params);
      notify(`Comando ${cmdType} encolado`, { tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setQueuing(false);
    }
  }

  if (error && !device)
    return <ErrorState error={error} onRetry={() => void load()} />;
  if (!device) return <LoadingState rows={6} />;

  const status = device.derived_status ?? device.status;
  const commandTypes = COMMAND_TYPES;
  const info: [string, string][] = [
    ["Nombre", device.name ?? "—"],
    ["Modelo", device.model ?? "—"],
    ["Firmware", device.firmware_version ?? "—"],
    ["Plataforma", device.platform ?? "—"],
    ["IP", device.ip_address ?? "—"],
    ["MAC", device.mac_address ?? "—"],
    ["Zona horaria", device.timezone],
    ["Última actividad", formatDateTime(device.last_activity_at)],
  ];

  return (
    <>
      <PageHeader
        title={device.name ?? device.serial_number}
        description={`Serial ${device.serial_number}`}
        crumbs={[{ label: "Relojes", href: "/devices" }, { label: device.serial_number }]}
        actions={<StatusDot status={status} />}
      />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}

      <Card className="p-5 md:p-6">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
          {info.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="text-xs text-zinc-500">{k}</dt>
              <dd className="mt-0.5 truncate text-sm" title={v}>
                {v}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card className="mt-4 p-5 md:p-6">
        <h2 className="text-[15px] font-semibold tracking-tight">Contadores del dispositivo</h2>
        <p className="mt-0.5 text-[13px] text-zinc-500">Reportados por el reloj vía GET OPTION</p>
        <dl className="mt-4 grid grid-cols-3 gap-x-6 gap-y-4 md:grid-cols-5">
          {COUNTERS.map((k) => (
            <div key={k} className="min-w-0">
              <dt className="truncate font-mono text-xs text-zinc-500" title={k}>
                {k}
              </dt>
              <dd className="mt-0.5 text-sm tabular-nums">{device.options[k] ?? "—"}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {capabilities ? (
        <Card className="mt-4 p-5 md:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-[15px] font-semibold tracking-tight">Perfil de integración</h2>
              <p className="mt-0.5 text-[13px] text-zinc-500">
                Estado derivado de tráfico y confirmaciones reales del reloj.
              </p>
              {capabilities.firmware ? (
                <p className="mt-1 text-xs text-zinc-500">Firmware: {capabilities.firmware}</p>
              ) : null}
            </div>
            <Badge tone={capabilities.profile === "security_push_acc" ? "sky" : "zinc"}>
              {capabilities.profile === "security_push_acc" ? "Security PUSH A&C" : "ADMS legacy"}
            </Badge>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {Object.entries(capabilities.confirmed).map(([key, confirmed]) => (
              <div key={key} className="rounded-xl border border-line-subtle bg-zinc-50/60 px-3 py-2">
                <p className="text-xs text-zinc-500">{CAPABILITY_LABELS[key] ?? key}</p>
                <p className={`mt-1 text-sm font-medium ${confirmed ? "text-emerald-700" : "text-zinc-500"}`}>
                  {confirmed ? "Confirmado" : "Pendiente"}
                </p>
              </div>
            ))}
          </div>
          {capabilities.next_validation ? <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900"><p className="font-medium">Estado de validación del protocolo</p><p className="mt-1 text-sky-800">{capabilities.next_validation}</p></div> : null}
        </Card>
      ) : null}

      <Can permission="devices.write">
        <Card className="mt-4 p-5 md:p-6">
          <h2 className="text-[15px] font-semibold tracking-tight">Administrar</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Field label="Zona horaria" hint="Ej. America/Mexico_City">
              {(fieldId) => (
                <span className="flex gap-2">
                  <Input
                    id={fieldId}
                    placeholder="America/Mexico_City"
                    value={tz}
                    onChange={(e) => setTz(e.target.value)}
                  />
                  <Button onClick={() => void saveTz()} loading={saving} disabled={!tz.trim()}>
                    Guardar
                  </Button>
                </span>
              )}
            </Field>
            <div className="flex flex-col gap-4">
              <Field label="Encolar comando">
                {(fieldId) => (
                  <span className="flex gap-2">
                    <Select
                      id={fieldId}
                      aria-label="Tipo de comando"
                      value={cmdType}
                      onChange={(e) => setCmdType(e.target.value)}
                    >
                      {commandTypes.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </Select>
                    <Button onClick={() => void queue()} loading={queuing}>
                      Encolar
                    </Button>
                  </span>
                )}
              </Field>
              <Field label="Parámetros (JSON)" hint='Ej. {"key":"DeviceName"}'>
                {(fieldId) => (
                  <Input
                    id={fieldId}
                    value={cmdParams}
                    onChange={(e) => setCmdParams(e.target.value)}
                    placeholder='{"key":"DeviceName"}'
                    className="font-mono"
                  />
                )}
              </Field>
              <p className="text-xs leading-relaxed text-sky-800">Para este ciclo de validación, usa un PIN de laboratorio y conserva la captura completa de la respuesta del reloj.</p>
            </div>
          </div>
        </Card>
      </Can>

      <div className="mb-4 mt-6 flex gap-1 rounded-xl border border-line-subtle bg-surface-card p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            aria-pressed={tab === t.id}
            className={`flex-1 rounded-lg px-3 py-2 text-sm transition-colors duration-200 ${
              tab === t.id
                ? "bg-black/[0.06] font-medium text-zinc-900"
                : "text-zinc-500 hover:bg-black/[0.03] hover:text-zinc-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "users" && (
        <DataTable
          ariaLabel="Personal en el reloj"
          columns={USER_COLUMNS}
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
          empty={<EmptyState title="Sin personal sincronizado" description="Aún no hay usuarios en este reloj." />}
        />
      )}
      {tab === "attendance" && (
        <DataTable
          ariaLabel="Marcaciones del reloj"
          columns={ATT_COLUMNS}
          data={attendance}
          keyOf={(r) => r.id}
          renderCard={(r) => (
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-sm font-medium">PIN {r.device_user_pin}</p>
                <p className="mt-0.5 text-[13px] text-zinc-500">{formatDateTime(r.recorded_at)}</p>
              </div>
              <span className="text-sm tabular-nums text-zinc-600">{r.status}</span>
            </div>
          )}
          empty={<EmptyState title="Sin marcaciones" description="Este reloj aún no reporta asistencia." />}
        />
      )}
      {tab === "commands" && (
        <DataTable
          ariaLabel="Comandos del reloj"
          columns={CMD_COLUMNS}
          data={commands}
          keyOf={(c) => c.id}
          renderCard={(c) => (
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-sm font-medium">#{c.protocol_command_id}</p>
                <p className="mt-0.5 font-mono text-xs text-zinc-500">{c.command_type}</p>
              </div>
              <StatusDot status={c.status} />
            </div>
          )}
          empty={<EmptyState title="Sin comandos" description="No se han encolado comandos para este reloj." />}
        />
      )}
      {tab === "events" && (
        events.length === 0 ? (
          <EmptyState title="Sin eventos" description="No hay eventos registrados para este reloj." />
        ) : (
          <Card className="p-2">
            <ul className="flex flex-col divide-y divide-line-subtle">
              {events.map((e, i) => (
                <li key={`${e.created_at}-${i}`} className="flex items-center justify-between gap-3 px-3 py-3">
                  <Badge tone={e.severity === "warning" || e.severity === "error" ? "red" : "zinc"}>
                    {e.type}
                  </Badge>
                  <span className="shrink-0 text-[13px] text-zinc-500">{formatDateTime(e.created_at)}</span>
                </li>
              ))}
            </ul>
          </Card>
        )
      )}
    </>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <DetailInner id={id} />;
}

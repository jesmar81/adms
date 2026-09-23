"use client";

import { Link2, Save, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable, Pagination } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import type { AttendanceRow, Device, DeviceUser, Employment } from "@/types";

const LIMIT = 50;

const COLUMNS: Column<AttendanceRow>[] = [
  {
    key: "pin",
    header: "PIN",
    render: (r) => <span className="font-mono font-medium">{r.device_user_pin}</span>,
  },
  { key: "at", header: "Fecha y hora", render: (r) => formatDateTime(r.recorded_at) },
  {
    key: "attribution",
    header: "Atribución",
    render: (r) => (
      <span className={`rounded-full px-2 py-1 text-xs font-medium ${r.attribution_status === "assigned" ? "bg-emerald-50 text-emerald-700" : r.attribution_status === "ambiguous" ? "bg-amber-50 text-amber-700" : "bg-zinc-100 text-zinc-600"}`}>
        {r.attribution_status === "assigned" ? "Asignada" : r.attribution_status === "ambiguous" ? "Ambigua" : "Sin asignar"}
      </span>
    ),
  },
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

export default function Page() {
  const { notify } = useToast();
  const [rows, setRows] = useState<AttendanceRow[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceUsers, setDeviceUsers] = useState<DeviceUser[]>([]);
  const [employments, setEmployments] = useState<Employment[]>([]);
  const [filters, setFilters] = useState({
    device_id: "",
    pin: "",
    date_from: "",
    date_to: "",
    status: "",
    verify_mode: "",
    work_code: "",
  });
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState<AttendanceRow | null>(null);
  const [employmentId, setEmploymentId] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { limit: String(LIMIT), offset: String(offset) };
      if (filters.device_id) params.device_id = filters.device_id;
      if (filters.pin.trim()) params.pin = filters.pin.trim();
      if (filters.date_from) params.date_from = new Date(filters.date_from).toISOString();
      if (filters.date_to) params.date_to = new Date(filters.date_to).toISOString();
      if (filters.status.trim()) params.status = filters.status.trim();
      if (filters.verify_mode.trim()) params.verify_mode = filters.verify_mode.trim();
      if (filters.work_code.trim()) params.work_code = filters.work_code.trim();
      setRows(await api.attendance(params));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    void Promise.allSettled([api.devices(), api.deviceUsers(), api.employments()]).then(
      ([loadedDevices, loadedUsers, loadedEmployments]) => {
        if (loadedDevices.status === "fulfilled") setDevices(loadedDevices.value);
        if (loadedUsers.status === "fulfilled") setDeviceUsers(loadedUsers.value);
        if (loadedEmployments.status === "fulfilled") setEmployments(loadedEmployments.value);
      },
    );
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function set<K extends keyof typeof filters>(k: K, v: string) {
    setOffset(0);
    setFilters((f) => ({ ...f, [k]: v }));
  }

  const hasFilters = Object.values(filters).some((v) => v !== "");
  const linkedPersonId = resolving
    ? deviceUsers.find(
        (row) => row.device_id === resolving.device_id && row.pin === resolving.device_user_pin,
      )?.person_id
    : null;
  const candidateEmployments = employments.filter(
    (employment) => employment.person_id === linkedPersonId,
  );

  function openResolution(row: AttendanceRow) {
    const personId = deviceUsers.find(
      (deviceUser) =>
        deviceUser.device_id === row.device_id && deviceUser.pin === row.device_user_pin,
    )?.person_id;
    const first = employments.find((employment) => employment.person_id === personId);
    setResolving(row);
    setEmploymentId(row.employment_id ?? first?.id ?? "");
    setReason("");
  }

  async function resolveAttribution() {
    if (!resolving || !employmentId || reason.trim().length < 5 || saving) return;
    setSaving(true);
    try {
      const updated = await api.resolveAttendanceAttribution(
        resolving.id,
        employmentId,
        reason.trim(),
      );
      setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setResolving(null);
      notify("Checada atribuida", {
        message: "La evidencia original se conservó y la resolución quedó auditada.",
        tone: "success",
      });
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Marcaciones"
        description="Registros de asistencia reportados por los relojes."
        crumbs={[{ label: "Marcaciones" }]}
      />
      <div className="mb-5 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <Field label="Reloj">
          {(id) => (
            <Select id={id} value={filters.device_id} onChange={(e) => set("device_id", e.target.value)}>
              <option value="">Todos los relojes</option>
              {devices.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name ?? d.serial_number}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="PIN">
          {(id) => (
            <Input id={id} placeholder="Ej. 1001" value={filters.pin} onChange={(e) => set("pin", e.target.value)} />
          )}
        </Field>
        <Field label="Desde">
          {(id) => (
            <Input id={id} type="datetime-local" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} />
          )}
        </Field>
        <Field label="Hasta">
          {(id) => (
            <Input id={id} type="datetime-local" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} />
          )}
        </Field>
        <Field label="Estado">
          {(id) => (
            <Input id={id} placeholder="Ej. 0" inputMode="numeric" value={filters.status} onChange={(e) => set("status", e.target.value)} />
          )}
        </Field>
        <Field label="Verificación">
          {(id) => (
            <Input id={id} placeholder="Ej. 15" inputMode="numeric" value={filters.verify_mode} onChange={(e) => set("verify_mode", e.target.value)} />
          )}
        </Field>
        <Field label="Código de trabajo">
          {(id) => (
            <Input id={id} placeholder="Work code" value={filters.work_code} onChange={(e) => set("work_code", e.target.value)} />
          )}
        </Field>
        <div className="flex items-end">
          <button
            onClick={() => {
              setFilters({ device_id: "", pin: "", date_from: "", date_to: "", status: "", verify_mode: "", work_code: "" });
              setOffset(0);
            }}
            disabled={!hasFilters}
            className="h-10 rounded-lg border border-line-subtle bg-white px-4 text-sm text-zinc-600 transition-colors duration-200 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Limpiar filtros
          </button>
        </div>
      </div>
      {error ? (
        <ErrorState error={error} onRetry={() => void load()} />
      ) : loading ? (
        <LoadingState rows={8} />
      ) : (
        <>
          <DataTable
            ariaLabel="Marcaciones"
            columns={[...COLUMNS, { key: "actions", header: "", render: (row) => <Can permission="attendance.write"><Button variant="ghost" size="sm" icon={<Link2 className="h-4 w-4" />} className="w-8 !px-0" aria-label="Resolver atribución" title="Resolver atribución" onClick={() => openResolution(row)} /></Can> }]}
            data={rows}
            keyOf={(r) => r.id}
            renderCard={(r) => (
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                  <p className="font-mono text-sm font-medium">PIN {r.device_user_pin}</p>
                  <p className="mt-0.5 text-[13px] text-zinc-500">{formatDateTime(r.recorded_at)}</p>
                  </div>
                  <span className="shrink-0 text-sm text-zinc-600">{r.attribution_status === "assigned" ? "Asignada" : r.attribution_status === "ambiguous" ? "Ambigua" : "Sin asignar"}</span>
                </div>
                <div className="mt-3 flex items-center justify-between gap-3 border-t border-line-subtle pt-2 text-sm text-zinc-600"><span>{r.status} · {r.verify_mode}</span><Can permission="attendance.write"><Button size="sm" variant="secondary" icon={<Link2 className="h-4 w-4" />} onClick={() => openResolution(r)}>Resolver</Button></Can></div>
              </div>
            )}
            empty={
              <EmptyState
                title="Sin registros"
                description="No hay marcaciones para los filtros aplicados."
              />
            }
          />
          {rows.length > 0 && (
            <Pagination offset={offset} limit={LIMIT} hasMore={rows.length === LIMIT} onPage={setOffset} />
          )}
        </>
      )}
      <Modal open={resolving !== null} onClose={() => setResolving(null)} title="Resolver atribución de checada" description="Asigna esta evidencia a un solo empleo. El registro original del reloj no se modifica." footer={<><Button variant="ghost" icon={<X className="h-4 w-4" />} className="w-10 !px-0" aria-label="Cancelar" title="Cancelar" onClick={() => setResolving(null)} /><Button variant="primary" icon={<Save className="h-4 w-4" />} className="w-10 !px-0" aria-label="Guardar atribución" title="Guardar atribución" onClick={() => void resolveAttribution()} loading={saving} disabled={!employmentId || reason.trim().length < 5} /></>}><div className="grid gap-3"><Field label="Empleo">{(id) => <Select id={id} value={employmentId} onChange={(event) => setEmploymentId(event.target.value)}><option value="">Selecciona</option>{candidateEmployments.map((employment) => <option key={employment.id} value={employment.id}>{employment.employee_number} · {employment.position ?? "Sin puesto"}</option>)}</Select>}</Field><Field label="Motivo de la resolución">{(id) => <Input id={id} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Ej. Reloj sin sucursal al momento de la captura" />}</Field>{candidateEmployments.length === 0 ? <p className="text-sm text-amber-700">Primero vincula el PIN con una persona y confirma que tenga un empleo vigente.</p> : null}</div></Modal>
    </>
  );
}

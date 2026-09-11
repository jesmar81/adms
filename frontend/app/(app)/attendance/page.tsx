"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable, Pagination } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import type { AttendanceRow, Device } from "@/types";

const LIMIT = 50;

const COLUMNS: Column<AttendanceRow>[] = [
  {
    key: "pin",
    header: "PIN",
    render: (r) => <span className="font-mono font-medium">{r.device_user_pin}</span>,
  },
  { key: "at", header: "Fecha y hora", render: (r) => formatDateTime(r.recorded_at) },
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
  const [rows, setRows] = useState<AttendanceRow[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
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
    void api.devices().then(setDevices).catch(() => undefined);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function set<K extends keyof typeof filters>(k: K, v: string) {
    setOffset(0);
    setFilters((f) => ({ ...f, [k]: v }));
  }

  const hasFilters = Object.values(filters).some((v) => v !== "");

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
            columns={COLUMNS}
            data={rows}
            keyOf={(r) => r.id}
            renderCard={(r) => (
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-mono text-sm font-medium">PIN {r.device_user_pin}</p>
                  <p className="mt-0.5 text-[13px] text-zinc-500">{formatDateTime(r.recorded_at)}</p>
                </div>
                <span className="text-sm tabular-nums text-zinc-600">estado {r.status}</span>
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
    </>
  );
}

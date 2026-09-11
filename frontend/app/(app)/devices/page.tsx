"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { StatusDot } from "@/components/ui/badge";
import { SearchInput, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { AddDeviceButton, NoDevicesEmpty } from "@/components/devices/AddDeviceModal";
import type { Device } from "@/types";

const FILTERS = [
  { value: "", label: "Todos los estados" },
  { value: "online", label: "En línea" },
  { value: "offline", label: "Sin conexión" },
  { value: "stale", label: "Inactivos" },
  { value: "unknown", label: "Desconocidos" },
  { value: "disabled", label: "Deshabilitados" },
];

function deviceStatus(d: Device): string {
  return d.derived_status ?? d.status;
}

const COLUMNS: Column<Device>[] = [
  {
    key: "device",
    header: "Dispositivo",
    render: (d) => (
      <span>
        <Link
          href={`/devices/${d.id}`}
          className="block font-medium text-zinc-900 transition-colors hover:text-accent"
        >
          {d.name ?? d.serial_number}
        </Link>
        <span className="mt-0.5 block font-mono text-xs text-zinc-500">{d.serial_number}</span>
      </span>
    ),
  },
  {
    key: "ip",
    header: "IP",
    render: (d) => <span className="font-mono text-[13px] text-zinc-600">{d.ip_address ?? "—"}</span>,
  },
  {
    key: "model",
    header: "Modelo",
    render: (d) => <span className="text-zinc-600">{d.model ?? d.platform ?? "—"}</span>,
  },
  {
    key: "status",
    header: "Estado",
    render: (d) => <StatusDot status={deviceStatus(d)} />,
  },
  {
    key: "activity",
    header: "Última actividad",
    render: (d) => (
      <span title={d.last_activity_at ?? undefined} className="text-zinc-600">
        {formatRelative(d.last_activity_at)}
      </span>
    ),
  },
];

function DeviceCard({ device }: { device: Device }) {
  return (
    <Link href={`/devices/${device.id}`} className="block">
      <span className="flex items-start justify-between gap-3">
        <span className="min-w-0">
          <span className="block truncate text-[15px] font-medium">
            {device.name ?? device.serial_number}
          </span>
          <span className="mt-0.5 block truncate font-mono text-xs text-zinc-500">
            {device.serial_number} · {device.ip_address ?? "sin IP"}
          </span>
        </span>
        <StatusDot status={deviceStatus(device)} />
      </span>
      <span className="mt-3 block text-xs text-zinc-500">
        Última actividad: {formatRelative(device.last_activity_at)}
      </span>
    </Link>
  );
}

export default function Page() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDevices(await api.devices());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return devices.filter((d) => {
      if (status && deviceStatus(d) !== status) return false;
      if (!q) return true;
      return [d.serial_number, d.name ?? "", d.ip_address ?? ""].some((v) =>
        v.toLowerCase().includes(q),
      );
    });
  }, [devices, query, status]);

  return (
    <>
      <PageHeader
        title="Relojes"
        description="Administración de dispositivos ZKTeco conectados a la plataforma."
        actions={<AddDeviceButton onRetry={() => void load()} />}
        crumbs={[{ label: "Relojes" }]}
      />
      <div className="mb-5 flex flex-col gap-2.5 sm:flex-row">
        <SearchInput
          aria-label="Buscar relojes"
          placeholder="Buscar por serial, nombre o IP…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="sm:max-w-xs"
        />
        <Select
          aria-label="Filtrar por estado"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="sm:w-52"
        >
          {FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </Select>
      </div>
      {error ? (
        <ErrorState error={error} onRetry={() => void load()} />
      ) : loading ? (
        <LoadingState rows={6} />
      ) : devices.length === 0 ? (
        <NoDevicesEmpty onRetry={() => void load()} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="Sin resultados"
          description="Ningún reloj coincide con la búsqueda o el filtro aplicado."
        />
      ) : (
        <>
          <p aria-live="polite" className="mb-3 text-[13px] text-zinc-500 tabular-nums">
            {filtered.length} de {devices.length} relojes
          </p>
          <DataTable
            ariaLabel="Relojes"
            columns={COLUMNS}
            data={filtered}
            keyOf={(d) => d.id}
            renderCard={(d) => <DeviceCard device={d} />}
            empty={<EmptyState title="Sin resultados" description="Ajusta la búsqueda." />}
          />
        </>
      )}
    </>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { StatusDot } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import type { DeviceCommand } from "@/types";

const STATUSES = ["pending", "sent", "confirmed", "failed", "expired", "cancelled"];

const COLUMNS: Column<DeviceCommand>[] = [
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
  {
    key: "confirmed",
    header: "Confirmado",
    render: (c) => formatDateTime(c.confirmed_at),
  },
];

export default function Page() {
  const [commands, setCommands] = useState<DeviceCommand[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setCommands(await api.commands(status || undefined));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Comandos"
        description="Cola de comandos enviados a los relojes y su estado de confirmación."
        crumbs={[{ label: "Comandos" }]}
      />
      <div className="mb-5 sm:w-60">
        <Select
          aria-label="Filtrar por estado"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">Todos los estados</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </div>
      {error ? (
        <ErrorState error={error} onRetry={() => void load()} />
      ) : loading ? (
        <LoadingState rows={6} />
      ) : (
        <DataTable
          ariaLabel="Comandos"
          columns={COLUMNS}
          data={commands}
          keyOf={(c) => c.id}
          renderCard={(c) => (
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-sm font-medium">#{c.protocol_command_id}</p>
                <p className="mt-0.5 font-mono text-xs text-zinc-500">{c.command_type}</p>
                <p className="mt-0.5 text-xs text-zinc-500">{formatDateTime(c.queued_at)}</p>
              </div>
              <StatusDot status={c.status} />
            </div>
          )}
          empty={
            <EmptyState
              title="Sin comandos"
              description="No hay comandos con el estado seleccionado."
            />
          }
        />
      )}
    </>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import type { AuditEntry } from "@/types";

const COLUMNS: Column<AuditEntry>[] = [
  { key: "at", header: "Fecha", render: (a) => formatDateTime(a.created_at) },
  {
    key: "action",
    header: "Acción",
    render: (a) => <span className="font-mono text-[13px]">{a.action}</span>,
  },
  { key: "resource", header: "Recurso", render: (a) => a.resource_type ?? "—" },
  {
    key: "request",
    header: "Solicitud",
    render: (a) => <span className="font-mono text-xs text-zinc-500">{a.request_id ?? "—"}</span>,
  },
];

export default function Page() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await api.audit());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Auditoría"
        description="Registro de acciones realizadas en la plataforma. Solo lectura."
        crumbs={[{ label: "Auditoría" }]}
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void load()} />
      ) : loading ? (
        <LoadingState rows={8} />
      ) : (
        <DataTable
          ariaLabel="Registro de auditoría"
          columns={COLUMNS}
          data={entries}
          keyOf={(a, i) => `${a.created_at}-${a.request_id ?? i}-${a.action}`}
          renderCard={(a) => (
            <div>
              <p className="font-mono text-sm font-medium">{a.action}</p>
              <p className="mt-0.5 text-[13px] text-zinc-500">{formatDateTime(a.created_at)}</p>
              <p className="mt-0.5 text-xs text-zinc-500">{a.resource_type ?? "Sin recurso"}</p>
            </div>
          )}
          empty={
            <EmptyState title="Sin registros" description="Aún no hay actividad auditada." />
          }
        />
      )}
    </>
  );
}

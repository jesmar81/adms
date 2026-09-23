"use client";

import { Activity, AlarmClock, AlertTriangle, CheckCircle2, Clock3, UserRoundX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api";
import type { LivePunctualityReport, LivePunctualityRow } from "@/types";

function dateInTimezone(timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function displayTime(value: string, timezone: string): string {
  return new Intl.DateTimeFormat("es-MX", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function elapsedLabel(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} h ${remainder} min` : `${hours} h`;
}

function IncidentRow({ row, timezone }: { row: LivePunctualityRow; timezone: string }) {
  const missing = row.status === "not_arrived";
  const tone = missing ? (row.tolerance_remaining_minutes > 0 ? "sky" : "red") : "amber";
  const state = missing
    ? row.tolerance_remaining_minutes > 0
      ? `Sin llegada · tolerancia ${row.tolerance_remaining_minutes} min`
      : "Sin llegada · tolerancia agotada"
    : "Llegó tarde";

  return (
    <tr className="border-t border-line-subtle transition-colors hover:bg-surface-hover/50">
      <td className="whitespace-nowrap px-4 py-3 font-mono text-[12px] tabular-nums text-foreground">
        {displayTime(row.scheduled_entry_at, timezone)}
      </td>
      <td className="min-w-52 px-4 py-3">
        <p className="text-[13px] font-medium text-foreground">{row.worker_name}</p>
        <p className="mt-0.5 text-[11px] text-muted">{row.employee_number}{row.site_name ? ` · ${row.site_name}` : ""}</p>
      </td>
      <td className="px-4 py-3"><Badge tone={tone}>{state}</Badge></td>
      <td className="whitespace-nowrap px-4 py-3 font-mono text-[12px] tabular-nums text-foreground">
        {row.arrival_at ? displayTime(row.arrival_at, timezone) : "—"}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right">
        {missing ? (
          <span className={`font-mono text-[12px] tabular-nums ${row.late_minutes ? "text-rose-400" : "text-muted"}`}>
            {row.late_minutes ? `${row.late_minutes} min fuera de tolerancia` : `${elapsedLabel(row.minutes_after_start)} desde entrada`}
          </span>
        ) : (
          <span className="font-mono text-[12px] font-semibold tabular-nums text-amber-300">
            {row.late_minutes} min tarde
          </span>
        )}
      </td>
    </tr>
  );
}

function IncidentCard({ row, timezone }: { row: LivePunctualityRow; timezone: string }) {
  const missing = row.status === "not_arrived";
  const tone = missing ? (row.tolerance_remaining_minutes > 0 ? "sky" : "red") : "amber";
  const state = missing
    ? row.tolerance_remaining_minutes > 0
      ? `Sin llegada · ${row.tolerance_remaining_minutes} min de tolerancia`
      : "Sin llegada · tolerancia agotada"
    : "Llegó tarde";
  const delay = missing
    ? row.late_minutes
      ? `${row.late_minutes} min fuera de tolerancia`
      : `${elapsedLabel(row.minutes_after_start)} desde entrada`
    : `${row.late_minutes} min tarde`;

  return (
    <article className="rounded-lg border border-line-subtle bg-surface-raised/50 p-3.5">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-foreground">{row.worker_name}</p>
        <p className="mt-1 truncate text-xs text-muted">{row.employee_number}{row.site_name ? ` · ${row.site_name}` : ""}</p>
      </div>
      <div className="mt-2"><Badge tone={tone}>{state}</Badge></div>
      <dl className="mt-3 grid grid-cols-2 gap-3 border-t border-line-subtle pt-3 text-sm">
        <div><dt className="text-[11px] text-muted">Entrada programada</dt><dd className="mt-0.5 font-mono tabular-nums text-foreground">{displayTime(row.scheduled_entry_at, timezone)}</dd></div>
        <div><dt className="text-[11px] text-muted">Llegada</dt><dd className="mt-0.5 font-mono tabular-nums text-foreground">{row.arrival_at ? displayTime(row.arrival_at, timezone) : "—"}</dd></div>
        <div className="col-span-2"><dt className="text-[11px] text-muted">Demora</dt><dd className={`mt-0.5 font-mono tabular-nums ${missing ? "text-rose-400" : "text-amber-300"}`}>{delay}</dd></div>
      </dl>
    </article>
  );
}

export function LivePunctualityPanel({ companyId, timezone }: { companyId: string; timezone: string }) {
  const [report, setReport] = useState<LivePunctualityReport | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const hasLoaded = useRef(false);

  useEffect(() => {
    let active = true;
    let inFlight = false;
    hasLoaded.current = false;
    setReport(null);
    setError(null);
    setLoading(true);
    const refresh = async () => {
      if (!companyId) {
        setReport(null);
        setLoading(false);
        return;
      }
      if (document.visibilityState === "hidden" || inFlight) return;
      inFlight = true;
      if (!hasLoaded.current) setLoading(true);
      try {
        const value = await api.livePunctuality({
          company_id: companyId,
          report_date: dateInTimezone(timezone),
        });
        if (active) {
          setReport(value);
          setError(null);
          hasLoaded.current = true;
        }
      } catch (cause) {
        if (active) setError(cause);
      } finally {
        inFlight = false;
        if (active) {
          setLoading(false);
        }
      }
    };

    void refresh();
    const interval = window.setInterval(() => void refresh(), 15_000);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      active = false;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [companyId, timezone]);

  const refreshNow = async () => {
    try {
      const value = await api.livePunctuality({ company_id: companyId, report_date: dateInTimezone(timezone) });
      setReport(value);
      setError(null);
      hasLoaded.current = true;
    } catch (cause) {
      setError(cause);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingState rows={5} />;
  if (!companyId) return <EmptyState icon={<Activity className="h-5 w-5" />} title="Selecciona una empresa" description="Elige la empresa para ver quién ya debía entrar." />;

  const pendingRows = report?.rows.filter((row) => row.status === "not_arrived") ?? [];
  const metrics = report ? [
    { label: "Turnos con entrada cumplida", value: report.scheduled_count, detail: "Su hora de entrada ya pasó", icon: <AlarmClock className="h-4 w-4" />, tone: "text-sky-300" },
    { label: "Pendientes de entrada", value: report.pending_arrival_count, detail: `${report.pending_beyond_tolerance_count} fuera de tolerancia`, icon: <UserRoundX className="h-4 w-4" />, tone: "text-rose-300" },
    { label: "Llegadas tarde registradas", value: report.late_count, detail: "Ya checaron; no aparecen en la lista", icon: <AlertTriangle className="h-4 w-4" />, tone: "text-amber-300" },
    { label: "Retardo acumulado", value: `${report.late_minutes_total} min`, detail: "Minutos posteriores a tolerancia", icon: <Clock3 className="h-4 w-4" />, tone: "text-amber-300" },
  ] as const : [];
  const updatedAt = report
    ? new Intl.DateTimeFormat("es-MX", { timeZone: timezone, hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(report.generated_at))
    : null;

  return (
    <div className="space-y-4">
      {error ? <ErrorState error={error} onRetry={() => void refreshNow()} /> : null}
      {report ? <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => <Card key={metric.label} className="p-4 transition-colors hover:border-line-soft">
            <div className="flex items-start justify-between gap-3">
              <div><p className="text-[10px] font-semibold uppercase tracking-[0.11em] text-muted">{metric.label}</p><p className="mt-2 font-mono text-[26px] font-bold leading-none tabular-nums text-foreground">{metric.value}</p><p className="mt-2 text-[11px] text-muted">{metric.detail}</p></div>
              <span className={`rounded-md border border-line-subtle bg-surface-raised p-2 ${metric.tone}`}>{metric.icon}</span>
            </div>
          </Card>)}
        </div>

        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line-subtle px-4 py-3.5">
            <div className="flex min-w-0 items-center gap-2.5"><span className="relative flex h-2 w-2 shrink-0"><span className="absolute h-full w-full animate-ping rounded-full bg-emerald-400/60" /><span className="relative h-2 w-2 rounded-full bg-emerald-400" /></span><div className="min-w-0"><h2 className="text-[13px] font-semibold text-foreground">Trabajadores que aún no registran entrada</h2><p className="mt-0.5 text-[11px] text-muted">{report.report_date} · {pendingRows.length} pendiente(s) · última actualización {updatedAt ?? "—"} · automático cada 15 s</p></div></div>
          </div>
          {pendingRows.length ? <>
            <div className="hidden overflow-x-auto xl:block"><table className="w-full min-w-[760px] text-left">
              <thead className="bg-surface-raised text-[10px] font-semibold uppercase tracking-wide text-muted"><tr><th className="px-4 py-2.5">Entrada programada</th><th className="px-4 py-2.5">Trabajador</th><th className="px-4 py-2.5">Estado</th><th className="px-4 py-2.5">Llegada</th><th className="px-4 py-2.5 text-right">Demora</th></tr></thead>
              <tbody>{pendingRows.map((row) => <IncidentRow key={row.employment_id} row={row} timezone={timezone} />)}</tbody>
            </table></div>
            <div className="grid gap-2 p-3 xl:hidden">{pendingRows.map((row) => <IncidentCard key={row.employment_id} row={row} timezone={timezone} />)}</div>
          </> : <div className="px-5 py-10"><EmptyState icon={<CheckCircle2 className="h-5 w-5" />} title={report.scheduled_count ? "No hay entradas pendientes" : "Aún no se cumple una hora de entrada"} description={report.scheduled_count ? "Todos los turnos que ya iniciaron tienen entrada registrada. Los retardos ya registrados permanecen en el reporte histórico de puntualidad." : "La lista mostrará a cada trabajador cuando pase su hora de entrada programada."} /></div>}
          <div className="border-t border-line-subtle bg-surface-raised/40 px-4 py-2.5 text-[11px] text-muted">Se omiten descansos, feriados, faltas justificadas y turnos cuya hora aún no llega. Al registrar su entrada, cada persona sale de esta lista en la siguiente actualización automática.</div>
        </Card>
      </> : <div className="py-3"><EmptyState icon={<Activity className="h-5 w-5" />} title="No se pudo cargar el reporte" description="Actualiza para consultar las llegadas de hoy." /></div>}
    </div>
  );
}

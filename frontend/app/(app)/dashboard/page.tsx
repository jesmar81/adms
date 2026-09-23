"use client";

import {
  AlertTriangle, ArrowUpRight, CheckCircle2, CircleHelp, Clock3, ShieldCheck,
  Terminal, TimerReset, UserRoundCheck, UsersRound,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AttributionDonut } from "@/components/dashboard/AttributionDonut";
import { AttendanceTrend, type TrendPoint } from "@/components/dashboard/AttendanceTrend";
import { StatusDot } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ErrorState, LoadingState, StatSkeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatNumber, greeting } from "@/lib/format";
import type { AttendanceDashboard, AttendanceRow, Company, Device, DeviceCommand } from "@/types";

interface Summary { total: number; online: number; offline: number; pending_commands: number; failed_commands: number; }
const emptySummary: Summary = { total: 0, online: 0, offline: 0, pending_commands: 0, failed_commands: 0 };

function Help({ children }: { children: string }) {
  return <span title={children} aria-label={children} className="inline-flex cursor-help text-muted/70 transition-colors hover:text-accent"><CircleHelp className="h-3.5 w-3.5" aria-hidden /></span>;
}

function Metric({ label, value, detail, help, icon, tone, progress }: { label: string; value: string; detail: string; help: string; icon: ReactNode; tone: string; progress?: number }) {
  const accents: Record<string, string> = { sky: "bg-sky-500", emerald: "bg-emerald-500", amber: "bg-amber-500", violet: "bg-violet-500", rose: "bg-rose-500" };
  return <Card className="group relative overflow-hidden p-4 transition-all duration-150 hover:-translate-y-px hover:border-line-soft hover:shadow-glow"><div className={`pointer-events-none absolute right-0 top-0 h-20 w-20 rounded-full opacity-10 blur-2xl ${accents[tone]}`} /><div className="relative flex items-start justify-between gap-3"><div className="min-w-0"><div className="flex items-center gap-1.5"><p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">{label}</p><Help>{help}</Help></div><p className="mt-2 font-mono text-[27px] font-bold leading-none tracking-tight text-foreground">{value}</p><p className="mt-1.5 min-h-4 text-[11px] leading-4 text-muted">{detail}</p></div><span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-white/5 ${accents[tone]}/10`}>{icon}</span></div>{progress !== undefined && <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-surface-hover"><div className={`h-full rounded-full transition-[width] duration-500 ${accents[tone]}`} style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>}</Card>;
}

function lastSevenDays(rows: AttendanceRow[]): TrendPoint[] {
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, index) => {
    const value = new Date(today); value.setDate(today.getDate() - (6 - index));
    return { key: value.toLocaleDateString("en-CA"), label: new Intl.DateTimeFormat("es-MX", { weekday: "short" }).format(value).replace(".", ""), date: new Intl.DateTimeFormat("es-MX", { day: "numeric", month: "short" }).format(value), count: 0 };
  });
  for (const row of rows) { const day = days.find((item) => item.key === new Date(row.recorded_at).toLocaleDateString("en-CA")); if (day) day.count += 1; }
  return days.map(({ key: _key, ...day }) => day);
}

function minutesWithHours(minutes: number) { return `${formatNumber(minutes)} min (${(minutes / 60).toFixed(1)} h)`; }
function localToday() { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10); }

export default function DashboardPage() {
  const { user, can } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [reportDate, setReportDate] = useState(localToday);
  const [kpis, setKpis] = useState<AttendanceDashboard | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [recent, setRecent] = useState<AttendanceRow[]>([]);
  const [pending, setPending] = useState<DeviceCommand[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [stats, deviceRows, attendanceRows, commandRows, companyRows] = await Promise.all([
        can("devices.read") ? api.summary() : Promise.resolve(emptySummary),
        can("devices.read") ? api.devices() : Promise.resolve([] as Device[]),
        can("attendance.read") ? api.attendance({ limit: "100" }) : Promise.resolve([] as AttendanceRow[]),
        can("commands.read") ? api.commands("pending") : Promise.resolve([] as DeviceCommand[]),
        can("companies.read") ? api.companies() : Promise.resolve([] as Company[]),
      ]);
      const activeCompanies = companyRows.filter((company) => company.active);
      const selectedCompanyId = companyId || activeCompanies[0]?.id || "";
      setSummary({ ...emptySummary, ...stats }); setDevices(deviceRows.slice(0, 5)); setRecent(attendanceRows); setPending(commandRows.slice(0, 6)); setCompanies(activeCompanies);
      if (selectedCompanyId !== companyId) setCompanyId(selectedCompanyId);
      setKpis(selectedCompanyId && can("attendance.read") ? await api.attendanceDashboard({ company_id: selectedCompanyId, report_date: reportDate }) : null);
    } catch (reason) { setError(reason); } finally { setLoading(false); }
  }, [can, companyId, reportDate]);
  useEffect(() => { void load(); }, [load]);

  const trend = useMemo(() => lastSevenDays(recent), [recent]);
  const attributed = useMemo(() => recent.filter((row) => row.attribution_status === "assigned").length, [recent]);
  const ambiguous = useMemo(() => recent.filter((row) => row.attribution_status === "ambiguous").length, [recent]);
  const unassigned = recent.length - attributed - ambiguous;
  const attendanceRate = kpis?.scheduled_workers ? (kpis.present_workers / kpis.scheduled_workers) * 100 : 0;
  const punctualityRate = kpis?.present_workers ? (kpis.on_time_workers / kpis.present_workers) * 100 : 0;
  const overtimePending = (kpis?.overtime_pending_hr ?? 0) + (kpis?.overtime_pending_direction ?? 0);
  const fleet = summary ?? emptySummary;

  return <>
    <section className="mb-7 flex flex-col justify-between gap-5 border-b border-line-subtle pb-6 lg:flex-row lg:items-end"><div><div className="mb-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300"><span className="relative flex h-1.5 w-1.5"><span className="absolute h-full w-full animate-pulse-dot rounded-full bg-emerald-400" /><span className="relative h-1.5 w-1.5 rounded-full bg-emerald-400" /></span>Centro de control operativo</div><h1 className="text-2xl font-semibold tracking-tight text-foreground md:text-[30px]">{greeting()}{user ? `, ${user.username}` : ""}</h1><p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">Indicadores calculados contra horarios, feriados, ajustes y solicitudes reales; no son datos simulados.</p></div>{companies.length > 0 && <div className="grid w-full grid-cols-1 gap-2 rounded-lg border border-line-subtle bg-surface-raised p-2 sm:w-auto sm:grid-cols-2"><label className="grid min-w-0 gap-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-muted">Empresa<select value={companyId} onChange={(event) => setCompanyId(event.target.value)} className="h-11 w-full min-w-0 rounded-md border border-line-soft bg-surface px-2 text-xs font-medium text-foreground outline-none transition focus:border-accent sm:h-8 sm:min-w-44">{companies.map((company) => <option key={company.id} value={company.id}>{company.trade_name || company.legal_name}</option>)}</select></label><label className="grid min-w-0 gap-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-muted">Día operativo<input type="date" value={reportDate} onChange={(event) => setReportDate(event.target.value)} className="h-11 w-full min-w-0 rounded-md border border-line-soft bg-surface px-2 text-xs text-foreground outline-none transition focus:border-accent sm:h-8" /></label></div>}</section>
    {error ? <ErrorState error={error} onRetry={() => void load()} /> : loading || !summary ? <StatSkeleton /> : kpis ? <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="Cobertura de turno" value={`${formatNumber(kpis.present_workers)} / ${formatNumber(kpis.scheduled_workers)}`} detail={`${formatNumber(kpis.absent_workers)} ausencias; ${formatNumber(kpis.justified_absences)} justificadas`} help="Personas con primera checada frente a quienes tenían turno laboral programado. Descansos y feriados no entran al denominador." icon={<UsersRound className="h-4 w-4 text-sky-300" aria-hidden />} tone="sky" progress={attendanceRate} /><Metric label="Puntualidad" value={`${punctualityRate.toFixed(1)}%`} detail={`${formatNumber(kpis.on_time_workers)} entradas a tiempo de ${formatNumber(kpis.present_workers)}`} help="Porcentaje de presentes cuya primera entrada quedó dentro de la tolerancia configurada en su horario." icon={<UserRoundCheck className="h-4 w-4 text-emerald-300" aria-hidden />} tone="emerald" progress={punctualityRate} /><Metric label="Excepciones" value={formatNumber(kpis.late_workers + kpis.absent_workers)} detail={`${formatNumber(kpis.late_workers)} retardos · ${minutesWithHours(kpis.late_minutes)}`} help="Suma de ausencias y retardos. Los minutos descuentan la tolerancia definida en el horario." icon={<AlertTriangle className="h-4 w-4 text-amber-300" aria-hidden />} tone="amber" /><Metric label="Tiempo extra" value={formatNumber(overtimePending)} detail={`${formatNumber(kpis.overtime_pending_hr)} RR. HH. · ${formatNumber(kpis.overtime_pending_direction)} Dirección`} help="Solicitudes pendientes. Una checada posterior al turno es evidencia, no tiempo pagable, hasta concluir las dos autorizaciones." icon={<TimerReset className="h-4 w-4 text-violet-300" aria-hidden />} tone="violet" /><Metric label="Marcas conciliadas" value={formatNumber(kpis.raw_marks)} detail={kpis.unresolved_marks ? `${formatNumber(kpis.unresolved_marks)} requieren conciliación` : "Sin marcas pendientes de atribución"} help="Checadas recibidas desde terminales de la empresa. Las ambiguas o sin empleo asignado se separan del cálculo de asistencia." icon={<ShieldCheck className="h-4 w-4 text-rose-300" aria-hidden />} tone="rose" progress={kpis.raw_marks ? ((kpis.raw_marks - kpis.unresolved_marks) / kpis.raw_marks) * 100 : 100} /></div> : <Card className="border-dashed p-5 text-sm text-muted">No hay una empresa disponible en tu alcance para calcular los indicadores de asistencia.</Card>}
    {!error && <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-12"><Card className="p-5 md:p-6 xl:col-span-7"><div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-1.5"><h2 className="text-[15px] font-semibold text-foreground">Flujo de checadas</h2><Help>Volumen recibido por el servidor durante los últimos siete días. Es telemetría, no un cálculo de puntualidad.</Help></div><p className="mt-1 text-xs text-muted">Pasa el cursor sobre un punto para consultar el volumen diario.</p></div><Link href="/attendance" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover">Ver marcaciones <ArrowUpRight className="h-3.5 w-3.5" aria-hidden /></Link></div>{loading ? <LoadingState rows={3} /> : <AttendanceTrend data={trend} />}</Card><Card className="p-5 md:p-6 xl:col-span-5"><div className="mb-5"><div className="flex items-center gap-1.5"><h2 className="text-[15px] font-semibold text-foreground">Integridad de atribución</h2><Help>Verifica que las checadas puedan asociarse a un empleo antes de usarse en asistencia o nómina.</Help></div><p className="mt-1 text-xs text-muted">Muestra de las últimas 100 marcaciones visibles.</p></div>{loading ? <LoadingState rows={3} /> : <AttributionDonut data={[{ label: "Asignadas", value: attributed, color: "#34d399" }, { label: "Ambiguas", value: ambiguous, color: "#fbbf24" }, { label: "Sin asignar", value: unassigned, color: "#fb7185" }]} />}{unassigned + ambiguous > 0 && <Link href="/attendance" className="mt-4 flex items-center justify-between rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-3 py-2 text-xs text-amber-200 transition-colors hover:bg-amber-500/[0.12]"><span>Hay checadas que requieren conciliación</span><ArrowUpRight className="h-3.5 w-3.5" aria-hidden /></Link>}</Card><Card className="p-5 md:p-6 xl:col-span-7"><div className="mb-4 flex items-start justify-between gap-3"><div><div className="flex items-center gap-1.5"><h2 className="text-[15px] font-semibold text-foreground">Salud de terminales</h2><Help>Último estado calculado desde la comunicación ADMS; es independiente de los KPI de asistencia.</Help></div><p className="mt-1 text-xs text-muted"><span className="font-mono text-foreground">{formatNumber(fleet.online)} / {formatNumber(fleet.total)}</span> terminales con comunicación reciente · {formatNumber(fleet.offline)} por revisar.</p></div><Link href="/devices" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover">Ver terminales <ArrowUpRight className="h-3.5 w-3.5" aria-hidden /></Link></div>{loading ? <LoadingState rows={4} /> : devices.length ? <ul className="divide-y divide-line-subtle">{devices.map((device) => <li key={device.id}><Link href={`/devices/${device.id}`} className="group flex items-center justify-between gap-3 rounded-lg px-2 py-3 transition-colors hover:bg-surface-hover"><span className="min-w-0"><span className="block truncate text-sm font-medium text-foreground">{device.name ?? device.serial_number}</span><span className="mt-1 block truncate font-mono text-[11px] text-muted">{device.serial_number} · {device.ip_address ?? "sin IP registrada"}</span></span><StatusDot status={device.derived_status ?? device.status} /></Link></li>)}</ul> : <div className="rounded-lg border border-dashed border-line-soft px-4 py-8 text-center text-sm text-muted">No hay relojes registrados todavía.</div>}</Card><Card className="p-5 md:p-6 xl:col-span-5"><div className="mb-4 flex items-start justify-between gap-3"><div><div className="flex items-center gap-1.5"><h2 className="text-[15px] font-semibold text-foreground">Actividad reciente</h2><Help>Las últimas marcaciones recibidas; el PIN es el identificador transmitido por el reloj.</Help></div><p className="mt-1 text-xs text-muted">Datos del servidor, no simulados.</p></div><Link href="/attendance" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover">Abrir lista <ArrowUpRight className="h-3.5 w-3.5" aria-hidden /></Link></div>{loading ? <LoadingState rows={4} /> : recent.length ? <ul className="space-y-1">{recent.slice(0, 5).map((row) => <li key={row.id} className="flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-surface-hover"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-300"><Clock3 className="h-4 w-4" aria-hidden /></span><span className="min-w-0 flex-1"><span className="block truncate font-mono text-xs font-medium text-foreground">PIN {row.device_user_pin}</span><span className="mt-0.5 block truncate text-[11px] text-muted">{formatDateTime(row.recorded_at)}</span></span><span className={row.attribution_status === "assigned" ? "text-emerald-400" : row.attribution_status === "ambiguous" ? "text-amber-400" : "text-rose-400"} title={`Atribución: ${row.attribution_status}`}><CheckCircle2 className="h-4 w-4" aria-hidden /></span></li>)}</ul> : <div className="rounded-lg border border-dashed border-line-soft px-4 py-8 text-center text-sm text-muted">Aún no hay marcaciones recibidas.</div>}</Card><Card className="p-5 md:p-6 xl:col-span-12"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-1.5"><h2 className="text-[15px] font-semibold text-foreground">Operaciones de dispositivos</h2><Help>Comandos que aún no han sido confirmados por una terminal. Revísalos antes de volver a enviarlos.</Help></div><p className="mt-1 text-xs text-muted">Cola limitada a los seis elementos más próximos.</p></div><Link href="/commands" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover">Gestionar cola <ArrowUpRight className="h-3.5 w-3.5" aria-hidden /></Link></div>{loading ? <div className="mt-4"><LoadingState rows={2} /></div> : pending.length ? <ul className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">{pending.map((command) => <li key={command.id} className="flex items-center gap-3 rounded-lg border border-line-subtle bg-surface-raised/60 px-3 py-3"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-300"><Terminal className="h-4 w-4" aria-hidden /></span><span className="min-w-0"><span className="block truncate font-mono text-xs text-foreground">#{command.protocol_command_id} · {command.command_type}</span><span className="mt-0.5 block text-[11px] text-amber-300">Pendiente de terminal</span></span></li>)}</ul> : <div className="mt-4 flex items-center gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.07] px-4 py-3 text-sm text-emerald-200"><CheckCircle2 className="h-4 w-4" aria-hidden />No hay comandos esperando confirmación.</div>}</Card></div>}
  </>;
}

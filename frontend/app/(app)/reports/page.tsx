"use client";

import { Activity, CalendarDays, Clock3, Download, FileBarChart, LogIn, Pencil, Save, TimerReset, UserX } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api";
import { OvertimePanel } from "@/components/reports/OvertimePanel";
import { LivePunctualityPanel } from "@/components/reports/LivePunctualityPanel";
import type { AbsenceReport, AttendanceAdjustment, Company, CorporateGroup, DailyArrivalReport, Employment, Person, PunctualityReport, WeeklyCardReport } from "@/types";

type ReportKind = "live" | "arrivals" | "absences" | "card" | "punctuality" | "overtime";
type AdjustmentDraft = { attendance_date: string; entry_at: string; meal_out_at: string; meal_in_at: string; exit_at: string; absence_kind: string; reason: string };

function isoDate(value: Date): string { return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 10); }
function mondayFor(value: string): string { const date = new Date(`${value}T12:00:00`); date.setDate(date.getDate() - ((date.getDay() + 6) % 7)); return isoDate(date); }
function time(value: string | null): string { return value ? new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "—"; }
function minutes(value: number): string { return `${value} min (${Math.floor(value / 60)} h ${value % 60} min)`; }
function localInput(value: string | null): string { return value ? new Date(value).toISOString().slice(0, 16) : ""; }
function toIso(value: string): string | null { return value ? new Date(value).toISOString() : null; }

const REPORTS: { id: ReportKind; label: string; description: string; icon: typeof CalendarDays }[] = [
  { id: "live", label: "Pendientes de entrada en vivo", description: "Muestra quién ya debía entrar y aún no registra checada; desaparece al llegar.", icon: Activity },
  { id: "arrivals", label: "Llegadas del día", description: "Primera checada y total de marcas por trabajador.", icon: LogIn },
  { id: "absences", label: "Faltas", description: "Sólo días laborales; descansos y feriados se excluyen.", icon: UserX },
  { id: "card", label: "Tarjeta semanal", description: "Lunes a domingo, con comida, incidencias y ajustes RR. HH.", icon: CalendarDays },
  { id: "punctuality", label: "Puntualidad histórica", description: "Consulta retardos y salidas fuera de horario por periodo.", icon: Clock3 },
  { id: "overtime", label: "Tiempo extra", description: "Detección, revisión de RR. HH. y autorización de Dirección.", icon: TimerReset },
];

export default function ReportsPage() {
  const searchParams = useSearchParams();
  const today = useMemo(() => isoDate(new Date()), []);
  const [kind, setKind] = useState<ReportKind>("live");
  const [groups, setGroups] = useState<CorporateGroup[]>([]); const [companies, setCompanies] = useState<Company[]>([]); const [employments, setEmployments] = useState<Employment[]>([]); const [people, setPeople] = useState<Person[]>([]);
  const [groupId, setGroupId] = useState(""); const [companyId, setCompanyId] = useState(""); const [employmentId, setEmploymentId] = useState("");
  const [reportDate, setReportDate] = useState(today); const [dateFrom, setDateFrom] = useState(mondayFor(today)); const [dateTo, setDateTo] = useState(today); const [mode, setMode] = useState("both");
  const [arrivals, setArrivals] = useState<DailyArrivalReport[]>([]); const [absences, setAbsences] = useState<AbsenceReport[]>([]); const [punctuality, setPunctuality] = useState<PunctualityReport[]>([]); const [card, setCard] = useState<WeeklyCardReport | null>(null);
  const [loading, setLoading] = useState(true); const [running, setRunning] = useState(false); const [error, setError] = useState<unknown>(null); const [editing, setEditing] = useState<AdjustmentDraft | null>(null);
  const visibleCompanies = companies.filter((company) => company.corporate_group_id === groupId);
  const workerRows = employments.filter((employment) => employment.company_id === companyId && employment.active);
  const visibleReports = REPORTS;
  const workerName = (employment: Employment) => {
    const person = people.find((item) => item.id === employment.person_id);
    return person ? `${person.first_name} ${person.last_name} ${person.second_last_name ?? ""}`.trim() : "Trabajador";
  };

  const loadCatalogs = useCallback(async () => {
    try {
      const [groupRows, companyRows, employmentRows] = await Promise.all([api.corporateGroups(), api.companies(), api.employments()]);
      setGroups(groupRows); setCompanies(companyRows); setEmployments(employmentRows); setGroupId((old) => old || groupRows[0]?.id || "");
    } catch (cause) { setError(cause); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void loadCatalogs(); }, [loadCatalogs]);
  useEffect(() => {
    if (searchParams.get("view") === "overtime") setKind("overtime");
  }, [searchParams]);
  useEffect(() => { if (!groupId) { setPeople([]); return; } void api.people(groupId).then(setPeople).catch(setError); }, [groupId]);
  useEffect(() => { if (!visibleCompanies.some((company) => company.id === companyId)) setCompanyId(visibleCompanies[0]?.id || ""); }, [companyId, visibleCompanies]);
  useEffect(() => { if (!workerRows.some((employment) => employment.id === employmentId)) setEmploymentId(workerRows[0]?.id || ""); }, [employmentId, workerRows]);

  async function runReport() {
    if ((kind === "card" && !employmentId) || (kind !== "card" && !companyId)) return;
    setRunning(true); setError(null);
    try {
      if (kind === "arrivals") setArrivals(await api.dailyArrivals({ company_id: companyId, report_date: reportDate }));
      if (kind === "absences") setAbsences(await api.absencesReport({ company_id: companyId, report_date: reportDate }));
      if (kind === "card") setCard(await api.weeklyCard({ employment_id: employmentId, week_start: mondayFor(reportDate) }));
      if (kind === "punctuality") setPunctuality(await api.punctualityReport({ company_id: companyId, date_from: dateFrom, date_to: dateTo, mode }));
    } catch (cause) { setError(cause); } finally { setRunning(false); }
  }
  async function downloadPdf(scope: "worker" | "company" | "group") {
    const params = { week_start: mondayFor(reportDate), ...(scope === "worker" ? { employment_id: employmentId } : scope === "company" ? { company_id: companyId } : { corporate_group_id: groupId }) };
    try { const blob = await api.weeklyCardsPdf(params); const href = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = href; link.download = `tarjetas_${params.week_start}.pdf`; link.click(); URL.revokeObjectURL(href); } catch (cause) { setError(cause); }
  }
  function openAdjustment(day: WeeklyCardReport["days"][number]) {
    setEditing({ attendance_date: day.report_date, entry_at: localInput(day.entry_at), meal_out_at: localInput(day.meal_out_at), meal_in_at: localInput(day.meal_in_at), exit_at: localInput(day.exit_at), absence_kind: day.day_kind === "FALTA JUSTIFICADA" ? "justified" : day.day_kind === "FALTA INJUSTIFICADA" ? "unjustified" : "", reason: day.adjustment_reason || "" });
  }
  async function saveAdjustment() {
    if (!editing || !card) return;
    try { await api.saveAttendanceAdjustment(card.employment_id, { attendance_date: editing.attendance_date, entry_at: toIso(editing.entry_at), meal_out_at: toIso(editing.meal_out_at), meal_in_at: toIso(editing.meal_in_at), exit_at: toIso(editing.exit_at), absence_kind: editing.absence_kind || null, reason: editing.reason }); setEditing(null); await runReport(); } catch (cause) { setError(cause); }
  }
  const updateDraft = (field: keyof AdjustmentDraft, value: string) => setEditing((current) => current ? { ...current, [field]: value } : current);

  function controls() {
    return <Card className="p-5">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Field label="Grupo corporativo">{(id) => <Select id={id} value={groupId} onChange={(event) => setGroupId(event.target.value)}>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field>
        <Field label="Empresa">{(id) => <Select id={id} value={companyId} onChange={(event) => setCompanyId(event.target.value)}><option value="">Selecciona</option>{visibleCompanies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field>
        {kind === "card" ? <Field label="Trabajador">{(id) => <Select id={id} value={employmentId} onChange={(event) => setEmploymentId(event.target.value)}><option value="">Selecciona</option>{workerRows.map((employment) => <option key={employment.id} value={employment.id}>{employment.employee_number} · {workerName(employment)}</option>)}</Select>}</Field> : null}
        {kind === "punctuality" ? <>
          <Field label="Desde">{(id) => <Input id={id} type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />}</Field>
          <Field label="Hasta">{(id) => <Input id={id} type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />}</Field>
          <Field label="Mostrar">{(id) => <Select id={id} value={mode} onChange={(event) => setMode(event.target.value)}><option value="both">Ambos</option><option value="late">Sólo llegadas tarde</option><option value="early">Sólo salidas temprano</option></Select>}</Field>
        </> : null}
        {kind !== "punctuality" && kind !== "card" && kind !== "live" ? <Field label="Fecha">{(id) => <Input id={id} type="date" value={reportDate} onChange={(event) => setReportDate(event.target.value)} />}</Field> : null}
        {kind === "card" ? <Field label="Cualquier día de la semana">{(id) => <Input id={id} type="date" value={reportDate} onChange={(event) => setReportDate(event.target.value)} />}</Field> : null}
      </div>
      {kind !== "live" ? <div className="mt-4 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={() => void downloadPdf("group")} disabled={!groupId}>PDF grupo</Button>
        <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={() => void downloadPdf("company")} disabled={!companyId}>PDF empresa</Button>
        {kind === "card" && <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={() => void downloadPdf("worker")} disabled={!employmentId}>PDF trabajador</Button>}
        <Button variant="primary" icon={<FileBarChart className="h-4 w-4" />} onClick={() => void runReport()} loading={running} disabled={kind === "card" ? !employmentId : !companyId}>Generar reporte</Button>
      </div> : <p className="mt-3 text-[11px] text-muted">Se consulta automáticamente la fecha actual de la empresa seleccionada.</p>}
    </Card>;
  }
 function cardResult() {
   if (!card) return <EmptyState icon={<CalendarDays className="h-5 w-5" />} title="Elige un trabajador" description="La tarjeta se calcula de lunes a domingo." />;
   return <Card className="overflow-hidden">
     <div className="border-b border-line-subtle p-4 sm:p-5"><p className="font-semibold">{card.worker_name}</p><p className="text-sm text-muted">{card.company_name}{card.site_name ? ` · ${card.site_name}` : ""} · {card.week_start} a {card.week_end}</p></div>
     <div className="hidden overflow-x-auto xl:block"><table className="w-full min-w-[960px] text-left text-sm"><thead className="bg-surface-raised text-xs uppercase text-muted"><tr><th className="p-3">Día</th><th className="p-3">Clasificación</th><th className="p-3">Entrada</th><th className="p-3">Salida comida</th><th className="p-3">Regreso comida</th><th className="p-3">Salida</th><th className="p-3">Tiempo extra detectado</th><th className="p-3" /></tr></thead><tbody>{card.days.map((day) => <tr key={day.report_date} className="border-t border-line-subtle"><td className="p-3">{day.report_date}</td><td className="p-3 font-medium">{day.day_kind}{day.late_minutes ? <p className="text-xs font-normal text-amber-700">Retardo: {minutes(day.late_minutes)}</p> : null}{day.early_departure_minutes ? <p className="text-xs font-normal text-amber-700">Salida: {minutes(day.early_departure_minutes)}</p> : null}</td><td className="p-3">{time(day.entry_at)}</td><td className="p-3">{time(day.meal_out_at)}</td><td className="p-3">{time(day.meal_in_at)}</td><td className="p-3">{time(day.exit_at)}</td><td className="p-3 font-mono text-emerald-400">{day.overtime_minutes ? minutes(day.overtime_minutes) : "—"}</td><td className="p-3"><Button variant="ghost" icon={<Pencil className="h-4 w-4" />} onClick={() => openAdjustment(day)} aria-label={`Ajustar ${day.report_date}`} /></td></tr>)}</tbody></table></div>
     <div className="divide-y divide-line-subtle xl:hidden">{card.days.map((day) => <article key={day.report_date} className="p-4">
       <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-foreground">{day.report_date}</p><p className="mt-1 text-xs font-medium text-muted">{day.day_kind}</p>{day.late_minutes ? <p className="mt-1 text-xs text-amber-700">Retardo: {minutes(day.late_minutes)}</p> : null}{day.early_departure_minutes ? <p className="mt-1 text-xs text-amber-700">Salida fuera de horario: {minutes(day.early_departure_minutes)}</p> : null}</div><Button size="sm" variant="secondary" icon={<Pencil className="h-4 w-4" />} onClick={() => openAdjustment(day)} aria-label={`Ajustar ${day.report_date}`}>Ajustar</Button></div>
       <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">{[["Entrada", day.entry_at], ["Salida a comer", day.meal_out_at], ["Regreso de comida", day.meal_in_at], ["Salida", day.exit_at]].map(([label, value]) => <div key={label}><dt className="text-[11px] text-muted">{label}</dt><dd className="mt-0.5 font-mono tabular-nums text-foreground">{time(value)}</dd></div>)}<div className="col-span-2"><dt className="text-[11px] text-muted">Tiempo extra detectado</dt><dd className="mt-0.5 font-mono tabular-nums text-emerald-400">{day.overtime_minutes ? minutes(day.overtime_minutes) : "—"}</dd></div></dl>
     </article>)}</div>
   </Card>;
 }
  function result() { if (running) return <LoadingState rows={6} />; if (kind === "card") return cardResult(); if (kind === "arrivals") return arrivals.length ? <Rows columns={["Trabajador", "No. empleado", "Primera llegada", "Marcas"]} rows={arrivals.map((row) => [row.worker_name, row.employee_number, time(row.first_mark_at), String(row.mark_count)])} /> : <EmptyState icon={<LogIn className="h-5 w-5" />} title="Sin llegadas" description="No hay checadas vinculadas." />; if (kind === "absences") return absences.length ? <Rows columns={["Trabajador", "No. empleado", "Entrada esperada"]} rows={absences.map((row) => [row.worker_name, row.employee_number, time(row.expected_entry_at)])} /> : <EmptyState icon={<UserX className="h-5 w-5" />} title="Sin faltas" description="No hay ausencias para los turnos exigibles." />; return punctuality.length ? <Rows columns={["Trabajador", "Fecha", "Retardo", "Salida fuera de horario"]} rows={punctuality.map((row) => [row.worker_name, row.report_date, row.late_minutes ? minutes(row.late_minutes) : "—", row.early_departure_minutes ? minutes(row.early_departure_minutes) : "—"])} /> : <EmptyState icon={<Clock3 className="h-5 w-5" />} title="Sin incidencias" description="No hay retardos ni salidas tempranas." />; }
  if (loading) return <LoadingState rows={6} />;
  return <><PageHeader title="Reportes" description="Asistencia, puntualidad en vivo, tarjetas semanales, tiempo extra y ajustes auditables de RR. HH." crumbs={[{ label: "Reportes" }]} />{error ? <div className="mb-5"><ErrorState error={error} onRetry={() => void runReport()} /></div> : null}<div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{visibleReports.map((report) => { const Icon = report.icon; return <button key={report.id} aria-pressed={kind === report.id} onClick={() => setKind(report.id)} className={`rounded-[10px] border p-3.5 text-left transition-colors ${kind === report.id ? "border-accent/50 bg-accent-soft shadow-glow" : "border-line-subtle bg-surface-card hover:bg-surface-hover"}`}><Icon className="h-4 w-4 text-accent" /><p className="mt-2.5 text-[13px] font-semibold text-foreground">{report.label}</p><p className="mt-1 text-[12px] leading-relaxed text-muted">{report.description}</p></button>; })}</div>{kind === "overtime" ? <OvertimePanel /> : <>{controls()}{kind === "live" ? <div className="mt-5"><LivePunctualityPanel companyId={companyId} timezone={companies.find((company) => company.id === companyId)?.timezone || "America/Mexico_City"} /></div> : <><div className="mt-5">{result()}</div>{editing ? <AdjustmentForm draft={editing} update={updateDraft} onCancel={() => setEditing(null)} onSave={() => void saveAdjustment()} /> : null}</>}</>}</>;
}

function Rows({ columns, rows }: { columns: string[]; rows: string[][] }) {
  return <Card className="overflow-hidden">
    <div className="hidden overflow-x-auto xl:block"><table className="w-full text-left text-sm"><thead className="bg-surface-raised text-xs uppercase text-muted"><tr>{columns.map((column) => <th key={column} className="p-3">{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[0]}-${index}`} className="border-t border-line-subtle">{row.map((cell, cellIndex) => <td key={cellIndex} className="p-3">{cell}</td>)}</tr>)}</tbody></table></div>
    <div className="divide-y divide-line-subtle xl:hidden">{rows.map((row, index) => <article key={`${row[0]}-${index}`} className="p-4"><h3 className="font-medium text-foreground">{row[0]}</h3><dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">{columns.slice(1).map((column, cellIndex) => <div key={column}><dt className="text-[11px] text-muted">{column}</dt><dd className="mt-0.5 break-words text-sm text-foreground">{row[cellIndex + 1]}</dd></div>)}</dl></article>)}</div>
  </Card>;
}
function AdjustmentForm({ draft, update, onCancel, onSave }: { draft: AdjustmentDraft; update: (field: keyof AdjustmentDraft, value: string) => void; onCancel: () => void; onSave: () => void }) {
  const absence = Boolean(draft.absence_kind);
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-2 sm:items-center sm:p-4">
    <section role="dialog" aria-modal="true" aria-labelledby="attendance-adjustment-title" className="flex max-h-[calc(100dvh-1rem)] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-line-soft bg-surface-card shadow-pop sm:max-h-[calc(100dvh-2rem)]">
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-line-subtle p-4 sm:p-6"><div><h2 id="attendance-adjustment-title" className="text-lg font-semibold text-foreground">Ajuste de asistencia RR. HH.</h2><p className="text-sm text-muted">Las checadas originales del reloj no se modifican.</p></div><Button variant="ghost" onClick={onCancel}>Cerrar</Button></header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 sm:p-6"><div className="grid gap-3 md:grid-cols-2"><Field label="Clasificación de falta">{(id) => <Select id={id} value={draft.absence_kind} onChange={(event) => update("absence_kind", event.target.value)}><option value="">No es falta: corregir horas</option><option value="justified">Falta justificada</option><option value="unjustified">Falta injustificada</option></Select>}</Field><Field label="Motivo obligatorio">{(id) => <Input id={id} value={draft.reason} onChange={(event) => update("reason", event.target.value)} placeholder="Ej. Olvidó registrar salida; autorización de gerente" />}</Field>{([ ["entry_at", "Entrada"], ["meal_out_at", "Salida a comer"], ["meal_in_at", "Regreso de comida"], ["exit_at", "Salida final"] ] as [keyof AdjustmentDraft, string][]).map(([field, label]) => <Field key={field} label={label}>{(id) => <Input id={id} type="datetime-local" disabled={absence} value={draft[field]} onChange={(event) => update(field, event.target.value)} />}</Field>)}</div></div>
      <footer className="flex shrink-0 flex-col-reverse gap-2 border-t border-line-subtle p-4 sm:flex-row sm:justify-end sm:p-6"><Button variant="secondary" onClick={onCancel}>Cancelar</Button><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={onSave} disabled={draft.reason.trim().length < 5}>Guardar ajuste</Button></footer>
    </section>
  </div>;
}

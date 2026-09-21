"use client";

import { CalendarDays, Clock3, FileBarChart, LogIn, UserX } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api";
import type { AbsenceReport, Company, CorporateGroup, DailyArrivalReport, Person, PunctualityReport, WeeklyCardReport } from "@/types";

type ReportKind = "arrivals" | "absences" | "card" | "punctuality";

function isoDate(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

function mondayFor(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return isoDate(date);
}

function time(value: string | null): string {
  return value ? new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "—";
}

function minutes(value: number): string {
  const hours = Math.floor(value / 60);
  return `${value} min (${hours} h ${value % 60} min)`;
}

const REPORTS: { id: ReportKind; label: string; description: string; icon: ReactNode }[] = [
  { id: "arrivals", label: "Llegadas del día", description: "Primera checada y total de marcas por trabajador.", icon: <LogIn className="h-5 w-5" /> },
  { id: "absences", label: "Faltas", description: "Sólo días laborables; excluye descansos y feriados.", icon: <UserX className="h-5 w-5" /> },
  { id: "card", label: "Tarjeta semanal", description: "Una persona, semana completa de lunes a domingo.", icon: <CalendarDays className="h-5 w-5" /> },
  { id: "punctuality", label: "Puntualidad", description: "Llegadas tarde y/o salidas temprano contra el horario.", icon: <Clock3 className="h-5 w-5" /> },
];

export default function ReportsPage() {
  const today = useMemo(() => isoDate(new Date()), []);
  const [kind, setKind] = useState<ReportKind>("arrivals");
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [groupId, setGroupId] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [personId, setPersonId] = useState("");
  const [reportDate, setReportDate] = useState(today);
  const [dateFrom, setDateFrom] = useState(mondayFor(today));
  const [dateTo, setDateTo] = useState(today);
  const [mode, setMode] = useState("both");
  const [arrivals, setArrivals] = useState<DailyArrivalReport[]>([]);
  const [absences, setAbsences] = useState<AbsenceReport[]>([]);
  const [card, setCard] = useState<WeeklyCardReport | null>(null);
  const [punctuality, setPunctuality] = useState<PunctualityReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const loadCatalogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedGroups, loadedCompanies] = await Promise.all([api.corporateGroups(), api.companies()]);
      setGroups(loadedGroups);
      setCompanies(loadedCompanies);
      const selected = groupId || loadedGroups[0]?.id || "";
      setGroupId(selected);
      setCompanyId((current) => loadedCompanies.some((company) => company.id === current) ? current : loadedCompanies.find((company) => company.corporate_group_id === selected)?.id ?? "");
    } catch (cause) {
      setError(cause);
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useEffect(() => { void loadCatalogs(); }, [loadCatalogs]);
  useEffect(() => {
    if (!groupId) { setPeople([]); return; }
    void api.people(groupId).then((rows) => {
      setPeople(rows);
      setPersonId((current) => rows.some((person) => person.id === current) ? current : rows[0]?.id ?? "");
    }).catch(setError);
  }, [groupId]);

  const visibleCompanies = companies.filter((company) => company.corporate_group_id === groupId);

  async function runReport() {
    if ((kind === "card" && !personId) || (kind !== "card" && !companyId)) return;
    setRunning(true);
    setError(null);
    try {
      if (kind === "arrivals") setArrivals(await api.dailyArrivals({ company_id: companyId, report_date: reportDate }));
      if (kind === "absences") setAbsences(await api.absencesReport({ company_id: companyId, report_date: reportDate }));
      if (kind === "card") setCard(await api.weeklyCard({ person_id: personId, week_start: mondayFor(reportDate) }));
      if (kind === "punctuality") setPunctuality(await api.punctualityReport({ company_id: companyId, date_from: dateFrom, date_to: dateTo, mode }));
    } catch (cause) {
      setError(cause);
    } finally {
      setRunning(false);
    }
  }

  function controls() {
    return <Card className="p-5"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><Field label="Grupo corporativo">{(id) => <Select id={id} value={groupId} onChange={(event) => setGroupId(event.target.value)}>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field>{kind !== "card" ? <Field label="Empresa">{(id) => <Select id={id} value={companyId} onChange={(event) => setCompanyId(event.target.value)}><option value="">Selecciona</option>{visibleCompanies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field> : <Field label="Trabajador">{(id) => <Select id={id} value={personId} onChange={(event) => setPersonId(event.target.value)}><option value="">Selecciona</option>{people.map((person) => <option key={person.id} value={person.id}>{person.first_name} {person.last_name} {person.second_last_name ?? ""}</option>)}</Select>}</Field>}{kind === "punctuality" ? <><Field label="Desde">{(id) => <Input id={id} type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />}</Field><Field label="Hasta">{(id) => <Input id={id} type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />}</Field><Field label="Mostrar">{(id) => <Select id={id} value={mode} onChange={(event) => setMode(event.target.value)}><option value="both">Ambos</option><option value="late">Sólo llegadas tarde</option><option value="early">Sólo salidas temprano</option></Select>}</Field></> : <Field label={kind === "card" ? "Cualquier día de la semana" : "Fecha"}>{(id) => <Input id={id} type="date" value={reportDate} onChange={(event) => setReportDate(event.target.value)} />}</Field>}</div><div className="mt-4 flex justify-end"><Button variant="primary" icon={<FileBarChart className="h-4 w-4" />} onClick={() => void runReport()} loading={running} disabled={kind === "card" ? !personId : !companyId}>Generar reporte</Button></div></Card>;
  }

  function result() {
    if (running) return <LoadingState rows={6} />;
    if (kind === "arrivals") return arrivals.length ? <Card className="overflow-hidden"><table className="w-full text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="p-3">Trabajador</th><th className="p-3">No. empleado</th><th className="p-3">Primera llegada</th><th className="p-3">Marcas</th></tr></thead><tbody>{arrivals.map((row) => <tr key={row.employment_id} className="border-t border-line-subtle"><td className="p-3 font-medium">{row.worker_name}</td><td className="p-3">{row.employee_number}</td><td className="p-3">{time(row.first_mark_at)}</td><td className="p-3">{row.mark_count}</td></tr>)}</tbody></table></Card> : <EmptyState icon={<LogIn className="h-5 w-5" />} title="Sin llegadas" description="No hay checadas vinculadas a trabajadores para esta fecha." />;
    if (kind === "absences") return absences.length ? <Card className="overflow-hidden"><table className="w-full text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="p-3">Trabajador</th><th className="p-3">No. empleado</th><th className="p-3">Entrada esperada</th></tr></thead><tbody>{absences.map((row) => <tr key={row.employment_id} className="border-t border-line-subtle"><td className="p-3 font-medium">{row.worker_name}</td><td className="p-3">{row.employee_number}</td><td className="p-3">{time(row.expected_entry_at)}</td></tr>)}</tbody></table></Card> : <EmptyState icon={<UserX className="h-5 w-5" />} title="Sin faltas" description="No hay ausencias para los turnos ya exigibles en esta fecha." />;
    if (kind === "card") return card ? <Card className="p-5"><p className="font-semibold">{card.worker_name}</p><p className="mt-1 text-sm text-zinc-500">Semana {card.week_start} a {card.week_end} · lunes a domingo</p><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-7">{card.days.map((day) => <div key={day.report_date} className="rounded-xl border border-line-subtle bg-zinc-50 p-3"><p className="text-xs font-medium text-zinc-500">{day.report_date}</p><p className="mt-2 text-sm">Entrada: {time(day.first_mark_at)}</p><p className="mt-1 text-sm">Salida: {time(day.last_mark_at)}</p><p className="mt-2 text-xs text-zinc-500">{day.mark_count} marca(s)</p></div>)}</div></Card> : <EmptyState icon={<CalendarDays className="h-5 w-5" />} title="Elige un trabajador" description="La tarjeta mostrará siete días, de lunes a domingo." />;
    return punctuality.length ? <Card className="overflow-hidden"><table className="w-full text-left text-sm"><thead className="bg-zinc-50 text-xs uppercase text-zinc-500"><tr><th className="p-3">Trabajador</th><th className="p-3">Fecha</th><th className="p-3">Llegada tarde</th><th className="p-3">Salida temprano</th></tr></thead><tbody>{punctuality.map((row) => <tr key={`${row.employment_id}-${row.report_date}`} className="border-t border-line-subtle"><td className="p-3 font-medium">{row.worker_name}<p className="text-xs font-normal text-zinc-500">{row.employee_number}</p></td><td className="p-3">{row.report_date}</td><td className="p-3">{row.late_minutes ? minutes(row.late_minutes) : "—"}</td><td className="p-3">{row.early_departure_minutes ? minutes(row.early_departure_minutes) : "—"}</td></tr>)}</tbody></table></Card> : <EmptyState icon={<Clock3 className="h-5 w-5" />} title="Sin incidencias" description="No hay retardos ni salidas tempranas para los filtros elegidos." />;
  }

  if (loading) return <LoadingState rows={6} />;
  return <><PageHeader title="Reportes" description="Asistencia calculada con horarios, tolerancias, días de descanso y feriados." crumbs={[{ label: "Reportes" }]} />{error ? <div className="mb-5"><ErrorState error={error} onRetry={() => void runReport()} /></div> : null}<div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">{REPORTS.map((report) => <button key={report.id} onClick={() => setKind(report.id)} className={`rounded-2xl border p-4 text-left transition-colors ${kind === report.id ? "border-accent bg-accent-50" : "border-line-subtle bg-white hover:bg-zinc-50"}`}><span className="text-accent-700">{report.icon}</span><p className="mt-3 font-semibold text-zinc-900">{report.label}</p><p className="mt-1 text-sm text-zinc-500">{report.description}</p></button>)}</div>{controls()}<div className="mt-5">{result()}</div></>;
}

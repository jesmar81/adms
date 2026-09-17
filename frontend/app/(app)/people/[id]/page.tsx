"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { ArrowLeft, CalendarDays, Clock3, Plus, Save, ShieldCheck, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AttendanceRow, Company, Employment, Person, ScheduleAssignment, WorkSchedule } from "@/types";

const PROFILE_FIELDS = [
  ["phone", "Teléfono", "tel"], ["email", "Correo", "email"], ["birth_date", "Fecha de nacimiento", "date"],
  ["sex", "Sexo", "text"], ["marital_status", "Estado civil", "text"], ["nationality", "Nacionalidad", "text"],
  ["birth_state", "Entidad de nacimiento", "text"], ["address_street", "Calle", "text"],
  ["address_ext_number", "No. exterior", "text"], ["address_int_number", "No. interior", "text"],
  ["address_neighborhood", "Colonia", "text"], ["address_municipality", "Municipio / alcaldía", "text"],
  ["address_state", "Estado", "text"], ["postal_code", "Código postal", "text"],
] as const;

const ATTENDANCE_COLUMNS: Column<AttendanceRow>[] = [
  { key: "recorded_at", header: "Fecha y hora", render: (row) => formatDateTime(row.recorded_at) },
  { key: "pin", header: "PIN", render: (row) => <span className="font-mono">{row.device_user_pin}</span> },
  { key: "status", header: "Estado", render: (row) => row.status },
  { key: "verify", header: "Validación", render: (row) => row.verify_mode },
];

function isoDate(value: Date) {
  return value.toISOString().slice(0, 10);
}

function initialDraft(person: Person): Record<string, string> {
  return Object.fromEntries(PROFILE_FIELDS.map(([key]) => [key, person[key] ?? ""]));
}

function PersonDetail({ id }: { id: string }) {
  const { notify } = useToast();
  const today = new Date();
  const monthAgo = new Date(today);
  monthAgo.setDate(monthAgo.getDate() - 30);
  const [person, setPerson] = useState<Person | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [employments, setEmployments] = useState<Employment[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [schedules, setSchedules] = useState<WorkSchedule[]>([]);
  const [assignments, setAssignments] = useState<Record<string, ScheduleAssignment[]>>({});
  const [marks, setMarks] = useState<AttendanceRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState(isoDate(monthAgo));
  const [dateTo, setDateTo] = useState(isoDate(today));
  const [sensitive, setSensitive] = useState<Record<string, string>>({});
  const [sensitiveOpen, setSensitiveOpen] = useState(false);
  const [companyId, setCompanyId] = useState("");
  const [employeeNumber, setEmployeeNumber] = useState("");
  const [position, setPosition] = useState("");
  const [startedOn, setStartedOn] = useState(isoDate(today));
  const [scheduleId, setScheduleId] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await Promise.all([
        api.person(id),
        api.employments({ person_id: id }),
        api.companies(),
        api.personAttendance(id, { date_from: new Date(dateFrom + "T00:00:00").toISOString(), date_to: new Date(dateTo + "T23:59:59").toISOString() }),
      ]);
      const loadedPerson = loaded[0];
      const loadedEmployments = loaded[1];
      const companyIds = [...new Set(loadedEmployments.map((item) => item.company_id))];
      const relatedSchedules = await Promise.all(companyIds.map((item) => api.workSchedules(item)));
      const assignmentLists = await Promise.all(loadedEmployments.map((item) => api.scheduleAssignments(item.id)));
      setPerson(loadedPerson);
      setDraft(initialDraft(loadedPerson));
      setEmployments(loadedEmployments);
      setCompanies(loaded[2]);
      setSchedules(relatedSchedules.flat());
      setAssignments(Object.fromEntries(loadedEmployments.map((item, index) => [item.id, assignmentLists[index]])));
      setMarks(loaded[3].items);
      setNextCursor(loaded[3].next_cursor);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, id]);

  useEffect(() => void load(), [load]);

  useEffect(() => {
    if (!companyId) return;
    void api.workSchedules(companyId).then((items) => {
      setSchedules((current) => [...current.filter((item) => item.company_id !== companyId), ...items]);
      setScheduleId(items[0]?.id ?? "");
    }).catch(setError);
  }, [companyId]);

  async function saveProfile() {
    setSaving(true);
    try {
      const body = Object.fromEntries(Object.entries(draft).map(([key, value]) => [key, value.trim() || null]));
      const updated = await api.updatePerson(id, body);
      setPerson(updated);
      setDraft(initialDraft(updated));
      notify("Expediente actualizado", { tone: "success" });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function openSensitive() {
    try {
      const value = await api.personSensitive(id);
      setSensitive({ curp: value.curp ?? "", rfc: value.rfc ?? "", nss: value.nss ?? "" });
      setSensitiveOpen(true);
    } catch (err) {
      setError(err);
    }
  }

  async function saveSensitive() {
    setSaving(true);
    try {
      const value = await api.updatePersonSensitive(id, {
        curp: sensitive.curp?.trim() || null,
        rfc: sensitive.rfc?.trim() || null,
        nss: sensitive.nss?.trim() || null,
      });
      setSensitive({ curp: value.curp ?? "", rfc: value.rfc ?? "", nss: value.nss ?? "" });
      notify("Identificadores protegidos actualizados", { tone: "success" });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function createEmployment() {
    if (!companyId || !employeeNumber.trim() || saving) return;
    setSaving(true);
    try {
      const employment = await api.createEmployment(id, { company_id: companyId, employee_number: employeeNumber.trim(), position: position.trim() || null, started_on: startedOn });
      if (scheduleId) await api.assignWorkSchedule(employment.id, { work_schedule_id: scheduleId, effective_from: startedOn });
      setCompanyId("");
      setEmployeeNumber("");
      setPosition("");
      setScheduleId("");
      notify("Empleo creado", { message: "El horario quedó asociado a este empleo.", tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function loadMore() {
    if (!nextCursor) return;
    try {
      const page = await api.personAttendance(id, { date_from: new Date(dateFrom + "T00:00:00").toISOString(), date_to: new Date(dateTo + "T23:59:59").toISOString(), cursor: nextCursor });
      setMarks((current) => [...current, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err);
    }
  }

  const fullName = person ? [person.first_name, person.last_name, person.second_last_name].filter(Boolean).join(" ") : "Expediente";
  const selectedSchedules = schedules.filter((item) => item.company_id === companyId);
  return (
    <>
      <PageHeader title={fullName} description="Expediente personal, empleos, horarios y checadas del reloj." crumbs={[{ label: "Personas", href: "/people" }, { label: "Expediente" }]} actions={<Link href="/people"><Button variant="secondary" icon={<ArrowLeft className="h-4 w-4" />}>Volver</Button></Link>} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      {loading ? <LoadingState rows={8} /> : <>
        <div className="grid gap-5 xl:grid-cols-2">
          <Card className="p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><UserRound className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Datos personales y domicilio</p><p className="text-sm text-zinc-500">Comunes a todos los empleos del grupo.</p></div></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{PROFILE_FIELDS.map(([key, label, type]) => <Field key={key} label={label}>{(fieldId) => <Input id={fieldId} type={type} value={draft[key] ?? ""} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} />}</Field>)}</div><div className="mt-4 grid gap-3 sm:grid-cols-3"><Field label="Contacto de emergencia">{(fieldId) => <Input id={fieldId} value={draft.emergency_contact_name ?? ""} onChange={(event) => setDraft((current) => ({ ...current, emergency_contact_name: event.target.value }))} />}</Field><Field label="Teléfono emergencia">{(fieldId) => <Input id={fieldId} value={draft.emergency_contact_phone ?? ""} onChange={(event) => setDraft((current) => ({ ...current, emergency_contact_phone: event.target.value }))} />}</Field><Field label="Parentesco">{(fieldId) => <Input id={fieldId} value={draft.emergency_contact_relationship ?? ""} onChange={(event) => setDraft((current) => ({ ...current, emergency_contact_relationship: event.target.value }))} />}</Field></div><Button className="mt-5" variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void saveProfile()} loading={saving}>Guardar expediente</Button></Card>
          <div className="flex flex-col gap-5">
            <Card className="p-5"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-3"><div className="rounded-xl bg-amber-50 p-2.5 text-amber-700"><ShieldCheck className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Datos fiscales y seguridad social</p><p className="text-sm text-zinc-500">CURP, RFC y NSS se cifran antes de almacenarse.</p></div></div>{!sensitiveOpen ? <Button variant="secondary" onClick={() => void openSensitive()}>Mostrar / editar</Button> : null}</div>{sensitiveOpen ? <div className="mt-5 grid gap-3 sm:grid-cols-3">{[["curp", "CURP"], ["rfc", "RFC"], ["nss", "NSS / IMSS"]].map(([key, label]) => <Field key={key} label={label}>{(fieldId) => <Input id={fieldId} value={sensitive[key] ?? ""} onChange={(event) => setSensitive((current) => ({ ...current, [key]: event.target.value.toUpperCase() }))} />}</Field>)}<div className="sm:col-span-3"><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void saveSensitive()} loading={saving}>Guardar protegidos</Button></div></div> : null}</Card>
            <Card className="p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><CalendarDays className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Empleos y horarios</p><p className="text-sm text-zinc-500">Cada empleo mantiene su propio horario.</p></div></div><div className="mt-5 grid gap-3">{employments.length ? employments.map((employment) => { const assignment = assignments[employment.id]?.find((item) => item.active && !item.effective_to); const schedule = schedules.find((item) => item.id === assignment?.work_schedule_id); return <div key={employment.id} className="rounded-xl border border-line-subtle bg-zinc-50/60 px-4 py-3"><p className="font-medium">{employment.employee_number}</p><p className="mt-1 text-sm text-zinc-600">{[employment.position, employment.department].filter(Boolean).join(" · ") || "Puesto pendiente"}</p><p className="mt-2 text-xs text-zinc-500">Horario: {schedule ? schedule.name : "Sin horario asignado"}</p></div>; }) : <p className="text-sm text-zinc-500">Aún no hay empleos asignados.</p>}</div></Card>
          </div>
        </div>
        <Card className="mt-5 p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><Plus className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Agregar empleo</p><p className="text-sm text-zinc-500">El número y horario pertenecen a la relación laboral con esa empresa.</p></div></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5"><Field label="Empresa">{(fieldId) => <Select id={fieldId} value={companyId} onChange={(event) => setCompanyId(event.target.value)}><option value="">Selecciona</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field><Field label="No. empleado">{(fieldId) => <Input id={fieldId} value={employeeNumber} onChange={(event) => setEmployeeNumber(event.target.value)} />}</Field><Field label="Puesto">{(fieldId) => <Input id={fieldId} value={position} onChange={(event) => setPosition(event.target.value)} />}</Field><Field label="Inicio">{(fieldId) => <Input id={fieldId} type="date" value={startedOn} onChange={(event) => setStartedOn(event.target.value)} />}</Field><Field label="Horario inicial">{(fieldId) => <Select id={fieldId} value={scheduleId} onChange={(event) => setScheduleId(event.target.value)} disabled={!companyId}><option value="">Sin asignar ahora</option>{selectedSchedules.map((schedule) => <option key={schedule.id} value={schedule.id}>{schedule.name}</option>)}</Select>}</Field></div><Button className="mt-4" variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createEmployment()} loading={saving} disabled={!companyId || !employeeNumber.trim()}>Crear empleo</Button></Card>
        <Card className="mt-5 p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><Clock3 className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Checadas capturadas</p><p className="text-sm text-zinc-500">Último mes por defecto; el año se consulta en bloques de 100.</p></div></div><div className="flex flex-wrap items-end gap-2"><div className="w-36"><Field label="Desde">{(fieldId) => <Input id={fieldId} type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />}</Field></div><div className="w-36"><Field label="Hasta">{(fieldId) => <Input id={fieldId} type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />}</Field></div><Button variant="secondary" onClick={() => { setDateFrom(String(today.getFullYear()) + "-01-01"); setDateTo(isoDate(today)); }}>Año actual</Button></div></div></Card>
        <div className="mt-4"><DataTable ariaLabel="Checadas de la persona" columns={ATTENDANCE_COLUMNS} data={marks} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{formatDateTime(row.recorded_at)}</p><p className="mt-1 text-xs text-zinc-500">PIN {row.device_user_pin} · Estado {row.status}</p></div>} empty={<EmptyState icon={<Clock3 className="h-5 w-5" />} title="Sin checadas en este periodo" description="Aparecerán al vincular el PIN del reloj con esta persona." />} /></div>
        {nextCursor ? <div className="mt-5 flex justify-center"><Button variant="secondary" onClick={() => void loadMore()}>Cargar las siguientes 100</Button></div> : null}
      </>}
    </>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <PersonDetail id={id} />;
}

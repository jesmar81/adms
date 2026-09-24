"use client";
/* eslint-disable @next/next/no-img-element -- authenticated image Blob URLs cannot use Next optimization */

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Camera, Clock3, Fingerprint, Pencil, Save, ShieldCheck, Trash2, UserRound, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { EmploymentSections } from "@/components/people/EmploymentSections";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { AttendanceRow, Company, Employment, Person, PersonDeviceUserLink, ScheduleAssignment, WorkSchedule } from "@/types";

const PERSONAL_FIELDS = [
  ["first_name", "Nombre(s)", "text"], ["last_name", "Apellido paterno", "text"], ["second_last_name", "Apellido materno", "text"],
  ["preferred_name", "Nombre preferido", "text"], ["phone", "Teléfono", "tel"], ["email", "Correo", "email"], ["birth_date", "Fecha de nacimiento", "date"],
  ["sex", "Sexo", "text"], ["marital_status", "Estado civil", "text"], ["nationality", "Nacionalidad", "text"],
  ["birth_state", "Entidad de nacimiento", "text"],
] as const;

const ADDRESS_FIELDS = [
  ["address_street", "Calle", "text"],
  ["address_ext_number", "No. exterior", "text"], ["address_int_number", "No. interior", "text"],
  ["address_neighborhood", "Colonia", "text"], ["address_municipality", "Municipio / alcaldía", "text"],
  ["address_state", "Estado", "text"], ["postal_code", "Código postal", "text"],
] as const;

const PROFILE_FIELDS = [...PERSONAL_FIELDS, ...ADDRESS_FIELDS] as const;

const MEXICAN_STATES = [
  "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila de Zaragoza", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán de Ocampo", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz de Ignacio de la Llave", "Yucatán", "Zacatecas",
] as const;

const PROFILE_SELECT_OPTIONS: Partial<Record<(typeof PROFILE_FIELDS)[number][0], readonly string[]>> = {
  sex: ["Mujer", "Hombre", "No especificar"],
  marital_status: ["Soltero(a)", "Casado(a)", "Unión libre", "Divorciado(a)", "Viudo(a)", "Separado(a)"],
  nationality: ["Mexicana", "Extranjera"],
  birth_state: MEXICAN_STATES,
  address_state: MEXICAN_STATES,
};

const EMERGENCY_RELATIONSHIPS = ["Madre", "Padre", "Cónyuge", "Pareja", "Hijo(a)", "Hermano(a)", "Tutor(a)", "Otro"] as const;

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
  return {
    ...Object.fromEntries(PROFILE_FIELDS.map(([key]) => [key, person[key] ?? (key === "nationality" ? "Mexicana" : "")])),
    emergency_contact_name: person.emergency_contact_name ?? "",
    emergency_contact_phone: person.emergency_contact_phone ?? "",
    emergency_contact_relationship: person.emergency_contact_relationship ?? "",
  };
}

function PersonDetail({ id }: { id: string }) {
  const { notify } = useToast();
  const { can } = useAuth();
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
  const [deviceLinks, setDeviceLinks] = useState<PersonDeviceUserLink[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState(isoDate(monthAgo));
  const [dateTo, setDateTo] = useState(isoDate(today));
  const [sensitive, setSensitive] = useState<Record<string, string>>({});
  const [sensitiveOpen, setSensitiveOpen] = useState(false);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [compensationEmployment, setCompensationEmployment] = useState<Employment | null>(null);
  const [compensation, setCompensation] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const refreshEmployments = useCallback(async () => {
    const loadedEmployments = await api.employments({ person_id: id });
    const companyIds = [...new Set(loadedEmployments.map((item) => item.company_id))];
    const [relatedSchedules, assignmentLists] = await Promise.all([
      Promise.all(companyIds.map((companyId) => api.workSchedules(companyId))),
      Promise.all(loadedEmployments.map((item) => api.scheduleAssignments(item.id))),
    ]);
    setEmployments(loadedEmployments);
    setSchedules(relatedSchedules.flat());
    setAssignments(Object.fromEntries(loadedEmployments.map((item, index) => [item.id, assignmentLists[index]])));
  }, [id]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loaded = await Promise.all([
        api.person(id),
        api.employments({ person_id: id }),
        api.companies(),
        api.personPhoto(id),
        can("device_users.read") ? api.personDeviceUsers(id) : Promise.resolve([] as PersonDeviceUserLink[]),
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
      setPhotoUrl(loaded[3] ? URL.createObjectURL(loaded[3]) : null);
      setDeviceLinks(loaded[4]);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [can, id]);

  useEffect(() => void load(), [load]);

  useEffect(() => {
    let active = true;
    setAttendanceLoading(true);
    void api.personAttendance(id, {
      date_from: new Date(dateFrom + "T00:00:00").toISOString(),
      date_to: new Date(dateTo + "T23:59:59").toISOString(),
    }).then((page) => {
      if (active) { setMarks(page.items); setNextCursor(page.next_cursor); }
    }).catch((err) => { if (active) setError(err); })
      .finally(() => { if (active) setAttendanceLoading(false); });
    return () => { active = false; };
  }, [dateFrom, dateTo, id]);

  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);

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
      setSensitive({ curp: value.curp ?? "", rfc: value.rfc ?? "", nss: value.nss ?? "", fiscal_name: value.fiscal_name ?? "", tax_regime: value.tax_regime ?? "", fiscal_postal_code: value.fiscal_postal_code ?? "" });
      setSensitiveOpen(true);
    } catch (err) {
      setError(err);
    }
  }

  async function updatePhoto(file: File | undefined) {
    if (!file || saving) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError(new Error("La fotografía debe ser JPG, PNG o WebP y pesar máximo 5 MB."));
      return;
    }
    setSaving(true);
    try {
      await api.uploadPersonPhoto(id, file);
      setPhotoUrl(URL.createObjectURL(file));
      notify("Fotografía actualizada", { tone: "success" });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function removePhoto() {
    if (!photoUrl || saving || !window.confirm("¿Quitar la fotografía del trabajador?")) return;
    setSaving(true);
    try {
      await api.deletePersonPhoto(id);
      setPhotoUrl(null);
      notify("Fotografía eliminada", { tone: "success" });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function saveSensitive() {
    setSaving(true);
    try {
      const value = await api.updatePersonSensitive(id, {
        curp: sensitive.curp?.trim() || null,
        rfc: sensitive.rfc?.trim() || null,
        nss: sensitive.nss?.trim() || null,
        fiscal_name: sensitive.fiscal_name?.trim() || null,
        tax_regime: sensitive.tax_regime?.trim() || null,
        fiscal_postal_code: sensitive.fiscal_postal_code?.trim() || null,
      });
      setSensitive({ curp: value.curp ?? "", rfc: value.rfc ?? "", nss: value.nss ?? "", fiscal_name: value.fiscal_name ?? "", tax_regime: value.tax_regime ?? "", fiscal_postal_code: value.fiscal_postal_code ?? "" });
      notify("Identificadores protegidos actualizados", { tone: "success" });
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function openCompensation(employment: Employment) {
    try {
      const loaded = await api.employmentCompensation(employment.id);
      setCompensation({
        daily_salary: loaded.daily_salary ?? "",
        integrated_daily_salary: loaded.integrated_daily_salary ?? "",
        pay_frequency: loaded.pay_frequency ?? "",
        payment_method: loaded.payment_method ?? "",
        bank_clabe: loaded.bank_clabe ?? "",
        imss_umf: loaded.imss_umf ?? "",
        imss_worker_type: loaded.imss_worker_type ?? "",
        imss_salary_type: loaded.imss_salary_type ?? "",
        imss_workday_type: loaded.imss_workday_type ?? "",
      });
      setCompensationEmployment(employment);
    } catch (err) {
      setError(err);
    }
  }

  async function saveCompensation() {
    if (!compensationEmployment || saving) return;
    setSaving(true);
    try {
      await api.updateEmploymentCompensation(compensationEmployment.id, {
        daily_salary: compensation.daily_salary || null,
        integrated_daily_salary: compensation.integrated_daily_salary || null,
        pay_frequency: compensation.pay_frequency || null,
        payment_method: compensation.payment_method || null,
        bank_clabe: compensation.bank_clabe || null,
        imss_umf: compensation.imss_umf || null,
        imss_worker_type: compensation.imss_worker_type || null,
        imss_salary_type: compensation.imss_salary_type || null,
        imss_workday_type: compensation.imss_workday_type || null,
      });
      notify("Nómina e IMSS actualizados", { tone: "success" });
      setCompensationEmployment(null);
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
  return (
    <>
      <PageHeader title={fullName} description="Expediente del trabajador, empleos, horarios y checadas del reloj." crumbs={[{ label: "Trabajadores", href: "/people" }, { label: "Expediente" }]} actions={<Link href="/people"><Button variant="secondary" icon={<ArrowLeft className="h-4 w-4" />}>Volver</Button></Link>} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      {loading ? <LoadingState rows={8} /> : <>
        <div className="space-y-5">
          <Card className="p-5">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-accent-soft p-2 text-accent"><UserRound className="h-5 w-5" aria-hidden /></div>
              <div><h2 className="font-semibold text-foreground">Expediente personal</h2><p className="text-sm text-muted">Estos datos pertenecen a la persona y son comunes a todos sus empleos.</p></div>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-4 rounded-lg border border-line-subtle bg-surface-raised/50 p-3">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-surface-hover">
                {photoUrl ? <img src={photoUrl} alt="Fotografía del trabajador" className="h-full w-full object-cover" /> : <UserRound className="h-8 w-8 text-muted" aria-hidden />}
              </div>
              <div className="min-w-0 flex-1"><Field label="Fotografía" hint="La fotografía se guarda al seleccionarla.">{(fieldId) => <Input id={fieldId} type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void updatePhoto(event.target.files?.[0])} disabled={saving} />}</Field></div>
              {photoUrl ? <Button variant="ghost" icon={<Trash2 className="h-4 w-4" />} aria-label="Eliminar fotografía" title="Eliminar fotografía" onClick={() => void removePhoto()} disabled={saving} /> : <Camera className="h-5 w-5 shrink-0 text-muted" aria-hidden />}
            </div>
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-foreground">Identidad y contacto</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {PERSONAL_FIELDS.map(([key, label, type]) => <Field key={key} label={label}>{(fieldId) => {
                  const options = PROFILE_SELECT_OPTIONS[key];
                  return options ? <Select id={fieldId} value={draft[key] ?? ""} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))}><option value="">Selecciona</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</Select> : <Input id={fieldId} type={type} value={draft[key] ?? ""} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} />;
                }}</Field>)}
              </div>
            </div>
            <div className="mt-6 border-t border-line-subtle pt-5">
              <h3 className="text-sm font-semibold text-foreground">Domicilio</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {ADDRESS_FIELDS.map(([key, label, type]) => <Field key={key} label={label}>{(fieldId) => {
                  const options = PROFILE_SELECT_OPTIONS[key];
                  return options ? <Select id={fieldId} value={draft[key] ?? ""} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))}><option value="">Selecciona</option>{options.map((option) => <option key={option} value={option}>{option}</option>)}</Select> : <Input id={fieldId} type={type} value={draft[key] ?? ""} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} />;
                }}</Field>)}
              </div>
            </div>
            <div className="mt-6 border-t border-line-subtle pt-5">
              <h3 className="text-sm font-semibold text-foreground">Contacto de emergencia</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <Field label="Nombre">{(fieldId) => <Input id={fieldId} value={draft.emergency_contact_name ?? ""} onChange={(event) => setDraft((current) => ({ ...current, emergency_contact_name: event.target.value }))} />}</Field>
                <Field label="Teléfono">{(fieldId) => <Input id={fieldId} value={draft.emergency_contact_phone ?? ""} onChange={(event) => setDraft((current) => ({ ...current, emergency_contact_phone: event.target.value }))} />}</Field>
                <Field label="Parentesco">{(fieldId) => <Select id={fieldId} value={draft.emergency_contact_relationship ?? ""} onChange={(event) => setDraft((current) => ({ ...current, emergency_contact_relationship: event.target.value }))}><option value="">Selecciona</option>{EMERGENCY_RELATIONSHIPS.map((relationship) => <option key={relationship} value={relationship}>{relationship}</option>)}</Select>}</Field>
              </div>
            </div>
            <div className="mt-6 flex justify-end border-t border-line-subtle pt-4">
              <Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void saveProfile()} loading={saving} disabled={!draft.first_name?.trim() || !draft.last_name?.trim()}>Guardar datos personales</Button>
            </div>
          </Card>
          <div className="flex flex-col gap-5">
            {can("people.sensitive.read") ? <Card className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3"><div className="rounded-lg bg-amber-500/10 p-2 text-amber-400"><ShieldCheck className="h-5 w-5" aria-hidden /></div><div><h2 className="font-semibold text-foreground">Datos fiscales y seguridad social</h2><p className="text-sm text-muted">CURP, RFC, NSS y datos CFDI protegidos.</p></div></div>
                {!sensitiveOpen ? <Button variant="secondary" icon={<Pencil className="h-4 w-4" />} onClick={() => void openSensitive()}>Ver y editar datos</Button> : null}
              </div>
              {sensitiveOpen ? <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {[["curp", "CURP"], ["rfc", "RFC"], ["nss", "NSS / IMSS"], ["fiscal_name", "Nombre fiscal"], ["tax_regime", "Régimen fiscal"], ["fiscal_postal_code", "CP fiscal"]].map(([key, label]) => <Field key={key} label={label}>{(fieldId) => <Input id={fieldId} value={sensitive[key] ?? ""} disabled={!can("people.sensitive.write")} onChange={(event) => setSensitive((current) => ({ ...current, [key]: event.target.value.toUpperCase() }))} />}</Field>)}
                </div>
                {can("people.sensitive.write") ? <div className="mt-5 flex justify-end border-t border-line-subtle pt-4"><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void saveSensitive()} loading={saving}>Guardar datos fiscales</Button></div> : null}
              </> : null}
            </Card> : null}
          </div>
        </div>
        <EmploymentSections personId={id} employments={employments} companies={companies} schedules={schedules} assignments={assignments} onChanged={refreshEmployments} onCompensation={(employment) => void openCompensation(employment)} />
        {can("device_users.read") ? <Card className="mt-5 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><div className="rounded-lg bg-accent-soft p-2 text-accent"><Fingerprint className="h-5 w-5" aria-hidden /></div><div><h2 className="font-semibold text-foreground">Identidades en reloj</h2><p className="text-sm text-muted">PIN y nombre configurado en cada dispositivo.</p></div></div><Link href="/device-users" className="text-xs font-medium text-accent hover:text-accent-hover">Administrar</Link></div>
          <div className="mt-4 grid gap-2">{deviceLinks.length ? deviceLinks.map((link) => <div key={`${link.device_id}:${link.pin}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line-subtle bg-surface-raised/50 px-3 py-2.5"><div className="min-w-0"><p className="truncate text-sm font-medium text-foreground">{link.device_name || link.device_serial_number}</p><p className="mt-0.5 text-xs text-muted">PIN <span className="font-mono font-medium text-foreground">{link.pin}</span> · {link.device_serial_number}</p><p className="mt-0.5 truncate text-xs text-muted">Nombre en reloj: {link.device_name_on_terminal || "Sin nombre"}</p></div><span className={`rounded-full px-2 py-1 text-[10px] font-medium ${link.sync_state === "synced" ? "bg-emerald-500/10 text-emerald-300" : link.sync_state === "failed" ? "bg-rose-500/10 text-rose-300" : "bg-amber-500/10 text-amber-300"}`}>{link.sync_state === "synced" ? "Confirmado" : link.sync_state === "failed" ? "Fallido" : "Pendiente"}</span></div>) : <EmptyState icon={<Fingerprint className="h-5 w-5" />} title="Sin PIN vinculado" description="Importa o vincula el PIN desde Personal en reloj para asociar sus checadas con este expediente." />}</div>
        </Card> : null}
        <Card className="mt-5 p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex items-center gap-3"><div className="rounded-lg bg-accent-soft p-2 text-accent"><Clock3 className="h-5 w-5" aria-hidden /></div><div><h2 className="font-semibold text-foreground">Checadas capturadas</h2><p className="text-sm text-muted">Último mes por defecto; el año se consulta en bloques de 100.</p></div></div>
            <div className="grid grid-cols-2 items-end gap-2 lg:flex lg:flex-wrap">
              <div className="min-w-0"><Field label="Desde">{(fieldId) => <Input id={fieldId} type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />}</Field></div>
              <div className="min-w-0"><Field label="Hasta">{(fieldId) => <Input id={fieldId} type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />}</Field></div>
              <Button variant="secondary" className="col-span-2 lg:col-span-1" onClick={() => { setDateFrom(String(today.getFullYear()) + "-01-01"); setDateTo(isoDate(today)); }}>Año actual</Button>
            </div>
          </div>
        </Card>
        <div className="mt-4">{attendanceLoading ? <LoadingState rows={4} /> : <DataTable ariaLabel="Checadas de la persona" columns={ATTENDANCE_COLUMNS} data={marks} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{formatDateTime(row.recorded_at)}</p><p className="mt-1 text-xs text-muted">PIN {row.device_user_pin} · Estado {row.status}</p></div>} empty={<EmptyState icon={<Clock3 className="h-5 w-5" />} title="Sin checadas en este periodo" description="Aparecerán al vincular el PIN del reloj con esta persona." />} />}</div>
        {nextCursor && !attendanceLoading ? <div className="mt-5 flex justify-center"><Button variant="secondary" onClick={() => void loadMore()}>Cargar las siguientes 100</Button></div> : null}
        <Modal open={compensationEmployment !== null} onClose={() => setCompensationEmployment(null)} title="Nómina e IMSS" description={compensationEmployment ? `Empleo ${compensationEmployment.employee_number}. Acceso restringido; CLABE cifrada al guardar.` : undefined} footer={<><Button variant="ghost" icon={<X className="h-4 w-4" />} onClick={() => setCompensationEmployment(null)}>Cancelar</Button><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void saveCompensation()} loading={saving}>Guardar nómina e IMSS</Button></>}><div className="grid gap-3 sm:grid-cols-2"><Field label="Salario diario">{(fieldId) => <Input id={fieldId} type="number" min="0" step="0.01" value={compensation.daily_salary ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, daily_salary: event.target.value }))} />}</Field><Field label="SBC / SDI">{(fieldId) => <Input id={fieldId} type="number" min="0" step="0.01" value={compensation.integrated_daily_salary ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, integrated_daily_salary: event.target.value }))} />}</Field><Field label="Periodicidad">{(fieldId) => <Select id={fieldId} value={compensation.pay_frequency ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, pay_frequency: event.target.value }))}><option value="">Selecciona</option><option value="semanal">Semanal</option><option value="catorcenal">Catorcenal</option><option value="quincenal">Quincenal</option><option value="mensual">Mensual</option></Select>}</Field><Field label="Método de pago">{(fieldId) => <Select id={fieldId} value={compensation.payment_method ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, payment_method: event.target.value }))}><option value="">Selecciona</option><option value="transferencia">Transferencia</option><option value="efectivo">Efectivo</option><option value="cheque">Cheque</option></Select>}</Field><Field label="CLABE">{(fieldId) => <Input id={fieldId} inputMode="numeric" maxLength={18} value={compensation.bank_clabe ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, bank_clabe: event.target.value.replace(/\D/g, "") }))} />}</Field><Field label="UMF">{(fieldId) => <Input id={fieldId} value={compensation.imss_umf ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, imss_umf: event.target.value }))} />}</Field><Field label="Tipo trabajador IMSS">{(fieldId) => <Input id={fieldId} value={compensation.imss_worker_type ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, imss_worker_type: event.target.value }))} />}</Field><Field label="Tipo salario IMSS">{(fieldId) => <Input id={fieldId} value={compensation.imss_salary_type ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, imss_salary_type: event.target.value }))} />}</Field><Field label="Tipo jornada IMSS">{(fieldId) => <Input id={fieldId} value={compensation.imss_workday_type ?? ""} onChange={(event) => setCompensation((current) => ({ ...current, imss_workday_type: event.target.value }))} />}</Field></div></Modal>
      </>}
    </>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <PersonDetail id={id} />;
}

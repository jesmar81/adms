"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Banknote, BriefcaseBusiness, CalendarDays, Pencil, Plus, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { ErrorState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Company, Employment, ScheduleAssignment, Site, WorkSchedule } from "@/types";

type EmploymentDraft = {
  company_id: string;
  site_id: string;
  employee_number: string;
  position: string;
  department: string;
  cost_center: string;
  contract_type: string;
  employment_relation_type: string;
  job_category: string;
  work_location: string;
  started_on: string;
  probation_ends_on: string;
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function emptyEmployment(): EmploymentDraft {
  return {
    company_id: "", site_id: "", employee_number: "", position: "", department: "",
    cost_center: "", contract_type: "", employment_relation_type: "", job_category: "",
    work_location: "", started_on: todayIso(), probation_ends_on: "",
  };
}

function employmentDraft(row: Employment): EmploymentDraft {
  return {
    company_id: row.company_id,
    site_id: row.site_id ?? "",
    employee_number: row.employee_number,
    position: row.position ?? "",
    department: row.department ?? "",
    cost_center: row.cost_center ?? "",
    contract_type: row.contract_type ?? "",
    employment_relation_type: row.employment_relation_type ?? "",
    job_category: row.job_category ?? "",
    work_location: row.work_location ?? "",
    started_on: row.started_on,
    probation_ends_on: row.probation_ends_on ?? "",
  };
}

function employmentPayload(draft: EmploymentDraft, original?: Employment) {
  return {
    company_id: draft.company_id,
    site_id: draft.site_id || null,
    employee_number: draft.employee_number.trim(),
    position: draft.position.trim() || null,
    department: draft.department.trim() || null,
    cost_center: draft.cost_center.trim() || null,
    manager_person_id: original?.manager_person_id ?? null,
    contract_type: draft.contract_type.trim() || null,
    employment_relation_type: draft.employment_relation_type || null,
    job_category: draft.job_category.trim() || null,
    work_location: draft.work_location.trim() || null,
    started_on: draft.started_on,
    ended_on: original?.ended_on ?? null,
    probation_ends_on: draft.probation_ends_on || null,
  };
}

function EmploymentFields({ draft, onChange, companies, editing = false }: {
  draft: EmploymentDraft;
  onChange: (next: EmploymentDraft) => void;
  companies: Company[];
  editing?: boolean;
}) {
  const [sites, setSites] = useState<Site[]>([]);
  const [siteError, setSiteError] = useState<unknown>(null);

  useEffect(() => {
    setSites([]);
    setSiteError(null);
    if (!draft.company_id) return;
    let active = true;
    void api.sites(draft.company_id).then((items) => {
      if (active) { setSites(items); setSiteError(null); }
    }).catch((error) => { if (active) setSiteError(error); });
    return () => { active = false; };
  }, [draft.company_id]);

  const change = (key: keyof EmploymentDraft, value: string) => onChange({ ...draft, [key]: value });
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Field label="Empresa">{(id) => <Select id={id} value={draft.company_id} disabled={editing} onChange={(event) => onChange({ ...draft, company_id: event.target.value, site_id: "" })}><option value="">Selecciona empresa</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field>
      <Field label="Sucursal">{(id) => <Select id={id} value={draft.site_id} disabled={!draft.company_id} onChange={(event) => change("site_id", event.target.value)}><option value="">Sin sucursal</option>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</Select>}</Field>
      <Field label="Número de empleado">{(id) => <Input id={id} value={draft.employee_number} onChange={(event) => change("employee_number", event.target.value)} maxLength={64} />}</Field>
      <Field label="Puesto">{(id) => <Input id={id} value={draft.position} onChange={(event) => change("position", event.target.value)} maxLength={150} />}</Field>
      <Field label="Departamento">{(id) => <Input id={id} value={draft.department} onChange={(event) => change("department", event.target.value)} maxLength={150} />}</Field>
      <Field label="Centro de costo">{(id) => <Input id={id} value={draft.cost_center} onChange={(event) => change("cost_center", event.target.value)} maxLength={100} />}</Field>
      <Field label="Relación laboral">{(id) => <Select id={id} value={draft.employment_relation_type} onChange={(event) => change("employment_relation_type", event.target.value)}><option value="">Selecciona</option><option value="indeterminado">Tiempo indeterminado</option><option value="determinado">Tiempo determinado</option><option value="obra">Por obra</option><option value="capacitación">Capacitación inicial</option></Select>}</Field>
      <Field label="Tipo de contrato">{(id) => <Input id={id} value={draft.contract_type} onChange={(event) => change("contract_type", event.target.value)} maxLength={80} placeholder="Individual, colectivo…" />}</Field>
      <Field label="Categoría">{(id) => <Input id={id} value={draft.job_category} onChange={(event) => change("job_category", event.target.value)} maxLength={100} />}</Field>
      <Field label="Lugar de trabajo">{(id) => <Input id={id} value={draft.work_location} onChange={(event) => change("work_location", event.target.value)} maxLength={150} />}</Field>
      <Field label="Fecha de inicio">{(id) => <Input id={id} type="date" value={draft.started_on} onChange={(event) => change("started_on", event.target.value)} />}</Field>
      <Field label="Fin de periodo de prueba">{(id) => <Input id={id} type="date" value={draft.probation_ends_on} onChange={(event) => change("probation_ends_on", event.target.value)} min={draft.started_on || undefined} />}</Field>
      {siteError ? <div className="sm:col-span-2 xl:col-span-3"><ErrorState error={siteError} /></div> : null}
    </div>
  );
}

function ScheduleEditor({ employment, companyName, schedules, assignments, onChanged }: {
  employment: Employment;
  companyName: string;
  schedules: WorkSchedule[];
  assignments: ScheduleAssignment[];
  onChanged: () => Promise<void>;
}) {
  const { can } = useAuth();
  const { notify } = useToast();
  const [selectedId, setSelectedId] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(todayIso());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const current = assignments.find((item) => item.active && !item.effective_to);
  const currentSchedule = schedules.find((item) => item.id === current?.work_schedule_id);
  const available = schedules.filter((item) => item.active && item.company_id === employment.company_id);
  const earliest = [employment.started_on, current?.effective_from ?? ""].filter(Boolean).sort().at(-1) ?? employment.started_on;
  const history = assignments.filter((item) => item.id !== current?.id);

  useEffect(() => {
    setSelectedId("");
    setEffectiveFrom([todayIso(), employment.started_on, current?.effective_from ?? ""].sort().at(-1) ?? todayIso());
  }, [employment.id, employment.started_on, current?.id, current?.effective_from]);

  async function save() {
    if (!selectedId || selectedId === current?.work_schedule_id || saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.replaceCurrentWorkSchedule(employment.id, { work_schedule_id: selectedId, effective_from: effectiveFrom });
      setSelectedId("");
      notify("Horario guardado", { message: `La asignación de ${companyName} quedó registrada.`, tone: "success" });
      await onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-line-subtle bg-surface-raised/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-sm font-semibold text-foreground">{companyName} · {employment.employee_number}</p><p className="mt-1 text-xs text-muted">Horario actual: <span className="font-medium text-foreground">{currentSchedule ? `${currentSchedule.name} (v${currentSchedule.version})` : current ? "Horario no disponible" : "Sin asignar"}</span>{current ? ` · desde ${current.effective_from}` : ""}</p></div>
        <Link href="/work-schedules" className="text-xs font-medium text-accent hover:text-accent-hover">Ver definiciones de horarios</Link>
      </div>
      {can("schedules.write") ? <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(10rem,13rem)_auto] sm:items-end">
        <Field label={current ? "Nuevo horario" : "Asignar horario"}>{(id) => <Select id={id} value={selectedId} onChange={(event) => setSelectedId(event.target.value)}><option value="">Selecciona un horario</option>{available.map((item) => <option key={item.id} value={item.id}>{item.name} (v{item.version})</option>)}</Select>}</Field>
        <Field label="Vigente desde">{(id) => <Input id={id} type="date" value={effectiveFrom} min={earliest} max={employment.ended_on ?? undefined} onChange={(event) => setEffectiveFrom(event.target.value)} />}</Field>
        <Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void save()} loading={saving} disabled={!selectedId || selectedId === current?.work_schedule_id || !effectiveFrom || effectiveFrom < earliest || Boolean(employment.ended_on && effectiveFrom > employment.ended_on)}>Guardar horario</Button>
      </div> : null}
      {!available.length ? <p className="mt-3 text-xs text-muted">Esta empresa todavía no tiene horarios activos. Crea uno en Horarios para poder asignarlo.</p> : null}
      {history.length ? <details className="mt-4 border-t border-line-subtle pt-3 text-xs text-muted"><summary className="cursor-pointer font-medium text-foreground">Historial de horarios ({history.length})</summary><ul className="mt-2 space-y-1">{history.map((item) => { const name = schedules.find((schedule) => schedule.id === item.work_schedule_id)?.name ?? "Horario no disponible"; return <li key={item.id}>{name} · {item.effective_from} a {item.effective_to ?? "sin cierre"}</li>; })}</ul></details> : null}
      {error ? <div className="mt-3"><ErrorState error={error} /></div> : null}
    </div>
  );
}

export function EmploymentSections({ personId, employments, companies, schedules, assignments, onChanged, onCompensation }: {
  personId: string;
  employments: Employment[];
  companies: Company[];
  schedules: WorkSchedule[];
  assignments: Record<string, ScheduleAssignment[]>;
  onChanged: () => Promise<void>;
  onCompensation: (employment: Employment) => void;
}) {
  const { can } = useAuth();
  const { notify } = useToast();
  const [creating, setCreating] = useState(false);
  const [createDraft, setCreateDraft] = useState<EmploymentDraft>(emptyEmployment);
  const [editing, setEditing] = useState<Employment | null>(null);
  const [editDraft, setEditDraft] = useState<EmploymentDraft>(emptyEmployment);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function createEmployment() {
    if (!createDraft.company_id || !createDraft.employee_number.trim() || !createDraft.started_on || saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.createEmployment(personId, employmentPayload(createDraft));
      setCreateDraft(emptyEmployment());
      setCreating(false);
      notify("Empleo creado", { message: "Ya puedes asignarle un horario en la sección siguiente.", tone: "success" });
      await onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function saveEmployment() {
    if (!editing || !editDraft.employee_number.trim() || !editDraft.started_on || saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateEmployment(editing.id, employmentPayload(editDraft, editing));
      setEditing(null);
      notify("Contrato actualizado", { tone: "success" });
      await onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card className="mt-5 p-5" >
        <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-center gap-3"><div className="rounded-lg bg-accent-soft p-2 text-accent"><BriefcaseBusiness className="h-5 w-5" aria-hidden /></div><div><h2 className="font-semibold text-foreground">Empleos y contratos</h2><p className="text-sm text-muted">Una relación laboral independiente por empresa. Aquí se guardan sus datos contractuales.</p></div></div>{can("employments.write") ? <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => { setCreating((value) => !value); setError(null); }}>{creating ? "Cerrar formulario" : "Agregar empleo"}</Button> : null}</div>
        <div className="mt-5 grid gap-3">{employments.length ? employments.map((employment) => <div key={employment.id} className="flex flex-wrap items-start justify-between gap-4 rounded-lg border border-line-subtle bg-surface-raised/50 p-4"><div className="min-w-0"><p className="text-sm font-semibold text-foreground">{companies.find((item) => item.id === employment.company_id)?.legal_name ?? "Empresa"} · {employment.employee_number}</p><p className="mt-1 text-sm text-muted">{[employment.position, employment.department].filter(Boolean).join(" · ") || "Puesto pendiente"}</p><p className="mt-2 text-xs text-muted">{employment.employment_relation_type || "Relación sin definir"} · {employment.contract_type || "Contrato sin definir"} · Inicio {employment.started_on}</p></div><div className="flex flex-wrap gap-2">{can("employments.write") ? <Button size="sm" icon={<Pencil className="h-4 w-4" />} onClick={() => { setEditing(employment); setEditDraft(employmentDraft(employment)); setError(null); }}>Editar contrato</Button> : null}{can("payroll.read") ? <Button size="sm" icon={<Banknote className="h-4 w-4" />} onClick={() => onCompensation(employment)}>Nómina e IMSS</Button> : null}</div></div>) : <p className="text-sm text-muted">Aún no hay empleos registrados para este trabajador.</p>}</div>
        {creating ? <div className="mt-5 border-t border-line-subtle pt-5"><h3 className="mb-4 text-sm font-semibold text-foreground">Nuevo empleo</h3><EmploymentFields draft={createDraft} onChange={setCreateDraft} companies={companies} /><div className="mt-4 flex flex-wrap justify-end gap-2"><Button variant="ghost" onClick={() => setCreating(false)}>Cancelar</Button><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void createEmployment()} loading={saving} disabled={!createDraft.company_id || !createDraft.employee_number.trim() || !createDraft.started_on}>Guardar empleo</Button></div></div> : null}
        {error && !editing ? <div className="mt-4"><ErrorState error={error} /></div> : null}
      </Card>

      <Card className="mt-5 p-5">
        <div className="flex items-center gap-3"><div className="rounded-lg bg-accent-soft p-2 text-accent"><CalendarDays className="h-5 w-5" aria-hidden /></div><div><h2 className="font-semibold text-foreground">Horarios por empleo</h2><p className="text-sm text-muted">Selecciona un horario y guarda su fecha de inicio. Cada empleo conserva un solo horario vigente.</p></div></div>
        <div className="mt-5 grid gap-3">{employments.length ? employments.map((employment) => <ScheduleEditor key={employment.id} employment={employment} companyName={companies.find((item) => item.id === employment.company_id)?.legal_name ?? "Empresa"} schedules={schedules} assignments={assignments[employment.id] ?? []} onChanged={onChanged} />) : <p className="text-sm text-muted">Registra primero un empleo para asignarle un horario.</p>}</div>
      </Card>

      <Modal open={editing !== null} onClose={() => { setEditing(null); setError(null); }} title="Editar contrato" description="Los cambios se guardan solamente en el empleo seleccionado." footer={<><Button variant="ghost" icon={<X className="h-4 w-4" />} onClick={() => { setEditing(null); setError(null); }}>Cancelar</Button><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void saveEmployment()} loading={saving} disabled={!editDraft.employee_number.trim() || !editDraft.started_on}>Guardar contrato</Button></>}>
        <EmploymentFields draft={editDraft} onChange={setEditDraft} companies={companies} editing />
        {error ? <div className="mt-4"><ErrorState error={error} /></div> : null}
      </Modal>
    </>
  );
}

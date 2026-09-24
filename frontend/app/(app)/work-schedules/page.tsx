"use client";

import { CalendarClock, Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import type { Company, WorkSchedule } from "@/types";

const DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function restDays(schedule: WorkSchedule): string {
  const worked = new Set(schedule.slots.map((slot) => slot.day_of_week));
  return DAY_NAMES.filter((_, day) => !worked.has(day)).join(", ") || "Sin descanso definido";
}

export default function WorkSchedulesPage() {
  const { notify } = useToast();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [schedules, setSchedules] = useState<WorkSchedule[]>([]);
  const [name, setName] = useState("");
  const [entry, setEntry] = useState("09:00");
  const [entryTolerance, setEntryTolerance] = useState("10");
  const [mealOut, setMealOut] = useState("14:00");
  const [mealIn, setMealIn] = useState("15:00");
  const [exit, setExit] = useState("18:00");
  const [includeMeal, setIncludeMeal] = useState(true);
  const [automaticExit, setAutomaticExit] = useState(false);
  const [daysOff, setDaysOff] = useState<number[]>([5, 6]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<WorkSchedule | null>(null);
  const [pendingDelete, setPendingDelete] = useState<WorkSchedule | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loadedCompanies = await api.companies();
      setCompanies(loadedCompanies);
      const selected = companyId || loadedCompanies[0]?.id || "";
      if (selected) {
        setCompanyId(selected);
        setSchedules(await api.workSchedules(selected));
      } else {
        setSchedules([]);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => void load(), [load]);

  function toggleDayOff(day: number) {
    setDaysOff((current) => {
      if (current.includes(day)) return current.filter((item) => item !== day);
      if (current.length === 2) return current;
      return [...current, day].sort();
    });
  }

  function slotsPayload() {
    return DAY_NAMES.flatMap((_, day) => {
      if (daysOff.includes(day)) return [];
      return [
        { day_of_week: day, kind: "entry", sequence: 1, expected_at: entry, tolerance_minutes: Number(entryTolerance) || 0, required: true },
        ...(includeMeal ? [
          { day_of_week: day, kind: "meal_out", sequence: 1, expected_at: mealOut, tolerance_minutes: 0, required: true },
          { day_of_week: day, kind: "meal_in", sequence: 1, expected_at: mealIn, tolerance_minutes: 0, required: true },
        ] : []),
        { day_of_week: day, kind: "exit", sequence: 1, expected_at: exit, tolerance_minutes: 0, required: true },
      ];
    });
  }

  function startEdit(schedule: WorkSchedule) {
    const worked = new Set(schedule.slots.map((slot) => slot.day_of_week));
    const sample = (kind: string, fallback: string) => schedule.slots.find((slot) => slot.kind === kind)?.expected_at.slice(0, 5) ?? fallback;
    setEditing(schedule);
    setName(schedule.name);
    setEntry(sample("entry", "09:00"));
    setEntryTolerance(String(schedule.slots.find((slot) => slot.kind === "entry")?.tolerance_minutes ?? 0));
    setMealOut(sample("meal_out", "14:00"));
    setMealIn(sample("meal_in", "15:00"));
    setExit(sample("exit", "18:00"));
    setIncludeMeal(schedule.slots.some((slot) => slot.kind === "meal_out"));
    setAutomaticExit(schedule.automatic_exit_enabled);
    setDaysOff(DAY_NAMES.map((_, day) => day).filter((day) => !worked.has(day)));
  }

  function resetForm() {
    setEditing(null);
    setName("");
    setEntryTolerance("10");
    setAutomaticExit(false);
    setDaysOff([5, 6]);
    setIncludeMeal(true);
  }

  function changeCompany(id: string) {
    resetForm();
    setError(null);
    setCompanyId(id);
  }

  async function save() {
    if (!companyId || !name.trim() || saving || daysOff.length < 1 || daysOff.length > 2) return;
    const payload = { name: name.trim(), timezone: "America/Mexico_City", automatic_exit_enabled: automaticExit, slots: slotsPayload() };
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        const updated = await api.updateWorkSchedule(editing.id, payload);
        notify("Horario actualizado", { message: updated.id === editing.id ? "Se actualizó el horario." : "Se creó una nueva versión para proteger el historial.", tone: "success" });
      } else {
        await api.createWorkSchedule({ company_id: companyId, ...payload });
        notify("Horario creado", { message: "Ya puede asignarse al empleo específico de cada persona.", tone: "success" });
      }
      resetForm();
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404 && editing) {
        resetForm();
        await load();
      }
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!pendingDelete || saving) return;
    setSaving(true);
    try {
      await api.deleteWorkSchedule(pendingDelete.id);
      notify("Horario eliminado", { tone: "success" });
      if (editing?.id === pendingDelete.id) resetForm();
      setPendingDelete(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  const columns: Column<WorkSchedule>[] = [
    { key: "name", header: "Horario", render: (row) => <span className="font-medium">{row.name}</span> },
    { key: "rest", header: "Descanso semanal", render: restDays },
    { key: "tolerance", header: "Tolerancia entrada", render: (row) => `${row.slots.find((slot) => slot.kind === "entry")?.tolerance_minutes ?? 0} min` },
    { key: "auto_exit", header: "Salida automática", render: (row) => row.automatic_exit_enabled ? "Activada" : "Manual" },
    { key: "slots", header: "Marcas esperadas", render: (row) => `${row.slots.length} definición(es)` },
    { key: "timezone", header: "Zona horaria", render: (row) => <span className="text-zinc-500">{row.timezone}</span> },
    { key: "actions", header: "", render: (row) => <span className="flex justify-end gap-1"><Button size="sm" variant="ghost" icon={<Pencil className="h-4 w-4" />} className="w-8 !px-0" aria-label="Editar horario" title="Editar horario" onClick={() => startEdit(row)} /><Button size="sm" variant="ghost" icon={<Trash2 className="h-4 w-4" />} className="w-8 !px-0 text-red-600" aria-label="Eliminar horario" title="Eliminar horario" onClick={() => setPendingDelete(row)} /></span> },
  ];

  return (
    <>
      <PageHeader title="Horarios" description="Cada horario define jornada, comida y uno o dos descansos no necesariamente consecutivos." crumbs={[{ label: "Horarios" }]} actions={editing ? <Button variant="ghost" icon={<X className="h-4 w-4" />} className="w-10 !px-0" aria-label="Cancelar edición" title="Cancelar edición" onClick={resetForm} /> : undefined} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5">
        <div className="flex flex-col gap-4">
          <div className="grid gap-3 lg:grid-cols-[16rem_minmax(0,1fr)]">
            <Field label="Empresa">{(id) => <Select id={id} value={companyId} onChange={(event) => changeCompany(event.target.value)} disabled={!companies.length}><option value="">Selecciona una empresa</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field>
            <Field label="Nombre del horario">{(id) => <Input id={id} value={name} onChange={(event) => setName(event.target.value)} placeholder="Operación martes a domingo" disabled={!companyId} />}</Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Field label="Entrada">{(id) => <Input id={id} type="time" value={entry} onChange={(event) => setEntry(event.target.value)} disabled={!companyId} />}</Field>
            <Field label="Tolerancia de entrada (minutos)">{(id) => <Input id={id} type="number" min="0" max="120" step="1" value={entryTolerance} onChange={(event) => setEntryTolerance(event.target.value)} disabled={!companyId} />}</Field>
            <Field label="Salida a comida">{(id) => <Input id={id} type="time" value={mealOut} onChange={(event) => setMealOut(event.target.value)} disabled={!companyId || !includeMeal} />}</Field>
            <Field label="Regreso de comida">{(id) => <Input id={id} type="time" value={mealIn} onChange={(event) => setMealIn(event.target.value)} disabled={!companyId || !includeMeal} />}</Field>
            <Field label="Salida">{(id) => <Input id={id} type="time" value={exit} onChange={(event) => setExit(event.target.value)} disabled={!companyId} />}</Field>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-zinc-700">Días de descanso semanal</p>
            <div className="flex flex-wrap gap-2">
              {DAY_NAMES.map((day, index) => <label key={day} className={`flex min-h-11 cursor-pointer items-center rounded-lg border px-3 text-sm transition-colors sm:min-h-0 sm:py-2 ${daysOff.includes(index) ? "border-accent-300 bg-accent-50 text-accent-800" : "border-line-soft text-zinc-600"}`}><input type="checkbox" className="sr-only" checked={daysOff.includes(index)} onChange={() => toggleDayOff(index)} />{day}</label>)}
            </div>
            <p className="mt-2 text-xs text-zinc-500">Selecciona uno o dos días. Pueden estar separados; no se permiten más de dos.</p>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-4">
              <label className="flex min-h-11 items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={includeMeal} onChange={(event) => setIncludeMeal(event.target.checked)} className="h-4 w-4 shrink-0 rounded border-line-soft text-accent-600 focus:ring-accent-500" />Incluir salida y regreso de comida</label>
              <label className="flex min-h-11 items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={automaticExit} onChange={(event) => setAutomaticExit(event.target.checked)} className="h-4 w-4 shrink-0 rounded border-line-soft text-accent-600 focus:ring-accent-500" />Generar salida automática al finalizar turno</label>
            </div>
            <p className="mt-2 text-xs text-zinc-500">La salida automática sólo cierra la jornada a la hora programada. Una checada real posterior se conserva como evidencia y se envía a Tiempo extra para revisión.</p>
            <Button variant="primary" icon={editing ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />} onClick={() => void save()} loading={saving} disabled={!companyId || !name.trim() || daysOff.length < 1}>{editing ? "Guardar cambios" : "Crear horario"}</Button>
          </div>
        </div>
      </Card>
      {loading ? <LoadingState rows={5} /> : <DataTable ariaLabel="Horarios" columns={columns} data={schedules} keyOf={(row) => row.id} renderCard={(row) => <div className="flex items-start justify-between gap-3"><div><p className="font-medium">{row.name}</p><p className="mt-1 text-xs text-zinc-500">Descanso: {restDays(row)} · {row.slots.length} marcas</p></div><span className="flex gap-1"><Button size="sm" variant="ghost" icon={<Pencil className="h-4 w-4" />} className="w-8 !px-0" aria-label="Editar horario" title="Editar horario" onClick={() => startEdit(row)} /><Button size="sm" variant="ghost" icon={<Trash2 className="h-4 w-4" />} className="w-8 !px-0 text-red-600" aria-label="Eliminar horario" title="Eliminar horario" onClick={() => setPendingDelete(row)} /></span></div>} empty={<EmptyState icon={<CalendarClock className="h-5 w-5" />} title="Sin horarios" description="Crea un horario para poder asignarlo a los empleos de esta empresa." />} />}
      <Modal open={pendingDelete !== null} onClose={() => setPendingDelete(null)} title="Eliminar horario" description="Esta acción no se puede deshacer." footer={<><Button variant="ghost" icon={<X className="h-4 w-4" />} className="w-10 !px-0" aria-label="Cancelar" title="Cancelar" onClick={() => setPendingDelete(null)} /><Button variant="danger" icon={<Trash2 className="h-4 w-4" />} className="w-10 !px-0" aria-label="Confirmar eliminación" title="Confirmar eliminación" onClick={() => void remove()} loading={saving} /></>}><p>Se eliminará <span className="font-medium">{pendingDelete?.name}</span>. Si tiene historial de asignaciones, el sistema la conservará para no alterar la auditoría.</p></Modal>
    </>
  );
}

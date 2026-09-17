"use client";

import { CalendarClock, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Company, WorkSchedule } from "@/types";

const DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

function restDays(schedule: WorkSchedule): string {
  const worked = new Set(schedule.slots.map((slot) => slot.day_of_week));
  return DAY_NAMES.filter((_, day) => !worked.has(day)).join(", ") || "Sin descanso definido";
}

const COLUMNS: Column<WorkSchedule>[] = [
  { key: "name", header: "Horario", render: (row) => <span className="font-medium">{row.name}</span> },
  { key: "rest", header: "Descanso semanal", render: restDays },
  { key: "slots", header: "Marcas esperadas", render: (row) => `${row.slots.length} definición(es)` },
  { key: "timezone", header: "Zona horaria", render: (row) => <span className="text-zinc-500">{row.timezone}</span> },
];

export default function WorkSchedulesPage() {
  const { notify } = useToast();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [schedules, setSchedules] = useState<WorkSchedule[]>([]);
  const [name, setName] = useState("");
  const [entry, setEntry] = useState("09:00");
  const [mealOut, setMealOut] = useState("14:00");
  const [mealIn, setMealIn] = useState("15:00");
  const [exit, setExit] = useState("18:00");
  const [includeMeal, setIncludeMeal] = useState(true);
  const [daysOff, setDaysOff] = useState<number[]>([5, 6]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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

  async function create() {
    if (!companyId || !name.trim() || saving || daysOff.length < 1 || daysOff.length > 2) return;
    const slots = DAY_NAMES.flatMap((_, day) => {
      if (daysOff.includes(day)) return [];
      return [
        { day_of_week: day, kind: "entry", sequence: 1, expected_at: entry, tolerance_minutes: 0, required: true },
        ...(includeMeal ? [
          { day_of_week: day, kind: "meal_out", sequence: 1, expected_at: mealOut, tolerance_minutes: 0, required: true },
          { day_of_week: day, kind: "meal_in", sequence: 1, expected_at: mealIn, tolerance_minutes: 0, required: true },
        ] : []),
        { day_of_week: day, kind: "exit", sequence: 1, expected_at: exit, tolerance_minutes: 0, required: true },
      ];
    });
    setSaving(true);
    try {
      await api.createWorkSchedule({ company_id: companyId, name: name.trim(), timezone: "America/Mexico_City", slots });
      setName("");
      notify("Horario creado", { message: "Ya puede asignarse al empleo específico de cada persona.", tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader title="Horarios" description="Cada horario define jornada, comida y uno o dos descansos no necesariamente consecutivos." crumbs={[{ label: "Horarios" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5">
        <div className="flex flex-col gap-4">
          <div className="grid gap-3 lg:grid-cols-[16rem_minmax(0,1fr)]">
            <Field label="Empresa">{(id) => <Select id={id} value={companyId} onChange={(event) => setCompanyId(event.target.value)} disabled={!companies.length}><option value="">Selecciona una empresa</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field>
            <Field label="Nombre del horario">{(id) => <Input id={id} value={name} onChange={(event) => setName(event.target.value)} placeholder="Operación martes a domingo" disabled={!companyId} />}</Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Field label="Entrada">{(id) => <Input id={id} type="time" value={entry} onChange={(event) => setEntry(event.target.value)} disabled={!companyId} />}</Field>
            <Field label="Salida a comida">{(id) => <Input id={id} type="time" value={mealOut} onChange={(event) => setMealOut(event.target.value)} disabled={!companyId || !includeMeal} />}</Field>
            <Field label="Regreso de comida">{(id) => <Input id={id} type="time" value={mealIn} onChange={(event) => setMealIn(event.target.value)} disabled={!companyId || !includeMeal} />}</Field>
            <Field label="Salida">{(id) => <Input id={id} type="time" value={exit} onChange={(event) => setExit(event.target.value)} disabled={!companyId} />}</Field>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-zinc-700">Días de descanso semanal</p>
            <div className="flex flex-wrap gap-2">
              {DAY_NAMES.map((day, index) => <label key={day} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm transition-colors ${daysOff.includes(index) ? "border-accent-300 bg-accent-50 text-accent-800" : "border-line-soft text-zinc-600"}`}><input type="checkbox" className="sr-only" checked={daysOff.includes(index)} onChange={() => toggleDayOff(index)} />{day}</label>)}
            </div>
            <p className="mt-2 text-xs text-zinc-500">Selecciona uno o dos días. Pueden estar separados; no se permiten más de dos.</p>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={includeMeal} onChange={(event) => setIncludeMeal(event.target.checked)} className="h-4 w-4 rounded border-line-soft text-accent-600 focus:ring-accent-500" />Incluir salida y regreso de comida</label>
            <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void create()} loading={saving} disabled={!companyId || !name.trim() || daysOff.length < 1}>Crear horario</Button>
          </div>
        </div>
      </Card>
      {loading ? <LoadingState rows={5} /> : <DataTable ariaLabel="Horarios" columns={COLUMNS} data={schedules} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{row.name}</p><p className="mt-1 text-xs text-zinc-500">Descanso: {restDays(row)} · {row.slots.length} marcas</p></div>} empty={<EmptyState icon={<CalendarClock className="h-5 w-5" />} title="Sin horarios" description="Crea un horario para poder asignarlo a los empleos de esta empresa." />} />}
    </>
  );
}

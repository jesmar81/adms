"use client";

import { CalendarPlus, Landmark, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Company, Holiday } from "@/types";

const KIND_LABEL: Record<Holiday["kind"], string> = {
  statutory: "LFT",
  company: "Empresa",
  electoral: "Electoral",
};

const COLUMNS: Column<Holiday>[] = [
  { key: "date", header: "Fecha", render: (row) => row.holiday_date },
  { key: "name", header: "Motivo", render: (row) => <span className="font-medium">{row.name}</span> },
  { key: "kind", header: "Tipo", render: (row) => <Badge tone={row.kind === "statutory" ? "sky" : "zinc"}>{KIND_LABEL[row.kind]}</Badge> },
  { key: "paid", header: "Descanso pagado", render: (row) => row.is_paid_rest ? "Sí" : "No" },
  { key: "source", header: "Origen", render: (row) => row.generated ? "Generado" : "Capturado por RRHH" },
];

export default function HolidaysPage() {
  const { notify } = useToast();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [holidayDate, setHolidayDate] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"company" | "electoral">("company");
  const [paidRest, setPaidRest] = useState(true);
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
        setHolidays(await api.holidays(selected, year));
      } else {
        setHolidays([]);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [companyId, year]);

  useEffect(() => void load(), [load]);

  async function generate() {
    if (!companyId || saving) return;
    setSaving(true);
    try {
      const result = await api.generateHolidays(companyId, year);
      notify("Calendario legal actualizado", { message: `${result.created} día(s) creado(s); ${result.existing} ya existían.`, tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function create() {
    if (!companyId || !holidayDate || !name.trim() || saving) return;
    setSaving(true);
    try {
      await api.createHoliday({ company_id: companyId, holiday_date: holidayDate, name: name.trim(), kind, is_paid_rest: paidRest });
      setHolidayDate("");
      setName("");
      notify("Día inhábil agregado", { tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader title="Feriados" description="Calendario por empresa: días obligatorios de la LFT y días internos que RRHH determine." crumbs={[{ label: "Feriados" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_9rem_auto] lg:items-end">
          <Field label="Empresa">{(id) => <Select id={id} value={companyId} onChange={(event) => setCompanyId(event.target.value)} disabled={!companies.length}><option value="">Selecciona una empresa</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field>
          <Field label="Año">{(id) => <Input id={id} type="number" min="2000" max="2200" value={year} onChange={(event) => setYear(Number(event.target.value))} />}</Field>
          <Button variant="secondary" icon={<RefreshCw className="h-4 w-4" />} onClick={() => void generate()} loading={saving} disabled={!companyId}>Generar o reparar legales</Button>
        </div>
        <div className="mt-4 rounded-xl border border-sky-100 bg-sky-50 px-4 py-3 text-sm text-sky-900"><div className="flex gap-2"><Landmark className="mt-0.5 h-4 w-4 shrink-0" /><p>La generación usa las reglas anuales conocidas del artículo 74 de la LFT. Las jornadas electorales se registran manualmente, porque la fecha depende de cada proceso electoral.</p></div></div>
      </Card>
      <Card className="mb-5 p-5">
        <div className="grid gap-3 lg:grid-cols-[10rem_minmax(0,1fr)_11rem_auto] lg:items-end">
          <Field label="Fecha">{(id) => <Input id={id} type="date" value={holidayDate} onChange={(event) => setHolidayDate(event.target.value)} disabled={!companyId} />}</Field>
          <Field label="Motivo">{(id) => <Input id={id} value={name} onChange={(event) => setName(event.target.value)} placeholder="Aniversario de la empresa" disabled={!companyId} />}</Field>
          <Field label="Tipo">{(id) => <Select id={id} value={kind} onChange={(event) => setKind(event.target.value as "company" | "electoral")} disabled={!companyId}><option value="company">Día interno</option><option value="electoral">Jornada electoral</option></Select>}</Field>
          <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void create()} loading={saving} disabled={!companyId || !holidayDate || !name.trim()}>Agregar</Button>
        </div>
        <label className="mt-3 flex min-h-11 items-center gap-2 text-sm text-zinc-700"><input type="checkbox" checked={paidRest} onChange={(event) => setPaidRest(event.target.checked)} className="h-4 w-4 shrink-0 rounded border-line-soft text-accent-600 focus:ring-accent-500" />Es día de descanso pagado</label>
      </Card>
      {loading ? <LoadingState rows={6} /> : <DataTable ariaLabel="Feriados de la empresa" columns={COLUMNS} data={holidays} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{row.holiday_date} · {row.name}</p><p className="mt-1 text-xs text-zinc-500">{KIND_LABEL[row.kind]} · {row.is_paid_rest ? "Descanso pagado" : "No pagado"}</p></div>} empty={<EmptyState icon={<CalendarPlus className="h-5 w-5" />} title="Sin feriados en este año" description="Genera primero los días legales o registra un día interno de la empresa." />} />}
    </>
  );
}

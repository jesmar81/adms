"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CalendarDays, Clock3, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AttendanceRow, Employment, Person } from "@/types";

const ATTENDANCE_COLUMNS: Column<AttendanceRow>[] = [
  { key: "recorded_at", header: "Fecha y hora", render: (row) => formatDateTime(row.recorded_at) },
  { key: "pin", header: "PIN", render: (row) => <span className="font-mono">{row.device_user_pin}</span> },
  { key: "status", header: "Estado", render: (row) => row.status },
  { key: "verify", header: "Validación", render: (row) => row.verify_mode },
  { key: "work", header: "Código", render: (row) => row.work_code ?? "—" },
];

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function DisplayEmployment({ row }: { row: Employment }) {
  return (
    <div className="rounded-xl border border-line-subtle bg-zinc-50/60 px-4 py-3">
      <p className="font-medium text-zinc-800">{row.employee_number}</p>
      <p className="mt-1 text-sm text-zinc-600">{[row.position, row.department].filter(Boolean).join(" · ") || "Puesto pendiente"}</p>
      <p className="mt-1 text-xs text-zinc-500">Vigente desde {row.started_on}</p>
    </div>
  );
}

function PersonDetail({ id }: { id: string }) {
  const today = new Date();
  const monthAgo = new Date(today);
  monthAgo.setDate(monthAgo.getDate() - 30);
  const [person, setPerson] = useState<Person | null>(null);
  const [employments, setEmployments] = useState<Employment[]>([]);
  const [marks, setMarks] = useState<AttendanceRow[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState(isoDate(monthAgo));
  const [dateTo, setDateTo] = useState(isoDate(today));
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedPerson, loadedEmployments, page] = await Promise.all([
        api.person(id),
        api.employments({ person_id: id }),
        api.personAttendance(id, { date_from: new Date(`${dateFrom}T00:00:00`).toISOString(), date_to: new Date(`${dateTo}T23:59:59`).toISOString() }),
      ]);
      setPerson(loadedPerson);
      setEmployments(loadedEmployments);
      setMarks(page.items);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, id]);

  useEffect(() => void load(), [load]);

  async function loadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await api.personAttendance(id, {
        date_from: new Date(`${dateFrom}T00:00:00`).toISOString(),
        date_to: new Date(`${dateTo}T23:59:59`).toISOString(),
        cursor: nextCursor,
      });
      setMarks((current) => [...current, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      setError(err);
    } finally {
      setLoadingMore(false);
    }
  }

  function showCurrentYear() {
    setDateFrom(`${today.getFullYear()}-01-01`);
    setDateTo(isoDate(today));
  }

  const fullName = person ? [person.first_name, person.last_name, person.second_last_name].filter(Boolean).join(" ") : "Expediente";
  return (
    <>
      <PageHeader title={fullName} description="Expediente de identidad, empleos y checadas capturadas desde los relojes." crumbs={[{ label: "Personas", href: "/people" }, { label: "Expediente" }]} actions={<Link href="/people"><Button variant="secondary" icon={<ArrowLeft className="h-4 w-4" />}>Volver</Button></Link>} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      {loading ? <LoadingState rows={7} /> : <>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <Card className="p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><UserRound className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Datos de contacto</p><p className="text-sm text-zinc-500">Identidad común del grupo</p></div></div><dl className="mt-5 grid gap-3 text-sm"><div><dt className="text-zinc-500">Correo</dt><dd className="mt-0.5 text-zinc-800">{person?.email ?? "No registrado"}</dd></div><div><dt className="text-zinc-500">Teléfono</dt><dd className="mt-0.5 text-zinc-800">{person?.phone ?? "No registrado"}</dd></div><div><dt className="text-zinc-500">Nombre preferido</dt><dd className="mt-0.5 text-zinc-800">{person?.preferred_name ?? "No registrado"}</dd></div></dl></Card>
          <Card className="p-5"><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><CalendarDays className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Empleos</p><p className="text-sm text-zinc-500">Una misma persona puede trabajar en varias empresas del grupo.</p></div></div><div className="mt-5 grid gap-3 sm:grid-cols-2">{employments.length ? employments.map((employment) => <DisplayEmployment key={employment.id} row={employment} />) : <p className="text-sm text-zinc-500">Aún no hay empleos asignados.</p>}</div></Card>
        </div>
        <Card className="mt-5 p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div><div className="flex items-center gap-3"><div className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><Clock3 className="h-5 w-5" /></div><div><p className="font-semibold text-zinc-800">Checadas capturadas</p><p className="text-sm text-zinc-500">Por defecto muestra el último mes; el año se consulta en bloques de 100.</p></div></div></div><div className="flex flex-wrap items-end gap-2"><div className="w-36"><Field label="Desde">{(fieldId) => <Input id={fieldId} type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />}</Field></div><div className="w-36"><Field label="Hasta">{(fieldId) => <Input id={fieldId} type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />}</Field></div><Button variant="secondary" onClick={showCurrentYear}>Año actual</Button></div></div></Card>
        <div className="mt-4"><DataTable ariaLabel="Checadas de la persona" columns={ATTENDANCE_COLUMNS} data={marks} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{formatDateTime(row.recorded_at)}</p><p className="mt-1 text-xs text-zinc-500">PIN {row.device_user_pin} · Estado {row.status} · Validación {row.verify_mode}</p></div>} empty={<EmptyState icon={<Clock3 className="h-5 w-5" />} title="Sin checadas en este periodo" description="Las checadas aparecerán cuando el PIN del reloj esté vinculado a esta persona." />} /></div>
        {nextCursor ? <div className="mt-5 flex justify-center"><Button variant="secondary" onClick={() => void loadMore()} loading={loadingMore}>Cargar las siguientes 100</Button></div> : null}
      </>}
    </>
  );
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <PersonDetail id={id} />;
}

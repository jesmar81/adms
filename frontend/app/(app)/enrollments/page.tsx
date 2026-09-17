"use client";

import { Fingerprint, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Device, Employment, EnrollmentRequest } from "@/types";

const METHODS = ["face", "fingerprint", "palm", "card"] as const;

const COLUMNS: Column<EnrollmentRequest>[] = [
  { key: "employment", header: "Empleo", render: (row) => <span className="font-mono text-[13px]">{row.employment_id}</span> },
  { key: "device", header: "Reloj", render: (row) => <span className="font-mono text-[13px]">{row.device_id}</span> },
  { key: "methods", header: "Métodos", render: (row) => row.methods.join(", ") },
  { key: "status", header: "Estado", render: (row) => <span className="capitalize">{row.status.replaceAll("_", " ")}</span> },
];

export default function EnrollmentsPage() {
  const { notify } = useToast();
  const [requests, setRequests] = useState<EnrollmentRequest[]>([]);
  const [employments, setEmployments] = useState<Employment[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [employmentId, setEmploymentId] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [methods, setMethods] = useState<string[]>(["face"]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const employmentById = useMemo(() => new Map(employments.map((employment) => [employment.id, employment])), [employments]);
  const deviceById = useMemo(() => new Map(devices.map((device) => [device.id, device])), [devices]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedRequests, loadedEmployments, loadedDevices] = await Promise.all([api.enrollmentRequests(), api.employments(), api.devices()]);
      setRequests(loadedRequests);
      setEmployments(loadedEmployments);
      setDevices(loadedDevices);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => void load(), [load]);

  function toggleMethod(method: string) {
    setMethods((current) => current.includes(method) ? current.filter((value) => value !== method) : [...current, method]);
  }

  async function create() {
    if (!employmentId || !deviceId || methods.length === 0 || saving) return;
    setSaving(true);
    try {
      await api.createEnrollmentRequest({ employment_id: employmentId, device_id: deviceId, methods });
      setMethods(["face"]);
      notify("Solicitud creada", { message: "Pendiente de aprobación y enrolamiento supervisado en el reloj.", tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  const requestColumns: Column<EnrollmentRequest>[] = COLUMNS.map((column) => ({ ...column, render: (row) => {
    if (column.key === "employment") return employmentById.get(row.employment_id)?.employee_number ?? row.employment_id;
    if (column.key === "device") return deviceById.get(row.device_id)?.name ?? deviceById.get(row.device_id)?.serial_number ?? row.device_id;
    return column.render(row);
  }}));
  return (
    <>
      <PageHeader title="Enrolamientos" description="Solicitud, aprobación y registro presencial de credenciales biométricas; nunca se almacenan plantillas en esta interfaz." crumbs={[{ label: "Enrolamientos" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5"><div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end"><Field label="Empleo">{(id) => <Select id={id} value={employmentId} onChange={(event) => setEmploymentId(event.target.value)}><option value="">Selecciona un empleo</option>{employments.map((employment) => <option key={employment.id} value={employment.id}>{employment.employee_number} · {employment.position ?? "Sin puesto"}</option>)}</Select>}</Field><Field label="Reloj">{(id) => <Select id={id} value={deviceId} onChange={(event) => setDeviceId(event.target.value)}><option value="">Selecciona un reloj</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.name ?? device.serial_number}</option>)}</Select>}</Field><div><p className="mb-2 text-sm font-medium text-zinc-700">Métodos autorizados</p><div className="flex flex-wrap gap-3">{METHODS.map((method) => <label key={method} className="flex items-center gap-1.5 text-sm capitalize text-zinc-700"><input type="checkbox" checked={methods.includes(method)} onChange={() => toggleMethod(method)} className="h-4 w-4 rounded border-line-soft text-accent-600 focus:ring-accent-500" />{method}</label>)}</div></div><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void create()} loading={saving} disabled={!employmentId || !deviceId || !methods.length}>Solicitar</Button></div></Card>
      {loading ? <LoadingState rows={5} /> : <DataTable ariaLabel="Solicitudes de enrolamiento" columns={requestColumns} data={requests} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{employmentById.get(row.employment_id)?.employee_number ?? "Empleo"}</p><p className="mt-1 text-xs text-zinc-500">{row.methods.join(", ")} · {row.status.replaceAll("_", " ")}</p></div>} empty={<EmptyState icon={<Fingerprint className="h-5 w-5" />} title="Sin solicitudes" description="Crea una solicitud y realiza el enrolamiento presencial en el equipo autorizado." />} />}
    </>
  );
}

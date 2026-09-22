"use client";

import {
  CheckCircle2,
  CircleArrowRight,
  Fingerprint,
  Hand,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Can } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Device, Employment, EnrollmentRequest } from "@/types";

const METHODS = ["face", "fingerprint", "palm", "card"] as const;

const FINGERS = [
  { id: "left_little", hand: "Izquierda", label: "Meñique", short: "I5" },
  { id: "left_ring", hand: "Izquierda", label: "Anular", short: "I4" },
  { id: "left_middle", hand: "Izquierda", label: "Medio", short: "I3" },
  { id: "left_index", hand: "Izquierda", label: "Índice", short: "I2" },
  { id: "left_thumb", hand: "Izquierda", label: "Pulgar", short: "I1" },
  { id: "right_thumb", hand: "Derecha", label: "Pulgar", short: "D1" },
  { id: "right_index", hand: "Derecha", label: "Índice", short: "D2" },
  { id: "right_middle", hand: "Derecha", label: "Medio", short: "D3" },
  { id: "right_ring", hand: "Derecha", label: "Anular", short: "D4" },
  { id: "right_little", hand: "Derecha", label: "Meñique", short: "D5" },
] as const;

const FINGER_LABELS = Object.fromEntries(FINGERS.map((finger) => [finger.id, `${finger.hand}: ${finger.label}`]));

const COLUMNS: Column<EnrollmentRequest>[] = [
  { key: "employment", header: "Empleo", render: (row) => <span className="font-mono text-[13px]">{row.employment_id}</span> },
  { key: "device", header: "Reloj", render: (row) => <span className="font-mono text-[13px]">{row.device_id}</span> },
  {
    key: "methods",
    header: "Credenciales",
    render: (row) => (
      <div>
        <p>{row.methods.join(", ")}</p>
        {row.fingerprint_positions.length ? (
          <p className="mt-1 text-xs text-zinc-500">
            {row.fingerprint_positions.map((finger) => FINGER_LABELS[finger] ?? finger).join(" · ")}
          </p>
        ) : null}
      </div>
    ),
  },
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
  const [fingers, setFingers] = useState<string[]>([]);
  const [consentObtained, setConsentObtained] = useState(false);
  const [consentReference, setConsentReference] = useState("");
  const [verifyingRow, setVerifyingRow] = useState<EnrollmentRequest | null>(null);
  const [verificationReference, setVerificationReference] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState("");
  const employmentById = useMemo(
    () => new Map(employments.map((employment) => [employment.id, employment])),
    [employments],
  );
  const deviceById = useMemo(
    () => new Map(devices.map((device) => [device.id, device])),
    [devices],
  );
  const hasFingerprints = methods.includes("fingerprint");
  const hasBiometrics = methods.some((method) => ["face", "fingerprint", "palm"].includes(method));

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedRequests, loadedEmployments, loadedDevices] = await Promise.all([
        api.enrollmentRequests(),
        api.employments(),
        api.devices(),
      ]);
      setRequests(loadedRequests);
      setEmployments(loadedEmployments);
      setDevices(loadedDevices);
    } catch (cause) {
      setError(cause);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function toggleMethod(method: string) {
    setMethods((current) => {
      const next = current.includes(method)
        ? current.filter((value) => value !== method)
        : [...current, method];
      if (method === "fingerprint" && !next.includes("fingerprint")) setFingers([]);
      return next;
    });
  }

  function toggleFinger(finger: string) {
    setMethods((current) => (current.includes("fingerprint") ? current : [...current, "fingerprint"]));
    setFingers((current) =>
      current.includes(finger) ? current.filter((value) => value !== finger) : [...current, finger],
    );
  }

  async function create() {
    if (!employmentId || !deviceId || methods.length === 0 || saving || (hasFingerprints && !fingers.length) || (hasBiometrics && (!consentObtained || consentReference.trim().length < 3))) return;
    setSaving(true);
    try {
      await api.createEnrollmentRequest({
        employment_id: employmentId,
        device_id: deviceId,
        methods,
        fingerprint_positions: fingers,
        consent_obtained: consentObtained,
        consent_reference: consentReference.trim() || null,
      });
      setMethods(["face"]);
      setFingers([]);
      setConsentObtained(false);
      setConsentReference("");
      notify("Solicitud creada", {
        message: "Las posiciones de huella seleccionadas quedaron registradas para el enrolamiento presencial.",
        tone: "success",
      });
      await load();
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  }

  async function advance(row: EnrollmentRequest, reference?: string) {
    const nextByStatus: Record<string, string> = {
      requested: "identity_verified",
      identity_verified: "approved",
      approved: "awaiting_device_enrollment",
      awaiting_device_enrollment: "verification_pending",
      verification_pending: "completed",
    };
    const next = nextByStatus[row.status];
    if (!next || updatingId) return;
    setUpdatingId(row.id);
    try {
      await api.updateEnrollmentRequest(row.id, { status: next, verification_reference: reference || null });
      notify("Estado actualizado", { message: "La solicitud avanzó de forma controlada.", tone: "success" });
      await load();
      if (next === "identity_verified") {
        setVerifyingRow(null);
        setVerificationReference("");
      }
    } catch (cause) {
      setError(cause);
    } finally {
      setUpdatingId("");
    }
  }

  const requestColumns: Column<EnrollmentRequest>[] = COLUMNS.map((column) => ({
    ...column,
    render: (row) => {
      if (column.key === "employment") return employmentById.get(row.employment_id)?.employee_number ?? row.employment_id;
      if (column.key === "device") return deviceById.get(row.device_id)?.name ?? deviceById.get(row.device_id)?.serial_number ?? row.device_id;
      return column.render(row);
    },
  }));
  requestColumns.push({
    key: "actions",
    header: "",
    render: (row) => {
      const labels: Record<string, string> = { requested: "Verificar identidad", identity_verified: "Aprobar", approved: "Enviar a enrolar", awaiting_device_enrollment: "Verificar credencial", verification_pending: "Completar" };
      const label = labels[row.status];
      if (!label) return null;
      return <Can permission="enrollments.approve"><Button size="sm" icon={row.status === "verification_pending" ? <CheckCircle2 className="h-4 w-4" /> : <CircleArrowRight className="h-4 w-4" />} onClick={() => row.status === "requested" ? setVerifyingRow(row) : void advance(row)} loading={updatingId === row.id}>{label}</Button></Can>;
    },
  });

  return (
    <>
      <PageHeader title="Enrolamientos" description="Solicitudes profesionales de credenciales; las plantillas biométricas nunca salen del reloj." crumbs={[{ label: "Enrolamientos" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 overflow-hidden">
        <div className="border-b border-line-subtle bg-zinc-50/80 px-5 py-4"><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-50 text-accent-700"><ShieldCheck className="h-5 w-5" /></span><div><h2 className="font-semibold">Nueva solicitud de enrolamiento</h2><p className="text-sm text-zinc-500">Selecciona la credencial y, para huellas, las posiciones exactas a registrar.</p></div></div></div>
        <div className="p-5"><div className="grid gap-4 lg:grid-cols-2"><Field label="Empleo">{(id) => <Select id={id} value={employmentId} onChange={(event) => setEmploymentId(event.target.value)}><option value="">Selecciona un empleo</option>{employments.map((employment) => <option key={employment.id} value={employment.id}>{employment.employee_number} · {employment.position ?? "Sin puesto"}</option>)}</Select>}</Field><Field label="Reloj autorizado">{(id) => <Select id={id} value={deviceId} onChange={(event) => setDeviceId(event.target.value)}><option value="">Selecciona un reloj</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.name ?? device.serial_number}</option>)}</Select>}</Field></div>
          <div className="mt-6"><p className="text-sm font-medium text-zinc-800">Credenciales a enrolar</p><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{METHODS.map((method) => { const active = methods.includes(method); const Icon = method === "fingerprint" ? Fingerprint : Hand; return <button type="button" key={method} onClick={() => toggleMethod(method)} aria-pressed={active} className={`rounded-2xl border p-4 text-left transition-colors ${active ? "border-accent bg-accent-50" : "border-line-subtle bg-white hover:bg-zinc-50"}`}><Icon className={`h-5 w-5 ${active ? "text-accent-700" : "text-zinc-400"}`} /><p className="mt-3 font-medium capitalize">{method === "face" ? "Rostro" : method === "fingerprint" ? "Huellas" : method === "palm" ? "Palma" : "Tarjeta"}</p><p className="mt-1 text-xs text-zinc-500">{active ? "Incluido en la solicitud" : "No seleccionado"}</p></button>; })}</div></div>
          {hasFingerprints ? <FingerprintSelector selected={fingers} onToggle={toggleFinger} /> : null}
          {hasBiometrics ? <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50/70 p-4"><label className="flex items-start gap-3 text-sm"><input type="checkbox" className="mt-1" checked={consentObtained} onChange={(event) => setConsentObtained(event.target.checked)} /><span><span className="block font-medium text-amber-900">Consentimiento biométrico documentado</span><span className="mt-0.5 block text-xs text-amber-800">Confirma que RR. HH. conserva el documento o folio aplicable.</span></span></label><div className="mt-3"><Field label="Folio o referencia del consentimiento">{(id) => <Input id={id} value={consentReference} onChange={(event) => setConsentReference(event.target.value)} placeholder="Ej. CONS-2026-0042" />}</Field></div></div> : null}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line-subtle pt-5"><p className="text-xs text-zinc-500">La solicitud conserva posiciones y evidencia de consentimiento; las plantillas se quedan exclusivamente en el dispositivo.</p><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void create()} loading={saving} disabled={!employmentId || !deviceId || !methods.length || (hasFingerprints && !fingers.length) || (hasBiometrics && (!consentObtained || consentReference.trim().length < 3))}>Crear solicitud</Button></div>
        </div>
      </Card>
      {loading ? <LoadingState rows={5} /> : <DataTable ariaLabel="Solicitudes de enrolamiento" columns={requestColumns} data={requests} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{employmentById.get(row.employment_id)?.employee_number ?? "Empleo"}</p><p className="mt-1 text-xs text-zinc-500">{row.methods.join(", ")} · {row.status.replaceAll("_", " ")}</p>{row.fingerprint_positions.length ? <p className="mt-1 text-xs text-zinc-500">{row.fingerprint_positions.map((finger) => FINGER_LABELS[finger] ?? finger).join(" · ")}</p> : null}</div>} empty={<EmptyState icon={<Fingerprint className="h-5 w-5" />} title="Sin solicitudes" description="Crea una solicitud y realiza el enrolamiento presencial en el equipo autorizado." />} />}
      <Modal open={verifyingRow !== null} onClose={() => setVerifyingRow(null)} title="Verificar identidad presencial" description="Registra el documento o control interno utilizado; no captures imágenes del documento aquí." footer={<><Button variant="ghost" onClick={() => setVerifyingRow(null)}>Cancelar</Button><Button variant="primary" icon={<ShieldCheck className="h-4 w-4" />} onClick={() => verifyingRow ? void advance(verifyingRow, verificationReference.trim()) : undefined} loading={Boolean(verifyingRow && updatingId === verifyingRow.id)} disabled={verificationReference.trim().length < 3}>Confirmar identidad</Button></>}><Field label="Referencia de verificación">{(id) => <Input id={id} value={verificationReference} onChange={(event) => setVerificationReference(event.target.value)} placeholder="Ej. INE cotejada / control 1842" />}</Field><p className="mt-3 text-xs text-zinc-500">La persona que creó la solicitud no puede verificarla ni aprobarla.</p></Modal>
    </>
  );
}

function FingerprintSelector({ selected, onToggle }: { selected: string[]; onToggle: (finger: string) => void }) {
  const groups = [FINGERS.slice(0, 5), FINGERS.slice(5)];
  return <section className="mt-6 rounded-2xl border border-line-subtle bg-zinc-50/70 p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-zinc-900">Posiciones de huellas</h3><p className="mt-1 text-sm text-zinc-500">Selecciona uno o varios dedos. Puedes corregir esta elección antes de completar el enrolamiento.</p></div><span className="rounded-full bg-white px-3 py-1 text-sm font-medium text-accent-700 shadow-sm">{selected.length} de 10 seleccionadas</span></div><div className="mt-5 grid gap-5 lg:grid-cols-2">{groups.map((hand) => <div key={hand[0].hand} className="rounded-2xl border border-line-subtle bg-white p-4"><div className="flex items-center gap-2 text-sm font-semibold text-zinc-800"><Hand className="h-4 w-4 text-accent-600" /> Mano {hand[0].hand.toLowerCase()}</div><div className="mt-4 grid grid-cols-5 gap-2">{hand.map((finger) => { const active = selected.includes(finger.id); return <button type="button" key={finger.id} aria-label={`${finger.hand} ${finger.label}`} aria-pressed={active} onClick={() => onToggle(finger.id)} className={`group flex min-h-24 flex-col items-center justify-center rounded-xl border px-1 text-center transition-all ${active ? "border-accent bg-accent text-white shadow-sm" : "border-line-subtle bg-zinc-50 text-zinc-600 hover:border-accent/50 hover:bg-accent-50"}`}><Fingerprint className={`h-6 w-6 ${active ? "text-white" : "text-zinc-400 group-hover:text-accent-600"}`} /><span className="mt-2 text-xs font-semibold">{finger.short}</span><span className="mt-0.5 text-[10px] leading-tight">{finger.label}</span></button>; })}</div></div>)}</div></section>;
}

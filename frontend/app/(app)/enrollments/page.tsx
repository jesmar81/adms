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
import { Can, useAuth } from "@/lib/auth";
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
import type { Device, EnrollmentCandidate, EnrollmentRequest } from "@/types";

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
  { key: "worker", header: "Trabajador", render: (row) => <div><p className="font-medium">{row.worker_name}</p><p className="text-xs text-muted">{row.employee_number} · {row.company_name}{row.site_name ? ` · ${row.site_name}` : ""}</p></div> },
  { key: "device", header: "Reloj", render: (row) => <span className="font-mono text-[13px]">{row.device_id}</span> },
  {
    key: "methods",
    header: "Credenciales",
    render: (row) => (
      <div>
        <p>{row.methods.join(", ")}</p>
        {row.fingerprint_positions.length ? (
            <p className="mt-1 text-xs text-muted">
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
  const { can } = useAuth();
  const [requests, setRequests] = useState<EnrollmentRequest[]>([]);
  const [candidates, setCandidates] = useState<EnrollmentCandidate[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [employmentId, setEmploymentId] = useState("");
  const [personId, setPersonId] = useState("");
  const [workerSearch, setWorkerSearch] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [methods, setMethods] = useState<string[]>(["face"]);
  const [fingers, setFingers] = useState<string[]>([]);
  const [verifyingRow, setVerifyingRow] = useState<EnrollmentRequest | null>(null);
  const [verificationReference, setVerificationReference] = useState("");
  const [actionError, setActionError] = useState<unknown>(null);
  const [requestsError, setRequestsError] = useState<unknown>(null);
  const [devicesError, setDevicesError] = useState<unknown>(null);
  const [candidatesError, setCandidatesError] = useState<unknown>(null);
  const [requestsLoading, setRequestsLoading] = useState(true);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [candidatesLoading, setCandidatesLoading] = useState(false);
  const [candidateRetry, setCandidateRetry] = useState(0);
  const [deviceRetry, setDeviceRetry] = useState(0);
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState("");
  const deviceById = useMemo(
    () => new Map(devices.map((device) => [device.id, device])),
    [devices],
  );
  const hasFingerprints = methods.includes("fingerprint");
  const filteredCandidates = useMemo(() => {
    const search = workerSearch.trim().toLocaleLowerCase();
    if (!search) return candidates;
    return candidates.filter((candidate) => [
      candidate.worker_name,
      candidate.employee_number,
      candidate.company_name,
      candidate.site_name ?? "",
      candidate.position ?? "",
    ].join(" ").toLocaleLowerCase().includes(search));
  }, [candidates, workerSearch]);

  const loadRequests = useCallback(async () => {
    setRequestsLoading(true);
    setRequestsError(null);
    try {
      setRequests(await api.enrollmentRequests());
    } catch (cause) {
      setRequestsError(cause);
    } finally {
      setRequestsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  useEffect(() => {
    let current = true;
    setDevicesLoading(true);
    setDevicesError(null);
    void api.devices().then((loadedDevices) => {
      if (current) setDevices(loadedDevices);
    }).catch((cause) => {
      if (current) setDevicesError(cause);
    }).finally(() => {
      if (current) setDevicesLoading(false);
    });
    return () => { current = false; };
  }, [deviceRetry]);

  useEffect(() => {
    let current = true;
    setCandidates([]);
    setCandidatesError(null);
    setEmploymentId("");
    setPersonId("");
    if (!deviceId || !can("enrollments.write")) {
      setCandidatesLoading(false);
      return () => { current = false; };
    }
    setCandidatesLoading(true);
    void api.enrollmentCandidates(deviceId).then((loadedCandidates) => {
      if (current) setCandidates(loadedCandidates);
    }).catch((cause) => {
      if (current) setCandidatesError(cause);
    }).finally(() => {
      if (current) setCandidatesLoading(false);
    });
    return () => { current = false; };
  }, [deviceId, can, candidateRetry]);

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
    if (!personId || !employmentId || !deviceId || methods.length === 0 || saving || (hasFingerprints && !fingers.length)) return;
    setSaving(true);
    setActionError(null);
    try {
      await api.createEnrollmentRequest({
        person_id: personId,
        employment_id: employmentId,
        device_id: deviceId,
        methods,
        fingerprint_positions: fingers,
      });
      setEmploymentId("");
      setPersonId("");
      setWorkerSearch("");
      setMethods(["face"]);
      setFingers([]);
      notify("Solicitud creada", {
        message: "La solicitud de enrolamiento quedó registrada.",
        tone: "success",
      });
      await loadRequests();
    } catch (cause) {
      setActionError(cause);
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
    setActionError(null);
    try {
      await api.updateEnrollmentRequest(row.id, { status: next, verification_reference: reference || null });
      notify("Estado actualizado", { message: "La solicitud avanzó de forma controlada.", tone: "success" });
      await loadRequests();
      if (next === "identity_verified") {
        setVerifyingRow(null);
        setVerificationReference("");
      }
    } catch (cause) {
      setActionError(cause);
    } finally {
      setUpdatingId("");
    }
  }

  const requestColumns: Column<EnrollmentRequest>[] = COLUMNS.map((column) => ({
    ...column,
    render: (row) => {
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
      {actionError ? <div className="mb-4"><ErrorState error={actionError} /></div> : null}
      {can("enrollments.write") ? <Card className="mb-5 overflow-hidden">
        <div className="border-b border-line-subtle bg-surface-raised/80 px-5 py-4"><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent"><ShieldCheck className="h-5 w-5" /></span><div><h2 className="font-semibold">Nueva solicitud de enrolamiento</h2><p className="text-sm text-muted">Selecciona al trabajador por su nombre. Se validará su empleo vigente con la empresa del reloj.</p></div></div></div>
        <div className="p-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Reloj autorizado">{(id) => <Select id={id} value={deviceId} onChange={(event) => { setDeviceId(event.target.value); setEmploymentId(""); setPersonId(""); setWorkerSearch(""); }} disabled={devicesLoading || Boolean(devicesError)}><option value="">{devicesLoading ? "Cargando relojes…" : devices.length ? "Selecciona un reloj" : "Sin relojes disponibles"}</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.name ?? device.serial_number}</option>)}</Select>}</Field>
            <Field label="Buscar trabajador">{(id) => <Input id={id} type="search" value={workerSearch} onChange={(event) => { setWorkerSearch(event.target.value); setEmploymentId(""); setPersonId(""); }} placeholder="Nombre, número, empresa o sucursal" disabled={!deviceId || candidatesLoading} />}</Field>
          </div>
          {devicesError ? <div className="mt-4"><ErrorState error={devicesError} onRetry={() => setDeviceRetry((value) => value + 1)} /></div> : null}
          {!devicesLoading && !devicesError && devices.length === 0 ? <p className="mt-2 text-xs text-muted">No hay relojes visibles para tu usuario o empresa. Revisa que el reloj esté asignado a una sucursal autorizada.</p> : null}
          {deviceId ? <div className="mt-4">
            <Field label="Trabajador">{(id) => <Select id={id} value={employmentId} onChange={(event) => {
              const candidate = candidates.find((item) => item.employment_id === event.target.value);
              setEmploymentId(candidate?.employment_id ?? "");
              setPersonId(candidate?.person_id ?? "");
            }} disabled={candidatesLoading || Boolean(candidatesError) || !filteredCandidates.length}>
              <option value="">{candidatesLoading ? "Cargando trabajadores…" : filteredCandidates.length ? "Selecciona un trabajador" : "Sin trabajadores disponibles"}</option>
              {filteredCandidates.map((candidate) => <option key={candidate.employment_id} value={candidate.employment_id}>{candidate.worker_name} · {candidate.employee_number} · {candidate.company_name}{candidate.site_name ? ` · ${candidate.site_name}` : ""}{candidate.position ? ` · ${candidate.position}` : ""}</option>)}
            </Select>}</Field>
            {candidatesError ? <div className="mt-3"><ErrorState error={candidatesError} onRetry={() => setCandidateRetry((value) => value + 1)} /></div> : null}
            {!candidatesLoading && !candidatesError && candidates.length === 0 ? <p className="mt-2 text-xs text-muted">No hay trabajadores con empleo vigente en la empresa de este reloj. Revisa el empleo desde el expediente del trabajador.</p> : null}
            {!candidatesLoading && !candidatesError && candidates.length > 0 && filteredCandidates.length === 0 ? <p className="mt-2 text-xs text-muted">No hay trabajadores que coincidan con la búsqueda.</p> : null}
          </div> : <p className="mt-3 text-xs text-muted">Elige un reloj para mostrar a los trabajadores que pueden enrolarse ahí.</p>}
          <div className="mt-6"><p className="text-sm font-medium text-foreground">Credenciales a enrolar</p><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{METHODS.map((method) => { const active = methods.includes(method); const Icon = method === "fingerprint" ? Fingerprint : Hand; return <button type="button" key={method} onClick={() => toggleMethod(method)} aria-pressed={active} className={`rounded-xl border p-4 text-left transition-colors ${active ? "border-accent/50 bg-accent-soft shadow-glow" : "border-line-subtle bg-surface-raised hover:bg-surface-hover"}`}><Icon className={`h-5 w-5 ${active ? "text-accent" : "text-muted"}`} /><p className="mt-3 font-medium capitalize text-foreground">{method === "face" ? "Rostro" : method === "fingerprint" ? "Huellas" : method === "palm" ? "Palma" : "Tarjeta"}</p><p className="mt-1 text-xs text-muted">{active ? "Incluido en la solicitud" : "No seleccionado"}</p></button>; })}</div></div>
          {hasFingerprints ? <FingerprintSelector selected={fingers} onToggle={toggleFinger} /> : null}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line-subtle pt-5"><p className="text-xs text-muted">Las plantillas biométricas permanecen exclusivamente en el dispositivo.</p><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void create()} loading={saving} disabled={!personId || !employmentId || !deviceId || !methods.length || candidatesLoading || (hasFingerprints && !fingers.length)}>Crear solicitud</Button></div>
        </div>
      </Card> : null}
      {requestsError ? <div className="mb-4"><ErrorState error={requestsError} onRetry={() => void loadRequests()} /></div> : null}
      {requestsLoading ? <LoadingState rows={5} /> : requestsError ? null : <DataTable ariaLabel="Solicitudes de enrolamiento" columns={requestColumns} data={requests} keyOf={(row) => row.id} renderCard={(row) => {
        const labels: Record<string, string> = { requested: "Verificar identidad", identity_verified: "Aprobar", approved: "Enviar a enrolar", awaiting_device_enrollment: "Verificar credencial", verification_pending: "Completar" };
        const label = labels[row.status];
        const device = deviceById.get(row.device_id);
        return <div>
          <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="font-medium text-foreground">{row.worker_name}</p><p className="mt-0.5 truncate text-xs text-muted">{row.employee_number} · {row.company_name}{row.site_name ? ` · ${row.site_name}` : ""}</p><p className="mt-0.5 truncate text-xs text-muted">{device?.name ?? device?.serial_number ?? row.device_id}</p></div><span className="max-w-[42%] rounded-md border border-line-subtle bg-surface-raised px-2.5 py-1 text-right text-xs capitalize text-muted break-words">{row.status.replaceAll("_", " ")}</span></div>
          <p className="mt-3 text-xs text-muted">Credenciales: {row.methods.join(", ")}</p>
          {row.fingerprint_positions.length ? <p className="mt-1 text-xs text-muted">Huellas: {row.fingerprint_positions.map((finger) => FINGER_LABELS[finger] ?? finger).join(" · ")}</p> : null}
          {label ? <div className="mt-3 border-t border-line-subtle pt-2"><Can permission="enrollments.approve"><Button size="sm" variant="secondary" icon={row.status === "verification_pending" ? <CheckCircle2 className="h-4 w-4" /> : <CircleArrowRight className="h-4 w-4" />} onClick={() => row.status === "requested" ? setVerifyingRow(row) : void advance(row)} loading={updatingId === row.id}>{label}</Button></Can></div> : null}
        </div>;
      }} empty={<EmptyState icon={<Fingerprint className="h-5 w-5" />} title="Sin solicitudes" description="Crea una solicitud y realiza el enrolamiento presencial en el equipo autorizado." />} />}
      <Modal open={verifyingRow !== null} onClose={() => setVerifyingRow(null)} title="Verificar identidad presencial" description="Registra el documento o control interno utilizado; no captures imágenes del documento aquí." footer={<><Button variant="ghost" onClick={() => setVerifyingRow(null)}>Cancelar</Button><Button variant="primary" icon={<ShieldCheck className="h-4 w-4" />} onClick={() => verifyingRow ? void advance(verifyingRow, verificationReference.trim()) : undefined} loading={Boolean(verifyingRow && updatingId === verifyingRow.id)} disabled={verificationReference.trim().length < 3}>Confirmar identidad</Button></>}><Field label="Referencia de verificación">{(id) => <Input id={id} value={verificationReference} onChange={(event) => setVerificationReference(event.target.value)} placeholder="Ej. INE cotejada / control 1842" />}</Field></Modal>
    </>
  );
}

function FingerprintSelector({ selected, onToggle }: { selected: string[]; onToggle: (finger: string) => void }) {
  const groups = [FINGERS.slice(0, 5), FINGERS.slice(5)];
  return <section className="mt-6 rounded-xl border border-line-subtle bg-surface-input/70 p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-foreground">Posiciones de huellas</h3><p className="mt-1 text-sm text-muted">Selecciona uno o varios dedos. Puedes corregir esta elección antes de completar el enrolamiento.</p></div><span className="rounded-full border border-accent/20 bg-accent-soft px-3 py-1 text-sm font-medium text-accent shadow-sm">{selected.length} de 10 seleccionadas</span></div><div className="mt-5 grid gap-5 lg:grid-cols-2">{groups.map((hand) => <div key={hand[0].hand} className="rounded-xl border border-line-subtle bg-surface-card p-4"><div className="flex items-center gap-2 text-sm font-semibold text-foreground"><Hand className="h-4 w-4 text-accent" /> Mano {hand[0].hand.toLowerCase()}</div><div className="mt-4 grid grid-cols-5 gap-2">{hand.map((finger) => { const active = selected.includes(finger.id); return <button type="button" key={finger.id} aria-label={`${finger.hand} ${finger.label}`} aria-pressed={active} onClick={() => onToggle(finger.id)} className={`group flex min-h-24 flex-col items-center justify-center rounded-lg border px-1 text-center transition-all ${active ? "border-accent bg-accent text-white shadow-glow" : "border-line-subtle bg-surface-input text-muted hover:border-accent/50 hover:bg-surface-hover"}`}><Fingerprint className={`h-6 w-6 ${active ? "text-white" : "text-muted group-hover:text-accent"}`} /><span className="mt-2 text-xs font-semibold">{finger.short}</span><span className="mt-0.5 text-[10px] leading-tight">{finger.label}</span></button>; })}</div></div>)}</div></section>;
}

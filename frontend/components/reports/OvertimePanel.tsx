"use client";

import { CircleHelp, Clock3, FileSearch, Plus, ShieldCheck, Stamp, TimerReset, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { Company, Employment, OvertimeRequest } from "@/types";

function isoDate(value: Date): string {
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function minutes(value: number | null): string {
  if (!value) return "—";
  return `${value} min (${Math.floor(value / 60)} h ${value % 60} min)`;
}

const STATUS: Record<OvertimeRequest["status"], { label: string; tone: Tone }> = {
  pending_hr: { label: "Pendiente RR. HH.", tone: "amber" },
  pending_direction: { label: "Pendiente Dirección", tone: "sky" },
  approved: { label: "Autorizado", tone: "emerald" },
  rejected: { label: "No autorizado", tone: "red" },
  cancelled: { label: "Cancelado", tone: "zinc" },
};

export function OvertimePanel() {
  const { can } = useAuth();
  const { notify } = useToast();
  const today = useMemo(() => isoDate(new Date()), []);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [employments, setEmployments] = useState<Employment[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [rows, setRows] = useState<OvertimeRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualEmploymentId, setManualEmploymentId] = useState("");
  const [manualDate, setManualDate] = useState(today);
  const [manualMinutes, setManualMinutes] = useState("30");
  const [manualReason, setManualReason] = useState("");
  const [reviewing, setReviewing] = useState<OvertimeRequest | null>(null);
  const [reviewedMinutes, setReviewedMinutes] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [authorizing, setAuthorizing] = useState<OvertimeRequest | null>(null);
  const [authorizedMinutes, setAuthorizedMinutes] = useState("");
  const [authorizationNote, setAuthorizationNote] = useState("");

  const companyEmployments = useMemo(
    () => employments.filter((employment) => employment.company_id === companyId && employment.active),
    [companyId, employments],
  );

  const loadRows = useCallback(async () => {
    if (!companyId) { setRows([]); return; }
    setLoading(true); setError(null);
    try { setRows(await api.overtimeRequests({ company_id: companyId, date_from: dateFrom, date_to: dateTo })); }
    catch (cause) { setError(cause); }
    finally { setLoading(false); }
  }, [companyId, dateFrom, dateTo]);

  useEffect(() => {
    void api.companies().then((companyRows) => {
      setCompanies(companyRows);
      setCompanyId((current) => current || companyRows[0]?.id || "");
    }).catch(setError);

    // Dirección únicamente autoriza: no necesita acceso al catálogo de trabajadores.
    // RR. HH./operación sí lo requiere para registrar una solicitud manual.
    if (can("overtime.request")) {
      void api.employments().then(setEmployments).catch(setError);
    }
  }, [can]);
  useEffect(() => { void loadRows(); }, [loadRows]);
  useEffect(() => { if (!companyEmployments.some((row) => row.id === manualEmploymentId)) setManualEmploymentId(companyEmployments[0]?.id || ""); }, [companyEmployments, manualEmploymentId]);

  async function detect() {
    if (!companyId || working) return;
    setWorking(true); setError(null);
    try {
      const created = await api.detectOvertime({ company_id: companyId, date_from: dateFrom, date_to: dateTo });
      notify(created.length ? `${created.length} incidencia(s) detectada(s)` : "No se detectó tiempo extra", { message: created.length ? "Quedan pendientes de revisión de RR. HH." : "No hubo marca posterior al fin de turno.", tone: "success" });
      await loadRows();
    } catch (cause) { setError(cause); }
    finally { setWorking(false); }
  }

  async function createManual() {
    const value = Number(manualMinutes);
    if (!manualEmploymentId || !Number.isInteger(value) || value < 1 || manualReason.trim().length < 5 || working) return;
    setWorking(true); setError(null);
    try {
      await api.createManualOvertime({ employment_id: manualEmploymentId, attendance_date: manualDate, minutes: value, reason: manualReason.trim() });
      notify("Tiempo extra manual enviado", { message: "Queda pendiente de revisión de RR. HH.", tone: "success" });
      setManualOpen(false); setManualReason(""); setManualMinutes("30"); await loadRows();
    } catch (cause) { setError(cause); }
    finally { setWorking(false); }
  }

  function openReview(row: OvertimeRequest) {
    setReviewing(row); setReviewedMinutes(String(row.minutes)); setReviewNote("");
  }

  async function review(decision: "send_to_direction" | "reject") {
    if (!reviewing || reviewNote.trim().length < 3 || working) return;
    const value = Number(reviewedMinutes);
    if (decision === "send_to_direction" && (!Number.isInteger(value) || value < 1 || value > 720)) return;
    setWorking(true); setError(null);
    try {
      await api.reviewOvertime(reviewing.id, { decision, reviewed_minutes: decision === "send_to_direction" ? value : null, note: reviewNote.trim() });
      notify(decision === "send_to_direction" ? "Enviado a Dirección" : "Tiempo extra rechazado", { tone: "success" });
      setReviewing(null); await loadRows();
    } catch (cause) { setError(cause); }
    finally { setWorking(false); }
  }

  function openAuthorization(row: OvertimeRequest) {
    setAuthorizing(row); setAuthorizedMinutes(String(row.reviewed_minutes ?? row.minutes)); setAuthorizationNote("");
  }

  async function authorize(decision: "approve" | "reject") {
    if (!authorizing || authorizationNote.trim().length < 3 || working) return;
    const value = Number(authorizedMinutes);
    if (decision === "approve" && (!Number.isInteger(value) || value < 1 || value > (authorizing.reviewed_minutes ?? 0))) return;
    setWorking(true); setError(null);
    try {
      await api.authorizeOvertime(authorizing.id, { decision, authorized_minutes: decision === "approve" ? value : null, note: authorizationNote.trim() });
      notify(decision === "approve" ? "Tiempo extra autorizado" : "Tiempo extra no autorizado", { tone: "success" });
      setAuthorizing(null); await loadRows();
    } catch (cause) { setError(cause); }
    finally { setWorking(false); }
  }

  return <>
    <Card className="p-4 md:p-5">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-1.5"><h2 className="text-[15px] font-semibold text-foreground">Tiempo extra con autorización</h2><span title="Sólo se detecta una incidencia si hay una marca real posterior a la salida programada. La marca automática de fin de turno no genera tiempo extra." className="cursor-help text-muted hover:text-accent"><CircleHelp className="h-3.5 w-3.5" aria-hidden /></span></div><p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">Detección por reloj o alta manual → revisión de RR. HH. → autorización de Dirección. Sólo los minutos autorizados deben llegar a nómina.</p></div><div className="flex flex-wrap gap-2">{can("overtime.request") && <Button variant="secondary" size="sm" icon={<FileSearch className="h-3.5 w-3.5" />} onClick={() => void detect()} loading={working} disabled={!companyId}>Detectar por checadas</Button>}{can("overtime.request") && <Button variant="primary" size="sm" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setManualOpen(true)} disabled={!companyId}>Agregar manual</Button>}</div></div>
      <div className="mt-4 grid gap-3 md:grid-cols-3"><Field label="Empresa">{(id) => <Select id={id} value={companyId} onChange={(event) => setCompanyId(event.target.value)}><option value="">Selecciona</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field><Field label="Desde">{(id) => <Input id={id} type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />}</Field><Field label="Hasta">{(id) => <Input id={id} type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />}</Field></div>
    </Card>
    {error ? <div className="mt-4"><ErrorState error={error} onRetry={() => void loadRows()} /></div> : null}
    {loading ? <div className="mt-4"><LoadingState rows={4} /></div> : rows.length ? <div className="mt-4 space-y-2">{rows.map((row) => { const status = STATUS[row.status]; return <Card key={row.id} className="p-4"><div className="flex flex-col justify-between gap-4 lg:flex-row"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-medium text-foreground">{row.worker_name}</span><span className="font-mono text-[11px] text-muted">{row.employee_number}</span><Badge tone={status.tone}>{status.label}</Badge><Badge tone={row.source === "detected" ? "sky" : "zinc"}>{row.source === "detected" ? "Detectado por reloj" : "Captura manual"}</Badge></div><div className="mt-3 grid gap-2 text-[12px] text-muted sm:grid-cols-2 xl:grid-cols-4"><p><span className="block text-[10px] uppercase tracking-wide text-muted/80">Fecha</span><span className="font-mono text-foreground">{row.report_date}</span></p><p><span className="block text-[10px] uppercase tracking-wide text-muted/80">Evidencia</span>{row.detected_exit_at ? <span className="font-mono text-foreground">Salida {formatDateTime(row.detected_exit_at)}</span> : <span>Sin marca; solicitud manual</span>}</p><p><span className="block text-[10px] uppercase tracking-wide text-muted/80">Minutos</span><span className="font-mono text-foreground">Solicitados: {minutes(row.minutes)}</span></p><p><span className="block text-[10px] uppercase tracking-wide text-muted/80">Resolución</span><span className="font-mono text-foreground">{row.authorized_minutes ? `Autorizados: ${minutes(row.authorized_minutes)}` : row.reviewed_minutes ? `RR. HH.: ${minutes(row.reviewed_minutes)}` : "Pendiente"}</span></p></div><p className="mt-3 rounded-md border border-line-subtle bg-surface-raised/60 px-2.5 py-2 text-[12px] leading-relaxed text-muted">{row.reason}</p>{row.review_note && <p className="mt-2 text-[11px] text-muted"><span className="font-medium text-foreground">RR. HH.:</span> {row.review_note}</p>}{row.authorization_note && <p className="mt-1 text-[11px] text-muted"><span className="font-medium text-foreground">Dirección:</span> {row.authorization_note}</p>}</div><div className="flex shrink-0 flex-row gap-2 lg:flex-col lg:items-end">{row.status === "pending_hr" && can("overtime.review") && <Button size="sm" variant="secondary" icon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={() => openReview(row)}>Revisar RR. HH.</Button>}{row.status === "pending_direction" && can("overtime.approve") && <Button size="sm" variant="primary" icon={<Stamp className="h-3.5 w-3.5" />} onClick={() => openAuthorization(row)}>Autorizar</Button>}</div></div></Card>; })}</div> : <div className="mt-4"><EmptyState icon={<TimerReset className="h-5 w-5" />} title="Sin tiempos extra en el periodo" description="Ejecuta la detección para buscar checadas posteriores al término de turno, o agrega una solicitud manual justificada." /></div>}
    <Modal open={manualOpen} onClose={() => setManualOpen(false)} title="Agregar tiempo extra manual" description="Úsalo cuando no exista una marca posterior al fin de turno. La solicitud pasa por RR. HH. y Dirección." footer={<><Button variant="ghost" onClick={() => setManualOpen(false)}>Cancelar</Button><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createManual()} loading={working} disabled={!manualEmploymentId || manualReason.trim().length < 5}>Enviar a revisión</Button></>}><div className="grid gap-3"><Field label="Trabajador / empleo">{(id) => <Select id={id} value={manualEmploymentId} onChange={(event) => setManualEmploymentId(event.target.value)}><option value="">Selecciona</option>{companyEmployments.map((employment) => <option key={employment.id} value={employment.id}>{employment.employee_number} · {employment.position ?? "Sin puesto"}</option>)}</Select>}</Field><div className="grid grid-cols-2 gap-3"><Field label="Fecha">{(id) => <Input id={id} type="date" value={manualDate} onChange={(event) => setManualDate(event.target.value)} />}</Field><Field label="Minutos solicitados">{(id) => <Input id={id} type="number" min="1" max="720" value={manualMinutes} onChange={(event) => setManualMinutes(event.target.value)} />}</Field></div><Field label="Motivo y evidencia">{(id) => <Textarea id={id} value={manualReason} onChange={(event) => setManualReason(event.target.value)} placeholder="Ej. Atención de incidente en sitio, folio y responsable que lo confirma." />}</Field></div></Modal>
    <Modal open={reviewing !== null} onClose={() => setReviewing(null)} title="Revisión de RR. HH." description="Confirma los minutos elegibles. Quien solicitó la incidencia no puede revisarla." footer={<><Button variant="danger" icon={<XCircle className="h-4 w-4" />} onClick={() => void review("reject")} disabled={reviewNote.trim().length < 3}>Rechazar</Button><Button variant="primary" icon={<ShieldCheck className="h-4 w-4" />} onClick={() => void review("send_to_direction")} loading={working} disabled={reviewNote.trim().length < 3}>Enviar a Dirección</Button></>}><div className="grid gap-3"><Field label="Minutos revisados">{(id) => <Input id={id} type="number" min="1" max="720" value={reviewedMinutes} onChange={(event) => setReviewedMinutes(event.target.value)} />}</Field><Field label="Conclusión de RR. HH.">{(id) => <Textarea id={id} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="Evidencia revisada y criterio aplicado." />}</Field></div></Modal>
    <Modal open={authorizing !== null} onClose={() => setAuthorizing(null)} title="Autorización de Dirección" description="Autoriza hasta el máximo validado por RR. HH. La decisión queda auditada." footer={<><Button variant="danger" icon={<XCircle className="h-4 w-4" />} onClick={() => void authorize("reject")} disabled={authorizationNote.trim().length < 3}>No autorizar</Button><Button variant="primary" icon={<Stamp className="h-4 w-4" />} onClick={() => void authorize("approve")} loading={working} disabled={authorizationNote.trim().length < 3}>Autorizar</Button></>}><div className="grid gap-3"><Field label="Minutos a autorizar">{(id) => <Input id={id} type="number" min="1" max={authorizing?.reviewed_minutes ?? undefined} value={authorizedMinutes} onChange={(event) => setAuthorizedMinutes(event.target.value)} />}</Field><Field label="Resolución de Dirección">{(id) => <Textarea id={id} value={authorizationNote} onChange={(event) => setAuthorizationNote(event.target.value)} placeholder="Motivo de autorización o rechazo." />}</Field></div></Modal>
  </>;
}

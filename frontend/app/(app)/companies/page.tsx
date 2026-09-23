"use client";

import { Building2, MapPin, Pencil, Plus, RotateCcw, ShieldAlert, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { BusinessAddress, Company, CorporateGroup, HardDeleteCaptcha, Site } from "@/types";

type EditTarget = { kind: "company"; row: Company } | { kind: "site"; row: Site };
type HardTarget = EditTarget;
type AddressDraft = Record<"street" | "exterior_number" | "interior_number" | "neighborhood" | "municipality" | "state" | "postal_code" | "reference_notes", string>;

const MEXICAN_STATES = ["Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila de Zaragoza", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán de Ocampo", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz de Ignacio de la Llave", "Yucatán", "Zacatecas"] as const;

function emptyAddress(): AddressDraft {
  return { street: "", exterior_number: "", interior_number: "", neighborhood: "", municipality: "", state: "", postal_code: "", reference_notes: "" };
}

function addressDraft(address: BusinessAddress | null): AddressDraft {
  return address ? { street: address.street ?? "", exterior_number: address.exterior_number ?? "", interior_number: address.interior_number ?? "", neighborhood: address.neighborhood ?? "", municipality: address.municipality ?? "", state: address.state ?? "", postal_code: address.postal_code ?? "", reference_notes: address.reference_notes ?? "" } : emptyAddress();
}

function addressPayload(address: AddressDraft): Record<string, string | null> | null {
  if (!Object.values(address).some((value) => value.trim())) return null;
  return Object.fromEntries(Object.entries(address).map(([key, value]) => [key, value.trim() || null]));
}

function addressLabel(address: BusinessAddress | null): string | null {
  if (!address) return null;
  return [address.street, address.exterior_number, address.neighborhood, address.municipality, address.state, address.postal_code].filter(Boolean).join(", ") || null;
}

function AddressFields({ value, onChange }: { value: AddressDraft; onChange: (key: keyof AddressDraft, next: string) => void }) {
  return <div className="grid gap-3 sm:grid-cols-2">
    <Field label="Calle">{(id) => <Input id={id} value={value.street} onChange={(event) => onChange("street", event.target.value)} />}</Field>
    <Field label="No. exterior">{(id) => <Input id={id} value={value.exterior_number} onChange={(event) => onChange("exterior_number", event.target.value)} />}</Field>
    <Field label="No. interior">{(id) => <Input id={id} value={value.interior_number} onChange={(event) => onChange("interior_number", event.target.value)} />}</Field>
    <Field label="Colonia">{(id) => <Input id={id} value={value.neighborhood} onChange={(event) => onChange("neighborhood", event.target.value)} />}</Field>
    <Field label="Municipio / alcaldía">{(id) => <Input id={id} value={value.municipality} onChange={(event) => onChange("municipality", event.target.value)} />}</Field>
    <Field label="Estado">{(id) => <Select id={id} value={value.state} onChange={(event) => onChange("state", event.target.value)}><option value="">Selecciona</option>{MEXICAN_STATES.map((state) => <option key={state}>{state}</option>)}</Select>}</Field>
    <Field label="Código postal">{(id) => <Input id={id} inputMode="numeric" maxLength={5} value={value.postal_code} onChange={(event) => onChange("postal_code", event.target.value)} />}</Field>
    <Field label="Referencias">{(id) => <Input id={id} value={value.reference_notes} onChange={(event) => onChange("reference_notes", event.target.value)} />}</Field>
  </div>;
}

export default function CompaniesPage() {
  const { user } = useAuth();
  const { notify } = useToast();
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [groupId, setGroupId] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupCode, setGroupCode] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyTradeName, setCompanyTradeName] = useState("");
  const [rfc, setRfc] = useState("");
  const [employerRegistration, setEmployerRegistration] = useState("");
  const [companyAddress, setCompanyAddress] = useState<AddressDraft>(emptyAddress);
  const [siteCompanyId, setSiteCompanyId] = useState("");
  const [siteName, setSiteName] = useState("");
  const [siteCode, setSiteCode] = useState("");
  const [siteAddress, setSiteAddress] = useState<AddressDraft>(emptyAddress);
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null);
  const [editName, setEditName] = useState("");
  const [editCode, setEditCode] = useState("");
  const [editTradeName, setEditTradeName] = useState("");
  const [editRfc, setEditRfc] = useState("");
  const [editEmployerRegistration, setEditEmployerRegistration] = useState("");
  const [editAddress, setEditAddress] = useState<AddressDraft>(emptyAddress);
  const [hardTarget, setHardTarget] = useState<HardTarget | null>(null);
  const [captcha, setCaptcha] = useState<HardDeleteCaptcha | null>(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loadedGroups = await api.corporateGroups();
      setGroups(loadedGroups);
      const selected = groupId || loadedGroups[0]?.id || "";
      if (!selected) { setCompanies([]); setSites([]); return; }
      setGroupId(selected);
      const loadedCompanies = await api.companies(selected, showInactive);
      const loadedSites = (await Promise.all(loadedCompanies.map((item) => api.sites(item.id, showInactive)))).flat();
      setCompanies(loadedCompanies);
      setSites(loadedSites);
      setSiteCompanyId((current) => loadedCompanies.some((item) => item.id === current && item.active) ? current : loadedCompanies.find((item) => item.active)?.id || "");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [groupId, showInactive]);

  useEffect(() => void load(), [load]);

  async function createGroup() {
    if (!groupName.trim() || !groupCode.trim() || saving) return;
    setSaving(true);
    try {
      const created = await api.createCorporateGroup({ name: groupName.trim(), code: groupCode.trim() });
      setGroupId(created.id); setGroupName(""); setGroupCode(""); notify("Grupo creado", { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  async function createCompany() {
    if (!groupId || !companyName.trim() || saving) return;
    setSaving(true);
    try {
      await api.createCompany({ corporate_group_id: groupId, legal_name: companyName.trim(), trade_name: companyTradeName.trim() || null, tax_id: rfc.trim() || null, employer_registration: employerRegistration.trim() || null, address: addressPayload(companyAddress), timezone: "America/Mexico_City" });
      setCompanyName(""); setCompanyTradeName(""); setRfc(""); setEmployerRegistration(""); setCompanyAddress(emptyAddress()); notify("Empresa creada", { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  async function createSite() {
    if (!siteCompanyId || !siteName.trim() || !siteCode.trim() || saving) return;
    setSaving(true);
    try {
      await api.createSite({ company_id: siteCompanyId, name: siteName.trim(), code: siteCode.trim().toUpperCase(), address: addressPayload(siteAddress), timezone: "America/Mexico_City" });
      setSiteName(""); setSiteCode(""); setSiteAddress(emptyAddress()); notify("Sucursal creada", { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  function openEdit(target: EditTarget) {
    setEditTarget(target);
    setEditName(target.kind === "company" ? target.row.legal_name : target.row.name);
    setEditCode(target.kind === "site" ? target.row.code : "");
    setEditTradeName(target.kind === "company" ? target.row.trade_name ?? "" : "");
    setEditRfc(target.kind === "company" ? target.row.tax_id ?? "" : "");
    setEditEmployerRegistration(target.kind === "company" ? target.row.employer_registration ?? "" : "");
    setEditAddress(addressDraft(target.row.address));
  }

  async function saveEdit() {
    if (!editTarget || !editName.trim() || saving) return;
    setSaving(true);
    try {
      if (editTarget.kind === "company") await api.updateCompany(editTarget.row.id, { legal_name: editName.trim(), trade_name: editTradeName.trim() || null, tax_id: editRfc.trim() || null, employer_registration: editEmployerRegistration.trim() || null, address: addressPayload(editAddress) });
      else await api.updateSite(editTarget.row.id, { name: editName.trim(), code: editCode.trim().toUpperCase() || editTarget.row.code, address: addressPayload(editAddress) });
      setEditTarget(null); notify("Registro actualizado", { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  async function softDelete(target: EditTarget) {
    const label = target.kind === "company" ? "empresa" : "sucursal";
    if (saving || !window.confirm(`¿Dar de baja la ${label}? Podrá restaurarse después.`)) return;
    setSaving(true);
    try {
      if (target.kind === "company") await api.deleteCompany(target.row.id); else await api.deleteSite(target.row.id);
      notify(`${label[0].toUpperCase()}${label.slice(1)} dada de baja`, { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  async function restore(target: EditTarget) {
    setSaving(true);
    try {
      if (target.kind === "company") await api.updateCompany(target.row.id, { active: true }); else await api.updateSite(target.row.id, { active: true });
      notify("Registro restaurado", { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  async function openHardDelete(target: HardTarget) {
    setSaving(true);
    try {
      const challenge = target.kind === "company" ? await api.companyHardDeleteCaptcha(target.row.id) : await api.siteHardDeleteCaptcha(target.row.id);
      setHardTarget(target); setCaptcha(challenge); setCaptchaAnswer("");
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  async function hardDelete() {
    if (!hardTarget || !captcha || captchaAnswer.length !== 6 || saving) return;
    setSaving(true);
    try {
      const body = { captcha_token: captcha.token, captcha_answer: captchaAnswer };
      if (hardTarget.kind === "company") await api.hardDeleteCompany(hardTarget.row.id, body); else await api.hardDeleteSite(hardTarget.row.id, body);
      setHardTarget(null); setCaptcha(null); notify("Registro eliminado definitivamente", { tone: "success" }); await load();
    } catch (err) { setError(err); } finally { setSaving(false); }
  }

  function updateCaptchaAnswer(value: string) {
    setCaptchaAnswer(value.split("").filter((character) => character >= "0" && character <= "9").join(""));
  }

  const activeCompanies = companies.filter((item) => item.active);

  function renderActions(target: EditTarget) {
    const label = target.kind === "company" ? "empresa" : "sucursal";
    const width = target.kind === "company" ? "w-9" : "w-8";
    if (target.row.active) {
      return (
        <>
          <Button variant="ghost" icon={<Pencil className="h-4 w-4" />} className={`${width} !px-0`} aria-label={`Editar ${label}`} title={`Editar ${label}`} onClick={() => openEdit(target)} />
          <Button variant="ghost" icon={<Trash2 className="h-4 w-4" />} className={`${width} !px-0`} aria-label={`Dar de baja ${label}`} title={`Dar de baja ${label}`} onClick={() => void softDelete(target)} />
        </>
      );
    }
    return (
      <>
        <Button variant="ghost" icon={<RotateCcw className="h-4 w-4" />} className={`${width} !px-0`} aria-label={`Restaurar ${label}`} title={`Restaurar ${label}`} onClick={() => void restore(target)} />
        {user?.is_superuser ? <Button variant="danger" icon={<ShieldAlert className="h-4 w-4" />} className={`${width} !px-0`} aria-label={`Eliminar ${label} definitivamente`} title={`Eliminar ${label} definitivamente`} onClick={() => void openHardDelete(target)} /> : null}
      </>
    );
  }

  function renderSite(site: Site) {
    const target: EditTarget = { kind: "site", row: site };
    return (
      <div key={site.id} className={`flex items-center justify-between gap-3 rounded-xl border border-line-subtle px-3 py-2.5 ${site.active ? "bg-zinc-50" : "border-dashed bg-zinc-50/50 opacity-70"}`}>
        <div className="flex min-w-0 items-center gap-2">
          <MapPin className="h-4 w-4 shrink-0 text-accent-700" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{site.name}</p>
            <p className="text-xs text-zinc-500">{site.code} · {site.active ? "Activa" : "Dada de baja"}</p>
            {addressLabel(site.address) ? <p className="mt-1 truncate text-xs text-zinc-400">{addressLabel(site.address)}</p> : null}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">{renderActions(target)}</div>
      </div>
    );
  }

  function renderCompany(company: Company) {
    const branches = sites.filter((site) => site.company_id === company.id);
    const target: EditTarget = { kind: "company", row: company };
    return (
      <Card key={company.id} className={`p-5 ${company.active ? "" : "border-dashed opacity-70"}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><Building2 className="h-5 w-5" /></span>
            <div>
              <p className="font-semibold text-zinc-900">{company.legal_name}</p>
              <p className="mt-1 text-sm text-zinc-500">{company.trade_name ?? "Sin nombre comercial"} · RFC {company.tax_id ?? "pendiente"}</p>
              <p className="mt-1 text-xs text-zinc-500">Registro patronal: {company.employer_registration ?? "pendiente"}</p>
              {addressLabel(company.address) ? <p className="mt-1 text-xs text-zinc-400">{addressLabel(company.address)}</p> : null}
              <p className="mt-1 text-xs text-zinc-400">{company.active ? "Activa" : "Dada de baja"} · {branches.length} sucursal(es)</p>
            </div>
          </div>
          <div className="flex gap-1">{renderActions(target)}</div>
        </div>
        <div className="mt-5 border-t border-line-subtle pt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Sucursales de esta empresa</p>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {branches.length ? branches.map(renderSite) : <p className="text-sm text-zinc-500">Esta empresa todavía no tiene sucursales.</p>}
          </div>
        </div>
      </Card>
    );
  }

  return (
    <>
      <PageHeader title="Empresas y sucursales" description="Cada sucursal pertenece a una empresa legal dentro del grupo corporativo." crumbs={[{ label: "Empresas y sucursales" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5">
        <div className="grid gap-5 xl:grid-cols-3">
          <div>
            <p className="font-semibold text-zinc-800">Grupo corporativo</p>
            <p className="mt-1 text-sm text-zinc-500">Contenedor de las empresas legales del mismo grupo.</p>
            {groups.length ? <div className="mt-3"><Field label="Grupo que administras">{(id) => <Select id={id} value={groupId} onChange={(event) => setGroupId(event.target.value)}>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field></div> : <div className="mt-3 grid gap-3"><Field label="Nombre">{(id) => <Input id={id} value={groupName} onChange={(event) => setGroupName(event.target.value)} />}</Field><Field label="Código">{(id) => <Input id={id} value={groupCode} onChange={(event) => setGroupCode(event.target.value.toUpperCase())} />}</Field><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createGroup()} loading={saving}>Crear grupo</Button></div>}
          </div>
          <div className="border-t border-line-subtle pt-5 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0">
            <p className="font-semibold text-zinc-800">Nueva empresa</p>
            <div className="mt-3 grid gap-3"><Field label="Razón social">{(id) => <Input id={id} value={companyName} onChange={(event) => setCompanyName(event.target.value)} disabled={!groupId} />}</Field><Field label="Nombre comercial">{(id) => <Input id={id} value={companyTradeName} onChange={(event) => setCompanyTradeName(event.target.value)} disabled={!groupId} />}</Field><Field label="RFC">{(id) => <Input id={id} value={rfc} onChange={(event) => setRfc(event.target.value.toUpperCase())} disabled={!groupId} />}</Field><Field label="Registro patronal IMSS">{(id) => <Input id={id} value={employerRegistration} onChange={(event) => setEmployerRegistration(event.target.value.toUpperCase())} disabled={!groupId} />}</Field><details className="rounded-xl border border-line-subtle p-3"><summary className="cursor-pointer text-sm font-medium text-zinc-700">Dirección fiscal en México</summary><div className="mt-3"><AddressFields value={companyAddress} onChange={(key, value) => setCompanyAddress((current) => ({ ...current, [key]: value }))} /></div></details><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createCompany()} loading={saving} disabled={!groupId || !companyName.trim()}>Crear empresa</Button></div>
          </div>
          <div className="border-t border-line-subtle pt-5 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0">
            <p className="font-semibold text-zinc-800">Nueva sucursal</p>
            <div className="mt-3 grid gap-3"><Field label="Empresa">{(id) => <Select id={id} value={siteCompanyId} onChange={(event) => setSiteCompanyId(event.target.value)} disabled={!activeCompanies.length}><option value="">Selecciona</option>{activeCompanies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field><Field label="Nombre">{(id) => <Input id={id} value={siteName} onChange={(event) => setSiteName(event.target.value)} disabled={!siteCompanyId} />}</Field><Field label="Código">{(id) => <Input id={id} value={siteCode} onChange={(event) => setSiteCode(event.target.value.toUpperCase())} disabled={!siteCompanyId} />}</Field><details className="rounded-xl border border-line-subtle p-3"><summary className="cursor-pointer text-sm font-medium text-zinc-700">Dirección operativa en México</summary><div className="mt-3"><AddressFields value={siteAddress} onChange={(key, value) => setSiteAddress((current) => ({ ...current, [key]: value }))} /></div></details><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createSite()} loading={saving} disabled={!siteCompanyId || !siteName.trim() || !siteCode.trim()}>Crear sucursal</Button></div>
          </div>
        </div>
      </Card>
      <label className="mb-4 flex min-h-11 items-center gap-2 text-sm text-zinc-600"><input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} /> Mostrar registros dados de baja</label>
      {loading ? <LoadingState rows={5} /> : companies.length === 0 ? <EmptyState icon={<Building2 className="h-5 w-5" />} title="Sin empresas" description="Crea la primera empresa legal del grupo." /> : <div className="space-y-4">{companies.map(renderCompany)}</div>}
      <Modal
        open={editTarget !== null}
        onClose={() => setEditTarget(null)}
        title={editTarget?.kind === "company" ? "Editar empresa" : "Editar sucursal"}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="ghost" onClick={() => setEditTarget(null)}>Cancelar</Button>
            <Button variant="primary" icon={<Pencil className="h-4 w-4" />} onClick={() => void saveEdit()} loading={saving}>Guardar</Button>
          </div>
        }
      >
        <div className="grid gap-3">
          <Field label={editTarget?.kind === "company" ? "Razón social" : "Nombre"}>
            {(id) => <Input id={id} value={editName} onChange={(event) => setEditName(event.target.value)} />}
          </Field>
          {editTarget?.kind === "site" ? (
            <Field label="Código">
              {(id) => <Input id={id} value={editCode} onChange={(event) => setEditCode(event.target.value.toUpperCase())} />}
            </Field>
          ) : null}
          {editTarget?.kind === "company" ? <><Field label="Nombre comercial">{(id) => <Input id={id} value={editTradeName} onChange={(event) => setEditTradeName(event.target.value)} />}</Field><Field label="RFC">{(id) => <Input id={id} value={editRfc} onChange={(event) => setEditRfc(event.target.value.toUpperCase())} />}</Field><Field label="Registro patronal IMSS">{(id) => <Input id={id} value={editEmployerRegistration} onChange={(event) => setEditEmployerRegistration(event.target.value.toUpperCase())} />}</Field></> : null}
          <div className="border-t border-line-subtle pt-4"><p className="mb-3 text-sm font-medium text-zinc-700">Dirección {editTarget?.kind === "company" ? "fiscal" : "operativa"} en México</p><AddressFields value={editAddress} onChange={(key, value) => setEditAddress((current) => ({ ...current, [key]: value }))} /></div>
        </div>
      </Modal>
      <Modal
        open={hardTarget !== null}
        onClose={() => { setHardTarget(null); setCaptcha(null); }}
        title="Eliminación definitiva"
        description="Debe estar dado de baja y sin dependencias."
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="ghost" onClick={() => { setHardTarget(null); setCaptcha(null); }}>Cancelar</Button>
            <Button variant="danger" icon={<ShieldAlert className="h-4 w-4" />} onClick={() => void hardDelete()} loading={saving} disabled={captchaAnswer.length !== 6}>Eliminar definitivamente</Button>
          </div>
        }
      >
        <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">CAPTCHA de precaución</p>
          <p className="mt-1">{captcha?.prompt}</p>
        </div>
        <div className="mt-4">
          <Field label="Código de seis dígitos">
            {(id) => <Input id={id} inputMode="numeric" maxLength={6} value={captchaAnswer} onChange={(event) => updateCaptchaAnswer(event.target.value)} />}
          </Field>
        </div>
      </Modal>
    </>
  );
}

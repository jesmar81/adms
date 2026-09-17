"use client";

import { Building2, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Company, CorporateGroup, Site } from "@/types";

const COMPANY_COLUMNS: Column<Company>[] = [
  { key: "name", header: "Razón social", render: (row) => <span className="font-medium">{row.legal_name}</span> },
  { key: "trade", header: "Nombre comercial", render: (row) => row.trade_name ?? "—" },
  { key: "rfc", header: "RFC", render: (row) => <span className="font-mono text-[13px]">{row.tax_id ?? "—"}</span> },
  { key: "tz", header: "Zona horaria", render: (row) => <span className="text-zinc-500">{row.timezone}</span> },
];

export default function CompaniesPage() {
  const { notify } = useToast();
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [groupId, setGroupId] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupCode, setGroupCode] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [rfc, setRfc] = useState("");
  const [siteCompanyId, setSiteCompanyId] = useState("");
  const [siteName, setSiteName] = useState("");
  const [siteCode, setSiteCode] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loadedGroups = await api.corporateGroups();
      setGroups(loadedGroups);
      const selected = groupId || loadedGroups[0]?.id || "";
      if (selected) {
        setGroupId(selected);
        const loadedCompanies = await api.companies(selected);
        setCompanies(loadedCompanies);
        setSiteCompanyId((current) => current || loadedCompanies[0]?.id || "");
        setSites((await Promise.all(loadedCompanies.map((company) => api.sites(company.id)))).flat());
      } else {
        setCompanies([]);
        setSites([]);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useEffect(() => void load(), [load]);

  async function createGroup() {
    if (!groupName.trim() || !groupCode.trim() || saving) return;
    setSaving(true);
    try {
      const created = await api.createCorporateGroup({ name: groupName.trim(), code: groupCode.trim() });
      setGroupId(created.id);
      setGroupName("");
      setGroupCode("");
      notify("Grupo creado", { tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function createCompany() {
    if (!groupId || !companyName.trim() || saving) return;
    setSaving(true);
    try {
      await api.createCompany({
        corporate_group_id: groupId,
        legal_name: companyName.trim(),
        tax_id: rfc.trim() || null,
        timezone: "America/Mexico_City",
      });
      setCompanyName("");
      setRfc("");
      notify("Empresa creada", { tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  async function createSite() {
    if (!siteCompanyId || !siteName.trim() || !siteCode.trim() || saving) return;
    setSaving(true);
    try {
      await api.createSite({
        company_id: siteCompanyId,
        name: siteName.trim(),
        code: siteCode.trim().toUpperCase(),
        timezone: "America/Mexico_City",
      });
      setSiteName("");
      setSiteCode("");
      notify("Sitio creado", { tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader title="Empresas y sitios" description="Estructura corporativa y centros de trabajo del grupo." crumbs={[{ label: "Empresas y sitios" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}

      <Card className="mb-5 p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8">
          <div>
            <p className="text-sm font-semibold text-zinc-800">Grupo corporativo</p>
            {groups.length ? (
              <div className="mt-3 max-w-sm"><Field label="Grupo activo">{(id) => <Select id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)}>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field></div>
            ) : (
              <div className="mt-3 grid gap-2 sm:grid-cols-2"><Field label="Nombre">{(id) => <Input id={id} value={groupName} onChange={(e) => setGroupName(e.target.value)} placeholder="Grupo ejemplo" />}</Field><Field label="Código">{(id) => <Input id={id} value={groupCode} onChange={(e) => setGroupCode(e.target.value.toUpperCase())} placeholder="GRUPO" />}</Field><div className="sm:col-span-2"><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createGroup()} loading={saving}>Crear grupo</Button></div></div>
            )}
          </div>
          <div className="border-t border-line-subtle pt-4 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            <p className="text-sm font-semibold text-zinc-800">Nueva empresa</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_9rem_auto]"><Field label="Razón social">{(id) => <Input id={id} value={companyName} onChange={(e) => setCompanyName(e.target.value)} disabled={!groupId} />}</Field><Field label="RFC">{(id) => <Input id={id} value={rfc} onChange={(e) => setRfc(e.target.value.toUpperCase())} disabled={!groupId} />}</Field><div className="flex items-end"><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createCompany()} loading={saving} disabled={!groupId || !companyName.trim()}>Crear</Button></div></div>
          </div>
        </div>
        <div className="mt-5 border-t border-line-subtle pt-5">
          <p className="text-sm font-semibold text-zinc-800">Nuevo sitio o centro de trabajo</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_10rem_auto]">
            <Field label="Empresa">{(id) => <Select id={id} value={siteCompanyId} onChange={(e) => setSiteCompanyId(e.target.value)} disabled={!companies.length}><option value="">Selecciona una empresa</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.legal_name}</option>)}</Select>}</Field>
            <Field label="Nombre">{(id) => <Input id={id} value={siteName} onChange={(e) => setSiteName(e.target.value)} disabled={!siteCompanyId} placeholder="Planta Norte" />}</Field>
            <Field label="Código">{(id) => <Input id={id} value={siteCode} onChange={(e) => setSiteCode(e.target.value.toUpperCase())} disabled={!siteCompanyId} placeholder="NORTE" />}</Field>
            <div className="flex items-end"><Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => void createSite()} loading={saving} disabled={!siteCompanyId || !siteName.trim() || !siteCode.trim()}>Crear sitio</Button></div>
          </div>
        </div>
      </Card>

      {loading ? <LoadingState rows={5} /> : <DataTable ariaLabel="Empresas" columns={COMPANY_COLUMNS} data={companies} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{row.legal_name}</p><p className="mt-1 text-xs text-zinc-500">{row.tax_id ?? "RFC pendiente"}</p></div>} empty={<EmptyState icon={<Building2 className="h-5 w-5" />} title="Sin empresas" description="Crea la primera empresa legal del grupo." />} />}
      {sites.length > 0 && <p className="mt-4 text-xs text-zinc-500">{sites.length} sitio(s) registrados en el grupo.</p>}
    </>
  );
}

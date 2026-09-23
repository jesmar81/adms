"use client";

import { Activity, Building2, Radio } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { LivePunctualityPanel } from "@/components/reports/LivePunctualityPanel";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api";
import type { Company } from "@/types";

export default function PendingArrivalsPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const loadCompanies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await api.companies();
      setCompanies(rows);
      setCompanyId((current) => rows.some((company) => company.id === current) ? current : rows[0]?.id ?? "");
    } catch (cause) {
      setError(cause);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadCompanies(); }, [loadCompanies]);

  const selectedCompany = companies.find((company) => company.id === companyId);

  return (
    <>
      <PageHeader
        title="Llegadas en vivo"
        description="Monitorea a quienes ya debían iniciar su turno y todavía no registran entrada. La lista se actualiza automáticamente y retira a cada persona cuando llega su marcación."
        crumbs={[{ label: "Marcaciones", href: "/attendance" }, { label: "Llegadas en vivo" }]}
      />

      {loading ? <LoadingState rows={3} /> : error ? <ErrorState error={error} onRetry={() => void loadCompanies()} /> : !companies.length ? (
        <EmptyState icon={<Building2 className="h-5 w-5" />} title="No hay empresas disponibles" description="Tu usuario no tiene empresas autorizadas para consultar llegadas." />
      ) : (
        <div className="space-y-4">
          <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="w-full sm:max-w-sm">
              <Field label="Empresa" hint="La lista considera únicamente los turnos de hoy en esta empresa.">
                {(id) => (
                  <Select id={id} value={companyId} onChange={(event) => setCompanyId(event.target.value)}>
                    {companies.map((company) => <option key={company.id} value={company.id}>{company.trade_name || company.legal_name}</option>)}
                  </Select>
                )}
              </Field>
            </div>
            <div className="flex items-center gap-2 self-start rounded-md border border-emerald-400/15 bg-emerald-400/5 px-2.5 py-1.5 text-[11px] text-emerald-300 sm:self-auto">
              <Radio className="h-3.5 w-3.5" aria-hidden />
              <span>Monitoreo automático cada 15 s</span>
            </div>
          </Card>
          {selectedCompany ? <LivePunctualityPanel companyId={selectedCompany.id} timezone={selectedCompany.timezone || "America/Mexico_City"} /> : (
            <EmptyState icon={<Activity className="h-5 w-5" />} title="Selecciona una empresa" description="Elige una empresa para consultar sus llegadas pendientes." />
          )}
        </div>
      )}
    </>
  );
}

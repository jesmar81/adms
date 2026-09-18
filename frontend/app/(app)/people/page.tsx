"use client";

import { Plus, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { CorporateGroup, Person } from "@/types";

const COLUMNS: Column<Person>[] = [
  {
    key: "name",
    header: "Trabajador",
    render: (row) => <span className="font-medium">{[row.first_name, row.last_name, row.second_last_name].filter(Boolean).join(" ")}</span>,
  },
  { key: "preferred", header: "Nombre preferido", render: (row) => row.preferred_name ?? "—" },
  { key: "email", header: "Correo", render: (row) => row.email ?? "—" },
  { key: "phone", header: "Teléfono", render: (row) => row.phone ?? "—" },
  {
    key: "actions",
    header: "",
    render: (row) => (
      <Link
        href={`/people/${row.id}`}
        className="text-sm font-medium text-accent-700 transition-colors hover:text-accent-900"
      >
        Ver expediente
      </Link>
    ),
  },
];

export default function PeoplePage() {
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [groupId, setGroupId] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const loadedGroups = await api.corporateGroups();
      setGroups(loadedGroups);
      const selected = groupId || loadedGroups[0]?.id || "";
      if (selected) {
        setGroupId(selected);
        setPeople(await api.people(selected));
      } else {
        setPeople([]);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  useEffect(() => void load(), [load]);

  return (
    <>
      <PageHeader title="Trabajadores" description="Expedientes laborales compartidos dentro del grupo corporativo." crumbs={[{ label: "Trabajadores" }]} actions={<Link href="/people/new"><Button variant="primary" icon={<Plus className="h-4 w-4" />}>Nuevo trabajador</Button></Link>} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5"><div className="max-w-sm"><Field label="Grupo corporativo">{(id) => <Select id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)} disabled={!groups.length}><option value="">Selecciona un grupo</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field></div></Card>
      {loading ? <LoadingState rows={6} /> : <DataTable ariaLabel="Trabajadores" columns={COLUMNS} data={people} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{[row.first_name, row.last_name, row.second_last_name].filter(Boolean).join(" ")}</p><p className="mt-1 text-xs text-zinc-500">{row.email ?? "Sin correo"}</p><Link href={`/people/${row.id}`} className="mt-3 inline-block text-sm font-medium text-accent-700">Ver expediente</Link></div>} empty={<EmptyState icon={<Users className="h-5 w-5" />} title="Sin trabajadores" description="Crea el primer expediente laboral del grupo." />} />}
    </>
  );
}

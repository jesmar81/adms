"use client";

import { Plus, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { DataTable } from "@/components/ui/table";
import type { Column } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { CorporateGroup, Person } from "@/types";

const COLUMNS: Column<Person>[] = [
  {
    key: "name",
    header: "Persona",
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
  const { notify } = useToast();
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [groupId, setGroupId] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [secondLastName, setSecondLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [nationality, setNationality] = useState("Mexicana");

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

  async function create() {
    if (!groupId || !firstName.trim() || !lastName.trim() || saving) return;
    setSaving(true);
    try {
      await api.createPerson({
        corporate_group_id: groupId,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        second_last_name: secondLastName.trim() || null,
        email: email.trim() || null,
        phone: phone.trim() || null,
        birth_date: birthDate || null,
        nationality: nationality.trim() || null,
      });
      setFirstName("");
      setLastName("");
      setSecondLastName("");
      setEmail("");
      setPhone("");
      setBirthDate("");
      setNationality("Mexicana");
      notify("Persona creada", { message: "Ahora puedes agregar sus empleos y asignaciones.", tone: "success" });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader title="Personas" description="Identidad compartida para trabajadores con uno o varios empleos dentro del grupo." crumbs={[{ label: "Personas" }]} />
      {error ? <div className="mb-4"><ErrorState error={error} onRetry={() => void load()} /></div> : null}
      <Card className="mb-5 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="lg:w-64"><Field label="Grupo corporativo">{(id) => <Select id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)} disabled={!groups.length}><option value="">Selecciona un grupo</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field></div>
          <div className="grid flex-1 gap-2 sm:grid-cols-2 xl:grid-cols-4"><Field label="Nombre">{(id) => <Input id={id} value={firstName} onChange={(e) => setFirstName(e.target.value)} disabled={!groupId} />}</Field><Field label="Apellido paterno">{(id) => <Input id={id} value={lastName} onChange={(e) => setLastName(e.target.value)} disabled={!groupId} />}</Field><Field label="Apellido materno">{(id) => <Input id={id} value={secondLastName} onChange={(e) => setSecondLastName(e.target.value)} disabled={!groupId} />}</Field><Field label="Correo">{(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={!groupId} />}</Field><Field label="Teléfono">{(id) => <Input id={id} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={!groupId} />}</Field><Field label="Nacimiento">{(id) => <Input id={id} type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} disabled={!groupId} />}</Field><Field label="Nacionalidad">{(id) => <Input id={id} value={nationality} onChange={(e) => setNationality(e.target.value)} disabled={!groupId} />}</Field></div>
          <Button variant="primary" icon={<Plus className="h-4 w-4" />} className="w-10 !px-0" aria-label="Crear persona" title="Crear persona" onClick={() => void create()} loading={saving} disabled={!groupId || !firstName.trim() || !lastName.trim()} />
        </div>
      </Card>
      {loading ? <LoadingState rows={6} /> : <DataTable ariaLabel="Personas" columns={COLUMNS} data={people} keyOf={(row) => row.id} renderCard={(row) => <div><p className="font-medium">{[row.first_name, row.last_name, row.second_last_name].filter(Boolean).join(" ")}</p><p className="mt-1 text-xs text-zinc-500">{row.email ?? "Sin correo"}</p><Link href={`/people/${row.id}`} className="mt-3 inline-block text-sm font-medium text-accent-700">Ver expediente</Link></div>} empty={<EmptyState icon={<Users className="h-5 w-5" />} title="Sin personas" description="Crea la primera persona del grupo para asignarle empleos y horarios." />} />}
    </>
  );
}

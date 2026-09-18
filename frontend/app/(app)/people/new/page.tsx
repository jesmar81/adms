"use client";
/* eslint-disable @next/next/no-img-element -- local Blob preview, never remotely optimized */

import { ArrowLeft, Camera, Save, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api";
import type { CorporateGroup } from "@/types";

const STATES = ["Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila de Zaragoza", "Colima", "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán de Ocampo", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz de Ignacio de la Llave", "Yucatán", "Zacatecas"] as const;
const RELATIONSHIPS = ["Madre", "Padre", "Cónyuge", "Pareja", "Hijo(a)", "Hermano(a)", "Tutor(a)", "Otro"] as const;

const EMPTY = {
  first_name: "", last_name: "", second_last_name: "", preferred_name: "", email: "", phone: "", birth_date: "",
  sex: "", marital_status: "", nationality: "Mexicana", birth_state: "", address_street: "", address_ext_number: "",
  address_int_number: "", address_neighborhood: "", address_municipality: "", address_state: "", postal_code: "",
  emergency_contact_name: "", emergency_contact_phone: "", emergency_contact_relationship: "",
};

const EMPTY_SENSITIVE = { curp: "", rfc: "", nss: "", fiscal_name: "", tax_regime: "", fiscal_postal_code: "" };

export default function NewWorkerPage() {
  const router = useRouter();
  const { notify } = useToast();
  const [groups, setGroups] = useState<CorporateGroup[]>([]);
  const [groupId, setGroupId] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>(EMPTY);
  const [sensitive, setSensitive] = useState<Record<string, string>>(EMPTY_SENSITIVE);
  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    void api.corporateGroups().then((items) => {
      setGroups(items);
      setGroupId(items[0]?.id ?? "");
    }).catch(setError).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!photo) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(photo);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  function setValue(key: string, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function choosePhoto(file: File | undefined) {
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setError(new Error("La fotografía debe ser JPG, PNG o WebP y pesar máximo 5 MB."));
      return;
    }
    setError(null);
    setPhoto(file);
  }

  async function save() {
    if (!groupId || !draft.first_name.trim() || !draft.last_name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const worker = await api.createPerson({
        corporate_group_id: groupId,
        ...Object.fromEntries(Object.entries(draft).map(([key, value]) => [key, value.trim() || null])),
        nationality: draft.nationality,
      });
      try {
        if (Object.values(sensitive).some((value) => value.trim())) {
          await api.updatePersonSensitive(worker.id, Object.fromEntries(Object.entries(sensitive).map(([key, value]) => [key, value.trim().toUpperCase() || null])));
        }
        if (photo) await api.uploadPersonPhoto(worker.id, photo);
      } catch {
        notify("Trabajador creado con datos pendientes", { message: "Completa los datos fiscales o la fotografía desde su expediente.", tone: "info" });
        router.replace(`/people/${worker.id}`);
        return;
      }
      notify("Trabajador creado", { message: "Continúa en el expediente para registrar empleo, horario y nómina.", tone: "success" });
      router.replace(`/people/${worker.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState rows={8} />;
  return (
    <>
      <PageHeader title="Nuevo trabajador" description="Crea el expediente personal completo antes de asignar su empleo y horario." crumbs={[{ label: "Trabajadores", href: "/people" }, { label: "Nuevo trabajador" }]} actions={<Link href="/people"><Button variant="secondary" icon={<ArrowLeft className="h-4 w-4" />}>Volver</Button></Link>} />
      {error ? <div className="mb-5"><ErrorState error={error} onRetry={() => setError(null)} /></div> : null}
      <div className="grid gap-5 xl:grid-cols-[280px_1fr]">
        <Card className="h-fit p-5"><div className="flex items-center gap-3"><span className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><Camera className="h-5 w-5" /></span><div><p className="font-semibold text-zinc-800">Fotografía</p><p className="text-sm text-zinc-500">JPG, PNG o WebP; máximo 5 MB.</p></div></div><div className="mt-5 flex aspect-square items-center justify-center overflow-hidden rounded-2xl bg-zinc-100">{previewUrl ? <img src={previewUrl} alt="Vista previa del trabajador" className="h-full w-full object-cover" /> : <UserRound className="h-16 w-16 text-zinc-400" />}</div><div className="mt-4"><Field label="Archivo de fotografía">{(id) => <Input id={id} type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => choosePhoto(event.target.files?.[0])} />}</Field></div></Card>
        <div className="space-y-5">
          <Card className="p-5"><div className="flex items-center gap-3"><span className="rounded-xl bg-accent-50 p-2.5 text-accent-700"><UserRound className="h-5 w-5" /></span><div><p className="font-semibold text-zinc-800">Identidad y datos personales</p><p className="text-sm text-zinc-500">Los campos con nombre y apellido paterno son obligatorios.</p></div></div><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><Field label="Grupo corporativo">{(id) => <Select id={id} value={groupId} onChange={(event) => setGroupId(event.target.value)}><option value="">Selecciona</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</Select>}</Field><Field label="Nombre">{(id) => <Input id={id} value={draft.first_name} onChange={(event) => setValue("first_name", event.target.value)} required />}</Field><Field label="Apellido paterno">{(id) => <Input id={id} value={draft.last_name} onChange={(event) => setValue("last_name", event.target.value)} required />}</Field><Field label="Apellido materno">{(id) => <Input id={id} value={draft.second_last_name} onChange={(event) => setValue("second_last_name", event.target.value)} />}</Field><Field label="Nombre preferido">{(id) => <Input id={id} value={draft.preferred_name} onChange={(event) => setValue("preferred_name", event.target.value)} />}</Field><Field label="Fecha de nacimiento">{(id) => <Input id={id} type="date" value={draft.birth_date} onChange={(event) => setValue("birth_date", event.target.value)} />}</Field><Field label="Sexo">{(id) => <Select id={id} value={draft.sex} onChange={(event) => setValue("sex", event.target.value)}><option value="">Selecciona</option><option>Mujer</option><option>Hombre</option><option>No especificar</option></Select>}</Field><Field label="Nacionalidad">{(id) => <Select id={id} value={draft.nationality} onChange={(event) => setValue("nationality", event.target.value)}><option>Mexicana</option><option>Extranjera</option></Select>}</Field><Field label="Estado civil">{(id) => <Select id={id} value={draft.marital_status} onChange={(event) => setValue("marital_status", event.target.value)}><option value="">Selecciona</option><option>Soltero(a)</option><option>Casado(a)</option><option>Unión libre</option><option>Divorciado(a)</option><option>Viudo(a)</option><option>Separado(a)</option></Select>}</Field><Field label="Entidad de nacimiento">{(id) => <Select id={id} value={draft.birth_state} onChange={(event) => setValue("birth_state", event.target.value)}><option value="">Selecciona</option>{STATES.map((state) => <option key={state}>{state}</option>)}</Select>}</Field><Field label="Correo">{(id) => <Input id={id} type="email" value={draft.email} onChange={(event) => setValue("email", event.target.value)} />}</Field><Field label="Teléfono">{(id) => <Input id={id} type="tel" value={draft.phone} onChange={(event) => setValue("phone", event.target.value)} />}</Field></div></Card>
          <Card className="p-5"><p className="font-semibold text-zinc-800">Domicilio y contacto de emergencia</p><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><Field label="Calle">{(id) => <Input id={id} value={draft.address_street} onChange={(event) => setValue("address_street", event.target.value)} />}</Field><Field label="No. exterior">{(id) => <Input id={id} value={draft.address_ext_number} onChange={(event) => setValue("address_ext_number", event.target.value)} />}</Field><Field label="No. interior">{(id) => <Input id={id} value={draft.address_int_number} onChange={(event) => setValue("address_int_number", event.target.value)} />}</Field><Field label="Colonia">{(id) => <Input id={id} value={draft.address_neighborhood} onChange={(event) => setValue("address_neighborhood", event.target.value)} />}</Field><Field label="Municipio / alcaldía">{(id) => <Input id={id} value={draft.address_municipality} onChange={(event) => setValue("address_municipality", event.target.value)} />}</Field><Field label="Estado">{(id) => <Select id={id} value={draft.address_state} onChange={(event) => setValue("address_state", event.target.value)}><option value="">Selecciona</option>{STATES.map((state) => <option key={state}>{state}</option>)}</Select>}</Field><Field label="Código postal">{(id) => <Input id={id} inputMode="numeric" maxLength={10} value={draft.postal_code} onChange={(event) => setValue("postal_code", event.target.value)} />}</Field><Field label="Contacto de emergencia">{(id) => <Input id={id} value={draft.emergency_contact_name} onChange={(event) => setValue("emergency_contact_name", event.target.value)} />}</Field><Field label="Teléfono emergencia">{(id) => <Input id={id} type="tel" value={draft.emergency_contact_phone} onChange={(event) => setValue("emergency_contact_phone", event.target.value)} />}</Field><Field label="Parentesco">{(id) => <Select id={id} value={draft.emergency_contact_relationship} onChange={(event) => setValue("emergency_contact_relationship", event.target.value)}><option value="">Selecciona</option>{RELATIONSHIPS.map((relationship) => <option key={relationship}>{relationship}</option>)}</Select>}</Field></div></Card>
          <Card className="p-5"><p className="font-semibold text-zinc-800">Datos fiscales y seguridad social</p><p className="mt-1 text-sm text-zinc-500">Se cifran antes de almacenarse. Puedes completarlos ahora o desde el expediente.</p><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[["curp", "CURP"], ["rfc", "RFC"], ["nss", "NSS / IMSS"], ["fiscal_name", "Nombre fiscal"], ["tax_regime", "Régimen fiscal"], ["fiscal_postal_code", "CP fiscal"]].map(([key, label]) => <Field key={key} label={label}>{(id) => <Input id={id} value={sensitive[key]} onChange={(event) => setSensitive((current) => ({ ...current, [key]: event.target.value.toUpperCase() }))} />}</Field>)}</div></Card>
          <div className="flex justify-end"><Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={() => void save()} loading={saving} disabled={!groupId || !draft.first_name.trim() || !draft.last_name.trim()}>Crear trabajador</Button></div>
        </div>
      </div>
    </>
  );
}

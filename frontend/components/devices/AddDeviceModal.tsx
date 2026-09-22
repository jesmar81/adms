"use client";

import { Fingerprint, Plus, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import type { Site } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AddDeviceModal({ open, onClose, onRetry }: { open: boolean; onClose: () => void; onRetry: () => void }) {
  const [sites, setSites] = useState<Site[]>([]);
  const [serial, setSerial] = useState("");
  const [name, setName] = useState("");
  const [model, setModel] = useState("SpeedFace-V5L");
  const [siteId, setSiteId] = useState("");
  const [timezone, setTimezone] = useState("America/Mexico_City");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    void api.sites().then(setSites).catch(() => setSites([]));
  }, [open]);

  async function provision() {
    const normalized = serial.trim();
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(normalized)) {
      setError("El serial debe tener 1 a 64 caracteres: letras, números, guion o guion bajo.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.createDevice({
        serial_number: normalized,
        name: name.trim() || null,
        model: model.trim() || null,
        timezone,
        site_id: siteId || null,
      });
      setSerial("");
      setName("");
      setSiteId("");
      onRetry();
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No fue posible dar de alta el reloj.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Dar de alta un reloj"
      description="Autoriza el número de serie antes de conectarlo. Un equipo desconocido será rechazado."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            icon={<ShieldCheck className="h-4 w-4" aria-hidden />}
            onClick={() => void provision()}
            loading={saving}
            disabled={!serial.trim()}
          >
            Autorizar reloj
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Número de serie">
          {(id) => <Input id={id} value={serial} onChange={(event) => setSerial(event.target.value)} autoCapitalize="characters" placeholder="Ej. AEXX123456" />}
        </Field>
        <Field label="Nombre operativo">
          {(id) => <Input id={id} value={name} onChange={(event) => setName(event.target.value)} placeholder="Acceso principal" />}
        </Field>
        <Field label="Modelo">
          {(id) => <Input id={id} value={model} onChange={(event) => setModel(event.target.value)} />}
        </Field>
        <Field label="Sucursal">
          {(id) => <Select id={id} value={siteId} onChange={(event) => setSiteId(event.target.value)}><option value="">Sin asignar</option>{sites.filter((site) => site.active).map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</Select>}
        </Field>
        <div className="sm:col-span-2">
          <Field label="Zona horaria">
            {(id) => <Input id={id} value={timezone} onChange={(event) => setTimezone(event.target.value)} />}
          </Field>
        </div>
      </div>
      {error ? <p role="alert" className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      <p className="mt-4 rounded-xl bg-zinc-50 p-3 text-xs leading-relaxed text-zinc-600">
        Después del alta configura el servidor ADMS del reloj como <span className="font-mono">{API_URL}</span>. El estado cambiará cuando llegue su primera conexión real.
      </p>
    </Modal>
  );
}

export function AddDeviceButton({ onRetry }: { onRetry: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="primary" icon={<Plus className="h-4 w-4" aria-hidden />} onClick={() => setOpen(true)}>
        Agregar reloj
      </Button>
      <AddDeviceModal open={open} onClose={() => setOpen(false)} onRetry={onRetry} />
    </>
  );
}

export function NoDevicesEmpty({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line-soft bg-surface-card/50 px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-black/[0.04] text-zinc-500">
        <Fingerprint className="h-5 w-5" aria-hidden />
      </span>
      <h3 className="mt-4 text-[15px] font-semibold tracking-tight">Sin relojes registrados</h3>
      <p className="mt-1.5 max-w-sm text-sm text-zinc-500">
        Autoriza primero su número de serie y después conecta el SpeedFace al servidor ADMS.
      </p>
      <div className="mt-5">
        <AddDeviceButton onRetry={onRetry} />
      </div>
    </div>
  );
}

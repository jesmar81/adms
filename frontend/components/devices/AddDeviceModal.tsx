"use client";

import { Fingerprint, Plus, RotateCw } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function AddDeviceModal({ open, onClose, onRetry }: { open: boolean; onClose: () => void; onRetry: () => void }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Agregar un reloj"
      description="Los relojes se registran solos al comunicarse con la plataforma. No necesitas crearlos manualmente."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cerrar
          </Button>
          <Button
            variant="primary"
            icon={<RotateCw className="h-4 w-4" aria-hidden />}
            onClick={() => {
              onRetry();
              onClose();
            }}
          >
            Buscar de nuevo
          </Button>
        </>
      }
    >
      <ol className="flex flex-col gap-4 text-sm">
        {[
          {
            title: "Apunta el reloj al servidor ADMS",
            body: `En el menú del reloj (SpeedFace-V5LP): comunicación → servidor → ${API_URL}.`,
          },
          {
            title: "Espera el primer registro",
            body: "En cuanto el reloj envíe /iclock/registry aparecerá en la lista con estado inicial “Desconocido”.",
          },
          {
            title: "Verifica la comunicación",
            body: "Si no aparece, revisa que el reloj tenga red y que el servidor sea alcanzable desde su segmento.",
          },
        ].map((step, i) => (
          <li key={step.title} className="flex gap-3.5">
            <span
              aria-hidden
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[13px] font-semibold text-accent"
            >
              {i + 1}
            </span>
            <span>
              <span className="block font-medium">{step.title}</span>
              <span className="mt-0.5 block break-words text-[13px] leading-relaxed text-zinc-500">
                {step.body}
              </span>
            </span>
          </li>
        ))}
      </ol>
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
        Apunta un SpeedFace-V5LP a /iclock/* y aparecerá aquí automáticamente.
      </p>
      <div className="mt-5">
        <AddDeviceButton onRetry={onRetry} />
      </div>
    </div>
  );
}

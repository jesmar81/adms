import type { ReactNode } from "react";

export type Tone = "emerald" | "amber" | "red" | "zinc" | "sky";

const TONES: Record<Tone, string> = {
  emerald: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  amber: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  red: "border-rose-500/25 bg-rose-500/10 text-rose-300",
  zinc: "border-line-subtle bg-surface-raised text-muted",
  sky: "border-accent/25 bg-accent-soft text-accent",
};

export function Badge({ tone = "zinc", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

const DOT_COLORS: Record<Tone, string> = {
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
  zinc: "bg-zinc-400",
  sky: "bg-accent",
};

/** Etiquetas en español para cada estado conocido de la API. */
const STATUS_META: Record<string, { tone: Tone; label: string; pulse?: boolean }> = {
  online: { tone: "emerald", label: "En línea", pulse: true },
  offline: { tone: "amber", label: "Sin conexión" },
  stale: { tone: "amber", label: "Inactivo" },
  unknown: { tone: "zinc", label: "Desconocido" },
  disabled: { tone: "red", label: "Deshabilitado" },
  pending: { tone: "amber", label: "Pendiente" },
  sent: { tone: "sky", label: "Enviado" },
  confirmed: { tone: "emerald", label: "Confirmado" },
  failed: { tone: "red", label: "Fallido" },
  expired: { tone: "zinc", label: "Expirado" },
  cancelled: { tone: "zinc", label: "Cancelado" },
  synced: { tone: "emerald", label: "Sincronizado" },
};

export function statusMeta(status: string): { tone: Tone; label: string; pulse?: boolean } {
  return STATUS_META[status] ?? { tone: "zinc", label: status };
}

/** Punto de estado + etiqueta. Representación única de estados en toda la app. */
export function StatusDot({ status, showLabel = true }: { status: string; showLabel?: boolean }) {
  const meta = statusMeta(status);
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-sm">
      <span className="relative flex h-2 w-2">
        {meta.pulse && (
          <span
            aria-hidden
            className={`absolute inline-flex h-full w-full animate-pulse-dot rounded-full ${DOT_COLORS[meta.tone]}`}
          />
        )}
        <span
          aria-hidden
          className={`relative inline-flex h-2 w-2 rounded-full ${DOT_COLORS[meta.tone]}`}
        />
      </span>
      {showLabel && <span className="text-foreground">{meta.label}</span>}
    </span>
  );
}

"use client";

import { AlertTriangle, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { Button } from "./button";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-line-soft bg-surface-card/70 px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-raised text-muted">
        {icon ?? <Inbox className="h-5 w-5" aria-hidden />}
      </span>
      <h3 className="mt-4 text-[15px] font-semibold tracking-tight text-foreground">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-xl bg-surface-raised ${className}`}>
      <span aria-hidden className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </div>
  );
}

export function LoadingState({ rows = 5 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Cargando" className="flex flex-col gap-2.5">
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonBlock key={i} className="h-14" />
      ))}
      <span className="sr-only">Cargando…</span>
    </div>
  );
}

export function StatSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonBlock key={i} className="h-[118px] rounded-2xl" />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  let message = "Ocurrió un error inesperado.";
  let status: number | undefined;
  if (error instanceof ApiError) {
    status = error.status;
    message =
      error.status === 429
        ? `Demasiados intentos.${error.retryAfter ? ` Reintenta en ${error.retryAfter}s.` : ""}`
        : error.status === 503
          ? "Servicio no disponible. Inténtalo de nuevo en un momento."
          : error.message;
  } else if (error instanceof Error) {
    message = error.message;
  }
  return (
    <div className="flex flex-col items-center rounded-xl border border-rose-500/25 bg-rose-500/10 px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-rose-500/15 text-rose-300">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </span>
      <h3 className="mt-4 text-[15px] font-semibold tracking-tight text-foreground">
        Algo salió mal{status ? ` (error ${status})` : ""}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-muted">{message}</p>
      {onRetry && (
        <div className="mt-5">
          <Button onClick={onRetry}>Reintentar</Button>
        </div>
      )}
    </div>
  );
}

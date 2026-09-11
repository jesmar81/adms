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
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line-soft bg-white/70 px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-black/[0.04] text-zinc-500">
        {icon ?? <Inbox className="h-5 w-5" aria-hidden />}
      </span>
      <h3 className="mt-4 text-[15px] font-semibold tracking-tight text-zinc-900">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-zinc-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-xl bg-black/[0.06] ${className}`}>
      <span aria-hidden className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/60 to-transparent" />
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
    <div className="flex flex-col items-center rounded-2xl border border-red-200 bg-red-50 px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-red-600">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </span>
      <h3 className="mt-4 text-[15px] font-semibold tracking-tight text-zinc-900">
        Algo salió mal{status ? ` (error ${status})` : ""}
      </h3>
      <p className="mt-1.5 max-w-sm text-sm text-zinc-500">{message}</p>
      {onRetry && (
        <div className="mt-5">
          <Button onClick={onRetry}>Reintentar</Button>
        </div>
      )}
    </div>
  );
}

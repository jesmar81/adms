"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="py-6 text-center text-slate-400">{label}</p>;
}

export function Empty({ label }: { label: string }) {
  return <p className="rounded border border-slate-800 bg-slate-900 p-4 text-center text-slate-400">{label}</p>;
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError
      ? `${error.message} (${error.code}${error.status === 429 && error.retryAfter ? `, retry in ${error.retryAfter}s` : ""})`
      : error instanceof Error
        ? error.message
        : "Unexpected error";
  const status = error instanceof ApiError ? error.status : undefined;
  return (
    <div className="rounded border border-red-800 bg-red-950 p-3 text-sm text-red-200">
      <strong>Error{status ? ` ${status}` : ""}:</strong> {message}
      {onRetry && (
        <button onClick={onRetry} className="ml-3 underline">
          Retry
        </button>
      )}
    </div>
  );
}

export function Pagination({
  offset,
  limit,
  hasMore,
  onPage,
}: {
  offset: number;
  limit: number;
  hasMore: boolean;
  onPage: (offset: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center gap-3 text-sm">
      <button
        disabled={offset === 0}
        onClick={() => onPage(Math.max(0, offset - limit))}
        className="rounded border border-slate-700 px-3 py-1 disabled:opacity-40"
      >
        ← Prev
      </button>
      <span className="text-slate-400">
        Showing {offset + 1}–{offset + limit}
      </span>
      <button
        disabled={!hasMore}
        onClick={() => onPage(offset + limit)}
        className="rounded border border-slate-700 px-3 py-1 disabled:opacity-40"
      >
        Next →
      </button>
    </div>
  );
}

export function Badge({ tone, children }: { tone: "green" | "red" | "yellow" | "gray"; children: ReactNode }) {
  const colors = {
    green: "border-green-700 bg-green-950 text-green-200",
    red: "border-red-700 bg-red-950 text-red-200",
    yellow: "border-yellow-700 bg-yellow-950 text-yellow-200",
    gray: "border-slate-700 bg-slate-900 text-slate-300",
  } as const;
  return (
    <span className={`rounded border px-2 py-0.5 text-xs ${colors[tone]}`}>{children}</span>
  );
}

export function statusTone(status: string): "green" | "red" | "yellow" | "gray" {
  if (["online", "confirmed", "synced"].includes(status)) return "green";
  if (["failed", "disabled"].includes(status)) return "red";
  if (["pending", "stale", "offline"].includes(status)) return "yellow";
  return "gray";
}

export function Shell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="mx-auto max-w-6xl p-6">
      <nav className="mb-6 flex flex-wrap gap-4 text-sm text-sky-400">
        <Link href="/dashboard">Dashboard</Link>
        <Link href="/devices">Devices</Link>
        <Link href="/attendance">Attendance</Link>
        <Link href="/device-users">Device users</Link>
        <Link href="/commands">Commands</Link>
        <Link href="/users">Users</Link>
        <Link href="/audit">Audit</Link>
      </nav>
      <h1 className="mb-4 text-2xl font-bold">{title}</h1>
      {children}
    </main>
  );
}

export const inputCls =
  "rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-100";

export const btnCls = "rounded bg-sky-700 px-3 py-1.5 text-sm font-medium hover:bg-sky-600";

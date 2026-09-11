"use client";

import { ArrowRight, Clock, Fingerprint, Terminal, Wifi, WifiOff } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime, formatNumber, greeting } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { StatusDot } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, StatCard } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { ErrorState, LoadingState, EmptyState, StatSkeleton } from "@/components/ui/states";
import type { AttendanceRow, Device, DeviceCommand } from "@/types";

interface Summary {
  total: number;
  online: number;
  offline: number;
  pending_commands: number;
  failed_commands: number;
}

export default function Page() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [recent, setRecent] = useState<AttendanceRow[]>([]);
  const [pending, setPending] = useState<DeviceCommand[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, d, r, p] = await Promise.all([
        api.summary(),
        api.devices(),
        api.attendance({ limit: "10" }),
        api.commands("pending"),
      ]);
      setSummary({
        total: s.total ?? 0,
        online: s.online ?? 0,
        offline: s.offline ?? 0,
        pending_commands: s.pending_commands ?? 0,
        failed_commands: s.failed_commands ?? 0,
      });
      setDevices(d.slice(0, 5));
      setRecent(r);
      setPending(p.slice(0, 6));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        title={`${greeting()}${user ? `, ${user.username}` : ""}`}
        description="Resumen del estado de tus relojes checadores y la actividad reciente."
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void load()} />
      ) : loading || !summary ? (
        <StatSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Relojes"
            value={formatNumber(summary.total)}
            sub="Dispositivos registrados"
            icon={<Fingerprint className="h-5 w-5" aria-hidden />}
          />
          <StatCard
            label="En línea"
            value={formatNumber(summary.online)}
            sub="Comunicación activa"
            icon={<Wifi className="h-5 w-5" aria-hidden />}
            iconTone="bg-emerald-50 text-emerald-700"
          />
          <StatCard
            label="Fuera de línea"
            value={formatNumber(summary.offline)}
            sub="Sin comunicación reciente"
            icon={<WifiOff className="h-5 w-5" aria-hidden />}
            iconTone="bg-amber-50 text-amber-700"
          />
          <StatCard
            label="Comandos pendientes"
            value={formatNumber(summary.pending_commands)}
            sub={`${formatNumber(summary.failed_commands)} fallidos`}
            icon={<Terminal className="h-5 w-5" aria-hidden />}
            iconTone="bg-violet-50 text-violet-700"
          />
        </div>
      )}

      {!error && (
        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-5">
          <Card className="p-5 md:p-6 xl:col-span-3">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-[15px] font-semibold tracking-tight">Estado de dispositivos</h2>
                <p className="mt-0.5 text-[13px] text-zinc-500">Última comunicación conocida</p>
              </div>
              <Link
                href="/devices"
                className="inline-flex items-center gap-1 text-[13px] font-medium text-accent transition-colors hover:text-accent-hover"
              >
                Ver todos <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Link>
            </div>
            {loading ? (
              <LoadingState rows={4} />
            ) : devices.length === 0 ? (
              <EmptyState
                title="Sin relojes registrados"
                description="Apunta un SpeedFace-V5LP a /iclock/* para que aparezca aquí."
                action={
                  <Link href="/devices">
                    <Button size="sm">Ver relojes</Button>
                  </Link>
                }
              />
            ) : (
              <ul className="flex flex-col divide-y divide-line-subtle">
                {devices.map((d) => (
                  <li key={d.id}>
                    <Link
                      href={`/devices/${d.id}`}
                      className="flex items-center justify-between gap-3 rounded-lg px-2 py-3 transition-colors duration-150 hover:bg-black/[0.03]"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">
                          {d.name ?? d.serial_number}
                        </span>
                        <span className="mt-0.5 block truncate font-mono text-xs text-zinc-500">
                          {d.serial_number} · {d.ip_address ?? "sin IP"}
                        </span>
                      </span>
                      <StatusDot status={d.derived_status ?? d.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="flex flex-col gap-4 xl:col-span-2">
            <Card className="p-5 md:p-6">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-[15px] font-semibold tracking-tight">Actividad reciente</h2>
                <Link
                  href="/attendance"
                  className="inline-flex items-center gap-1 text-[13px] font-medium text-accent transition-colors hover:text-accent-hover"
                >
                  Ver todo <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              </div>
              {loading ? (
                <LoadingState rows={3} />
              ) : recent.length === 0 ? (
                <p className="py-4 text-center text-sm text-zinc-500">Aún no hay marcaciones.</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {recent.slice(0, 5).map((r) => (
                    <li key={r.id} className="flex items-center gap-3 text-sm">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-black/[0.04] text-zinc-500">
                        <Clock className="h-4 w-4" aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium tabular-nums">
                          PIN {r.device_user_pin}
                        </span>
                        <span className="block truncate text-xs text-zinc-500">
                          {formatDateTime(r.recorded_at)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-5 md:p-6">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-[15px] font-semibold tracking-tight">Comandos pendientes</h2>
                <Link
                  href="/commands"
                  className="inline-flex items-center gap-1 text-[13px] font-medium text-accent transition-colors hover:text-accent-hover"
                >
                  Ver todos <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              </div>
              {loading ? (
                <LoadingState rows={2} />
              ) : pending.length === 0 ? (
                <p className="py-4 text-center text-sm text-zinc-500">Sin comandos en cola.</p>
              ) : (
                <ul className="flex flex-col gap-2.5">
                  {pending.map((c) => (
                    <li key={c.id} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate font-mono text-[13px] text-zinc-600">
                        #{c.protocol_command_id} · {c.command_type}
                      </span>
                      <StatusDot status={c.status} />
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}

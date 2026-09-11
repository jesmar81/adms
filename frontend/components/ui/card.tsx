import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`rounded-2xl border border-line-subtle bg-surface-card shadow-card ${className}`}
    >
      {children}
    </section>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: ReactNode;
  iconTone?: string;
}

export function StatCard({ label, value, sub, icon, iconTone = "bg-accent-soft text-accent" }: StatCardProps) {
  return (
    <Card className="p-5 transition-colors duration-200 hover:border-line-soft">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-zinc-500">{label}</p>
          <p className="mt-1.5 text-[28px] font-semibold leading-none tracking-tight text-zinc-900 tabular-nums">
            {value}
          </p>
          {sub && <p className="mt-1.5 truncate text-xs text-zinc-400">{sub}</p>}
        </div>
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconTone}`}>
          {icon}
        </span>
      </div>
    </Card>
  );
}

import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section
      className={`relative overflow-hidden rounded-[10px] border border-line-subtle bg-surface-card/85 shadow-card backdrop-blur-sm ${className}`}
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
    <Card className="group p-4 transition-all duration-150 hover:-translate-y-px hover:border-line-soft hover:shadow-glow">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-semibold uppercase tracking-[0.11em] text-muted">{label}</p>
          <p className="mt-1.5 font-mono text-[26px] font-bold leading-none tracking-tight text-foreground tabular-nums">
            {value}
          </p>
          {sub && <p className="mt-1.5 truncate text-[11px] text-muted">{sub}</p>}
        </div>
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-white/5 ${iconTone}`}>
          {icon}
        </span>
      </div>
    </Card>
  );
}

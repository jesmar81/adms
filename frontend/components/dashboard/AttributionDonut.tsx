"use client";

import { useMemo, useState } from "react";

export interface AttributionSegment {
  label: string;
  value: number;
  color: string;
}

export function AttributionDonut({ data }: { data: AttributionSegment[] }) {
  const [active, setActive] = useState<number | null>(null);
  const total = data.reduce((sum, item) => sum + item.value, 0);
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const segments = useMemo(() => {
    let cumulative = 0;
    return data.map((item) => {
      const percentage = total ? (item.value / total) * 100 : 0;
      const dash = Math.max(0, (percentage / 100) * circumference - (data.filter((row) => row.value > 0).length > 1 ? 4 : 0));
      const segment = { ...item, percentage: Math.round(percentage), dash, offset: -(cumulative / 100) * circumference };
      cumulative += percentage;
      return segment;
    });
  }, [data, total, circumference]);
  const selected = active === null ? null : segments[active];
  return (
    <div className="flex items-center gap-5">
      <div className="relative h-[146px] w-[146px] shrink-0"><svg viewBox="0 0 160 160" className="h-full w-full -rotate-90"><circle cx="80" cy="80" r={radius} fill="none" stroke="currentColor" strokeWidth="18" className="text-muted/15" />{segments.map((segment, index) => segment.value > 0 && <circle key={segment.label} cx="80" cy="80" r={radius} fill="none" stroke={segment.color} strokeWidth={active === index ? 22 : 18} strokeLinecap="round" strokeDasharray={`${segment.dash} ${circumference - segment.dash}`} strokeDashoffset={segment.offset} className="cursor-pointer transition-all duration-200" style={{ opacity: active !== null && active !== index ? 0.35 : 1 }} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} />)}</svg><div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><span className="font-mono text-2xl font-bold text-foreground">{selected ? `${selected.percentage}%` : total}</span><span className="mt-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">{selected ? selected.label : "checadas"}</span></div></div>
      <ul className="min-w-0 flex-1 space-y-2">{segments.map((segment, index) => <li key={segment.label} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} className={`flex cursor-default items-center justify-between gap-2 rounded-md border px-2.5 py-1.5 text-xs transition-colors ${active === index ? "border-line-soft bg-surface-raised" : "border-transparent"}`}><span className="flex min-w-0 items-center gap-2"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: segment.color }} /><span className="truncate text-muted">{segment.label}</span></span><span className="font-mono font-semibold text-foreground">{segment.value}</span></li>)}</ul>
    </div>
  );
}

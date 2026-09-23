"use client";

import { CalendarDays } from "lucide-react";
import { useId, useMemo, useState } from "react";

export interface TrendPoint {
  label: string;
  date: string;
  count: number;
}

export function AttendanceTrend({ data }: { data: TrendPoint[] }) {
  const [active, setActive] = useState<number | null>(null);
  const gradientId = useId().replace(/:/g, "");
  const { points, linePath, areaPath, max } = useMemo(() => {
    const width = 640;
    const height = 202;
    const left = 30;
    const right = 16;
    const top = 16;
    const bottom = 32;
    const chartWidth = width - left - right;
    const chartHeight = height - top - bottom;
    const maximum = Math.max(1, ...data.map((item) => item.count));
    const chartPoints = data.map((item, index) => ({
      ...item,
      x: data.length > 1 ? left + (index / (data.length - 1)) * chartWidth : width / 2,
      y: top + chartHeight - (item.count / maximum) * chartHeight,
    }));
    const path = chartPoints.reduce((result, point, index, list) => {
      if (!index) return `M ${point.x} ${point.y}`;
      const previous = list[index - 1];
      const middle = previous.x + (point.x - previous.x) / 2;
      return `${result} C ${middle} ${previous.y}, ${middle} ${point.y}, ${point.x} ${point.y}`;
    }, "");
    const area = chartPoints.length ? `${path} L ${chartPoints[chartPoints.length - 1].x} ${height - bottom} L ${chartPoints[0].x} ${height - bottom} Z` : "";
    return { points: chartPoints, linePath: path, areaPath: area, max: maximum };
  }, [data]);

  if (!data.length || !data.some((point) => point.count)) {
    return <div className="flex h-[218px] flex-col items-center justify-center gap-2 text-center text-sm text-muted"><CalendarDays className="h-7 w-7 text-muted/60" aria-hidden /><span>Aún no hay checadas para visualizar en los últimos siete días.</span></div>;
  }

  const selected = active === null ? null : points[active];
  return (
    <div className="relative h-[238px]">
      <svg viewBox="0 0 640 202" className="h-[202px] w-full overflow-visible" preserveAspectRatio="none" role="img" aria-label="Tendencia de checadas de los últimos siete días">
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity="0.34" /><stop offset="100%" stopColor="#3b82f6" stopOpacity="0" /></linearGradient>
        </defs>
        {[0, 0.5, 1].map((fraction) => { const y = 16 + (1 - fraction) * 154; return <line key={fraction} x1="30" x2="624" y1={y} y2={y} stroke="currentColor" strokeDasharray="4 5" className="text-muted/20" />; })}
        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path d={linePath} fill="none" stroke="#60a5fa" strokeWidth="2.5" strokeLinecap="round" />
        {points.map((point, index) => <g key={point.date} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} className="cursor-pointer"><rect x={point.x - 38} y="0" width="76" height="185" fill="transparent" /><circle cx={point.x} cy={point.y} r={active === index ? 6 : 4} fill="#60a5fa" stroke="#121215" strokeWidth="2" /><text x={point.x} y="197" textAnchor="middle" className="fill-current text-[10px] font-mono text-muted">{point.label}</text></g>)}
      </svg>
      <div className="absolute left-0 top-0 rounded-md border border-line-subtle bg-surface-raised/80 px-2 py-1 font-mono text-[10px] text-muted">máx. {max} checadas</div>
      {selected && <div className="absolute right-0 top-0 rounded-lg border border-line-soft bg-surface-card/95 px-3 py-2 shadow-pop backdrop-blur-sm"><p className="text-[11px] font-medium text-foreground">{selected.date}</p><p className="mt-0.5 font-mono text-xs text-accent">{selected.count} checadas</p></div>}
    </div>
  );
}

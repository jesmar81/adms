import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Calendar, CheckCircle2, TrendingUp, AlertTriangle } from 'lucide-react';

export interface WeeklyTrendDay {
  date: string;
  day: string;
  punches: number;
  punctualityRate: number;
  onTime: number;
  late: number;
  absences: number;
  incidents: number;
  evaluated: number;
}

interface WeeklyTrendChartProps {
  data: WeeklyTrendDay[];
  className?: string;
}

export const WeeklyTrendChart: React.FC<WeeklyTrendChartProps> = ({
  data = [],
  className,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground text-xs">
        <Calendar className="w-8 h-8 mb-2 opacity-40" />
        <span>Sin registros de los últimos 7 días</span>
      </div>
    );
  }

  // Totals & averages
  const totalWeeklyPunches = data.reduce((acc, d) => acc + d.punches, 0);
  const evaluatedDays = data.filter((d) => d.evaluated > 0);
  const avgPunctuality =
    evaluatedDays.length > 0
      ? Math.round(
          evaluatedDays.reduce((acc, d) => acc + d.punctualityRate, 0) /
            evaluatedDays.length
        )
      : 100;

  // Max scale for punch bars
  const maxPunches = Math.max(1, ...data.map((d) => d.punches));

  // SVG dimensions for the punctuality line curve
  const width = 600;
  const height = 180;
  const paddingX = 40;
  const paddingBottom = 30;
  const paddingTop = 20;
  const chartHeight = height - paddingTop - paddingBottom;
  const chartWidth = width - paddingX * 2;

  const points = data.map((d, index) => {
    const x =
      data.length > 1
        ? paddingX + (index / (data.length - 1)) * chartWidth
        : width / 2;
    // Punctuality rate goes from 0 to 100
    const y = paddingTop + chartHeight - (d.punctualityRate / 100) * chartHeight;
    return { x, y, data: d, index };
  });

  // Generate SVG path for the punctuality curve
  const linePath = points.reduce((acc, point, i, arr) => {
    if (i === 0) return `M ${point.x},${point.y}`;
    const prev = arr[i - 1];
    const cp1x = prev.x + (point.x - prev.x) / 2;
    const cp1y = prev.y;
    const cp2x = prev.x + (point.x - prev.x) / 2;
    const cp2y = point.y;
    return `${acc} C ${cp1x},${cp1y} ${cp2x},${cp2y} ${point.x},${point.y}`;
  }, '');

  // Fill area under line
  const areaPath =
    points.length > 0
      ? `${linePath} L ${points[points.length - 1].x},${
          height - paddingBottom
        } L ${points[0].x},${height - paddingBottom} Z`
      : '';

  const hoveredDay = hoveredIndex !== null ? data[hoveredIndex] : null;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Top summary badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-medium text-muted-foreground">
            Últimos 7 días naturales
          </span>
        </div>

        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="font-semibold font-mono">{totalWeeklyPunches}</span>
            <span className="text-[11px] opacity-80">checadas</span>
          </div>

          <div className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span className="font-semibold font-mono">{avgPunctuality}%</span>
            <span className="text-[11px] opacity-80">promedio</span>
          </div>
        </div>
      </div>

      {/* Main SVG Visualization */}
      <div className="relative w-full flex-1 flex flex-col justify-end">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-44 overflow-visible"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
              <stop offset="85%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.3" />
            </linearGradient>
          </defs>

          {/* Grid horizontal guidelines */}
          {[0, 50, 100].map((pct) => {
            const y = paddingTop + chartHeight - (pct / 100) * chartHeight;
            return (
              <g key={pct}>
                <line
                  x1={paddingX}
                  y1={y}
                  x2={width - paddingX}
                  y2={y}
                  stroke="currentColor"
                  strokeDasharray="4 4"
                  className="text-border/40"
                  strokeWidth="1"
                />
                <text
                  x={paddingX - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="text-[9px] fill-muted-foreground font-mono"
                >
                  {pct}%
                </text>
              </g>
            );
          })}

          {/* Punch Volume Bars (Underneath curve) */}
          {data.map((d, index) => {
            const barWidth = 24;
            const xCenter =
              data.length > 1
                ? paddingX + (index / (data.length - 1)) * chartWidth
                : width / 2;
            const barX = xCenter - barWidth / 2;
            const barMaxHeight = chartHeight * 0.7; // Max height inside chart
            const barHeight =
              maxPunches > 0 ? (d.punches / maxPunches) * barMaxHeight : 0;
            const barY = height - paddingBottom - barHeight;

            const isHovered = hoveredIndex === index;

            return (
              <g
                key={d.date}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Clickable transparent target area */}
                <rect
                  x={xCenter - chartWidth / (data.length * 2)}
                  y={paddingTop}
                  width={chartWidth / data.length}
                  height={chartHeight}
                  fill="transparent"
                />

                {/* Punch Bar */}
                {barHeight > 0 && (
                  <rect
                    x={barX}
                    y={barY}
                    width={barWidth}
                    height={barHeight}
                    rx="4"
                    fill="url(#barGradient)"
                    className={cn(
                      'transition-all duration-200',
                      isHovered ? 'brightness-125' : 'opacity-80'
                    )}
                  />
                )}

                {/* Day label */}
                <text
                  x={xCenter}
                  y={height - 10}
                  textAnchor="middle"
                  className={cn(
                    'text-[10px] font-mono transition-colors',
                    isHovered
                      ? 'fill-foreground font-semibold'
                      : 'fill-muted-foreground'
                  )}
                >
                  {d.day}
                </text>
              </g>
            );
          })}

          {/* Area under curve */}
          <path d={areaPath} fill="url(#areaGradient)" />

          {/* Curve path */}
          <path
            d={linePath}
            fill="none"
            stroke="#10b981"
            strokeWidth="2.5"
            strokeLinecap="round"
            className="filter drop-shadow-sm"
          />

          {/* Point dots */}
          {points.map((pt) => {
            const isHovered = hoveredIndex === pt.index;
            return (
              <g
                key={pt.index}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIndex(pt.index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#34d399' : '#10b981'}
                  stroke="#09090b"
                  strokeWidth="2"
                  className="transition-all duration-200"
                />
                {isHovered && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={10}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="1.5"
                    opacity="0.6"
                    className="animate-ping origin-center"
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredDay && (
          <div className="absolute top-0 right-0 bg-popover/95 backdrop-blur-md text-popover-foreground text-xs py-2 px-3 rounded-lg border border-border shadow-xl font-mono z-20 pointer-events-none min-w-[190px]">
            <div className="flex items-center justify-between pb-1.5 border-b border-border/50 font-sans">
              <span className="font-semibold text-foreground text-[11px]">
                {hoveredDay.day} ({hoveredDay.date})
              </span>
              <span className="text-[10px] text-emerald-400 font-mono font-bold">
                {hoveredDay.punctualityRate}% punt.
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 pt-1.5 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Checadas:</span>
                <span className="font-bold text-foreground">{hoveredDay.punches}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-emerald-400">A tiempo:</span>
                <span className="font-bold">{hoveredDay.onTime}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-amber-400">Retardos:</span>
                <span className="font-bold">{hoveredDay.late}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-rose-400">Ausencias:</span>
                <span className="font-bold">{hoveredDay.absences}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Chart Legend */}
      <div className="flex items-center justify-center space-x-6 pt-3 text-xs text-muted-foreground border-t border-border/40 mt-2">
        <div className="flex items-center space-x-1.5">
          <div className="h-2.5 w-2.5 rounded-xs bg-primary/80" />
          <span>Volumen de Checadas</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <span>Línea de Puntualidad (%)</span>
        </div>
      </div>
    </div>
  );
};

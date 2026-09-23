import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { CheckCircle2, AlertCircle } from 'lucide-react';

export interface BreakdownItem {
  name: string;
  count: number;
  color: string;
  percentage: number;
}

interface DonutChartProps {
  data: BreakdownItem[];
  title?: string;
  subtitle?: string;
  centerMetric?: {
    value: string | number;
    label: string;
  };
  className?: string;
}

export const DonutChart: React.FC<DonutChartProps> = ({
  data = [],
  title = 'Desglose de Asistencia',
  subtitle = 'Estado de evaluaciones del turno actual',
  centerMetric,
  className,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const totalCount = data.reduce((acc, curr) => acc + curr.count, 0);

  // SVG parameters
  const size = 200;
  const strokeWidth = 22;
  const radius = 70;
  const circumference = 2 * Math.PI * radius; // ~439.82
  const center = size / 2;

  let cumulativePercent = 0;

  // Render segments
  const segments = data.map((item, index) => {
    const isZero = totalCount === 0 || item.percentage === 0;
    const strokeDash = isZero ? 0 : (item.percentage / 100) * circumference;
    const gap = data.filter(d => d.count > 0).length > 1 ? 4 : 0;
    const adjustedDash = Math.max(0, strokeDash - gap);
    const strokeDashoffset = -((cumulativePercent / 100) * circumference);

    cumulativePercent += item.percentage;

    const isHovered = hoveredIndex === index;

    return {
      ...item,
      strokeDasharray: `${adjustedDash} ${circumference - adjustedDash}`,
      strokeDashoffset,
      isHovered,
      index,
    };
  });

  const activeItem = hoveredIndex !== null ? data[hoveredIndex] : null;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Title Header */}
      {(title || subtitle) && (
        <div className="mb-3">
          {title && (
            <h3 className="text-sm font-semibold text-foreground tracking-tight">
              {title}
            </h3>
          )}
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
          )}
        </div>
      )}

      {/* Main Chart and Legend Area */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-6 flex-1 py-2">
        {/* SVG Donut */}
        <div className="relative flex items-center justify-center w-[180px] h-[180px] shrink-0">
          <svg
            viewBox={`0 0 ${size} ${size}`}
            className="w-full h-full transform -rotate-90"
          >
            {/* Background track circle */}
            <circle
              cx={center}
              cy={center}
              r={radius}
              fill="transparent"
              stroke="currentColor"
              strokeWidth={strokeWidth}
              className="text-muted/30"
            />

            {/* Empty state single ring if totalCount is 0 */}
            {totalCount === 0 && (
              <circle
                cx={center}
                cy={center}
                r={radius}
                fill="transparent"
                stroke="currentColor"
                strokeWidth={strokeWidth}
                strokeDasharray={`${circumference} 0`}
                className="text-muted/50"
              />
            )}

            {/* Segments */}
            {totalCount > 0 &&
              segments.map((seg) => {
                if (seg.count <= 0) return null;
                return (
                  <circle
                    key={seg.name}
                    cx={center}
                    cy={center}
                    r={radius}
                    fill="transparent"
                    stroke={seg.color}
                    strokeWidth={seg.isHovered ? strokeWidth + 4 : strokeWidth}
                    strokeDasharray={seg.strokeDasharray}
                    strokeDashoffset={seg.strokeDashoffset}
                    strokeLinecap="round"
                    className="transition-all duration-300 cursor-pointer origin-center hover:opacity-100"
                    style={{
                      opacity: hoveredIndex !== null && !seg.isHovered ? 0.35 : 1,
                      filter: seg.isHovered ? `drop-shadow(0 0 6px ${seg.color})` : 'none',
                    }}
                    onMouseEnter={() => setHoveredIndex(seg.index)}
                    onMouseLeave={() => setHoveredIndex(null)}
                  />
                );
              })}
          </svg>

          {/* Central Callout */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none px-2">
            {activeItem ? (
              <div className="animate-in fade-in zoom-in-95 duration-150">
                <span
                  className="text-2xl font-bold font-mono tracking-tight"
                  style={{ color: activeItem.color }}
                >
                  {activeItem.percentage}%
                </span>
                <span className="block text-[11px] font-medium text-foreground max-w-[90px] truncate">
                  {activeItem.name}
                </span>
                <span className="block text-[10px] text-muted-foreground font-mono">
                  {activeItem.count} {activeItem.count === 1 ? 'colab.' : 'colabs.'}
                </span>
              </div>
            ) : centerMetric ? (
              <div>
                <span className="text-2xl font-bold font-mono text-foreground tracking-tight">
                  {centerMetric.value}
                </span>
                <span className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  {centerMetric.label}
                </span>
              </div>
            ) : (
              <div>
                <span className="text-2xl font-bold font-mono text-foreground tracking-tight">
                  {totalCount}
                </span>
                <span className="block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Evaluados
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Legend List */}
        <div className="flex flex-col gap-2 w-full max-w-[200px]">
          {data.map((item, idx) => {
            const isHovered = hoveredIndex === idx;
            return (
              <div
                key={item.name}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                className={cn(
                  'flex items-center justify-between p-1.5 rounded-md transition-colors cursor-pointer text-xs border border-transparent',
                  isHovered
                    ? 'bg-muted/60 border-border/60 shadow-xs'
                    : 'hover:bg-muted/30'
                )}
              >
                <div className="flex items-center space-x-2 min-w-0">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0 transition-transform"
                    style={{
                      backgroundColor: item.color,
                      transform: isHovered ? 'scale(1.3)' : 'scale(1)',
                    }}
                  />
                  <span className="truncate font-medium text-foreground text-[12px]">
                    {item.name}
                  </span>
                </div>
                <div className="flex items-center space-x-1.5 shrink-0 pl-2">
                  <span className="font-mono text-xs font-semibold text-foreground">
                    {item.count}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    ({item.percentage}%)
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

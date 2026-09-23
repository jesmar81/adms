import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Flame, Clock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface HourlyPunchItem {
  hour: string;
  count: number;
  onTime: number;
  late: number;
}

interface HourlyPunchChartProps {
  data: HourlyPunchItem[];
  peakHour?: string;
  className?: string;
}

export const HourlyPunchChart: React.FC<HourlyPunchChartProps> = ({
  data = [],
  peakHour,
  className,
}) => {
  const [hoveredHour, setHoveredHour] = useState<HourlyPunchItem | null>(null);

  // Dynamic max count for proportional scaling
  const maxCount = Math.max(1, ...data.map((item) => item.count));
  const totalPunches = data.reduce((acc, curr) => acc + curr.count, 0);

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Subheader with peak hour and stats */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="text-xs text-muted-foreground">
          {totalPunches === 0
            ? 'Sin checadas registradas en el día'
            : `${totalPunches} checadas registradas hoy`}
        </div>

        {peakHour && totalPunches > 0 && (
          <Badge
            variant="outline"
            className="flex items-center gap-1 text-[11px] font-mono bg-amber-500/10 text-amber-400 border-amber-500/20"
          >
            <Flame className="w-3 h-3 text-amber-400 animate-pulse" />
            <span>Pico: {peakHour} hrs</span>
          </Badge>
        )}
      </div>

      {/* Bar Chart Container */}
      <div className="relative flex-1 flex flex-col justify-end">
        <div className="h-56 w-full flex items-end justify-between gap-1.5 pt-6 pb-2 px-1 border-b border-border/60">
          {data.map((item) => {
            const isPeak = peakHour && item.hour === peakHour && item.count > 0;
            // Height proportional to maximum count
            const heightPercent =
              item.count > 0
                ? Math.min(100, Math.max(12, (item.count / maxCount) * 100))
                : 4;

            const onTimePercent =
              item.count > 0 ? (item.onTime / item.count) * 100 : 100;
            const latePercent = 100 - onTimePercent;

            return (
              <div
                key={item.hour}
                className="flex-1 flex flex-col items-center h-full justify-end group relative"
                onMouseEnter={() => setHoveredHour(item)}
                onMouseLeave={() => setHoveredHour(null)}
              >
                {/* Bar Column */}
                <div
                  style={{ height: `${heightPercent}%` }}
                  className={cn(
                    'w-full max-w-[32px] rounded-t-md overflow-hidden flex flex-col justify-end transition-all duration-300 relative cursor-pointer',
                    item.count === 0
                      ? 'bg-muted/30 group-hover:bg-muted/50'
                      : isPeak
                      ? 'ring-2 ring-amber-400/40 shadow-lg shadow-amber-500/10 group-hover:brightness-110'
                      : 'group-hover:brightness-110'
                  )}
                >
                  {/* Late portion (amber) */}
                  {item.late > 0 && (
                    <div
                      style={{ height: `${latePercent}%` }}
                      className="w-full bg-amber-400 shrink-0"
                    />
                  )}
                  {/* On-time portion (blue/emerald) */}
                  {item.count > 0 && (
                    <div
                      style={{ height: `${onTimePercent}%` }}
                      className="w-full bg-primary"
                    />
                  )}
                </div>

                {/* Hour label */}
                <span
                  className={cn(
                    'text-[10px] font-mono mt-2 transition-colors',
                    isPeak
                      ? 'text-amber-400 font-bold'
                      : 'text-muted-foreground group-hover:text-foreground'
                  )}
                >
                  {item.hour.substring(0, 2)}h
                </span>
              </div>
            );
          })}
        </div>

        {/* Floating Tooltip */}
        {hoveredHour && (
          <div className="absolute top-0 right-0 bg-popover/95 backdrop-blur-md text-popover-foreground text-xs py-2 px-3 rounded-lg border border-border shadow-xl font-mono z-20 pointer-events-none">
            <div className="flex items-center gap-1.5 font-sans font-semibold text-foreground border-b border-border/50 pb-1 mb-1.5 text-[11px]">
              <Clock className="w-3 h-3 text-primary" />
              <span>Ventana de {hoveredHour.hour} hrs</span>
            </div>
            <div className="flex items-center justify-between gap-4 text-[10px]">
              <span className="text-muted-foreground">Total checadas:</span>
              <span className="font-bold text-foreground">{hoveredHour.count}</span>
            </div>
            <div className="flex items-center justify-between gap-4 text-[10px] text-emerald-400">
              <span>A tiempo:</span>
              <span className="font-bold">{hoveredHour.onTime}</span>
            </div>
            {hoveredHour.late > 0 && (
              <div className="flex items-center justify-between gap-4 text-[10px] text-amber-400">
                <span>Con retardo:</span>
                <span className="font-bold">{hoveredHour.late}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart Legend */}
      <div className="flex items-center justify-center space-x-6 pt-3 text-xs text-muted-foreground">
        <div className="flex items-center space-x-1.5">
          <div className="h-2.5 w-2.5 rounded-xs bg-primary" />
          <span>A Tiempo</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <div className="h-2.5 w-2.5 rounded-xs bg-amber-400" />
          <span>Con Retardo</span>
        </div>
      </div>
    </div>
  );
};

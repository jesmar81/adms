import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Briefcase, Clock, Flame, AlertCircle, ArrowUpRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PayrollSummaryCardProps {
  totalHoursWorked?: number;
  totalOvertimeHours?: number;
  totalLateMinutes?: number;
  totalEvaluated?: number;
  onNavigateToOvertime?: () => void;
  className?: string;
}

export const PayrollSummaryCard: React.FC<PayrollSummaryCardProps> = ({
  totalHoursWorked = 0,
  totalOvertimeHours = 0,
  totalLateMinutes = 0,
  totalEvaluated = 0,
  onNavigateToOvertime,
  className,
}) => {
  // Convert late minutes to hours and minutes for readability
  const lateHours = Math.floor(totalLateMinutes / 60);
  const lateMins = totalLateMinutes % 60;
  const lateFormatted =
    lateHours > 0 ? `${lateHours}h ${lateMins}m` : `${totalLateMinutes} min`;

  return (
    <Card className={cn('border-border/80 bg-card/70 backdrop-blur-sm', className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="flex items-center space-x-2">
          <div className="rounded-lg bg-indigo-500/10 p-1.5 text-indigo-400">
            <Briefcase className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-sm font-semibold text-foreground">
              Métricas de Jornada & Pre-Nómina
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Horas efectivas acumuladas en la jornada de hoy
            </p>
          </div>
        </div>

        {onNavigateToOvertime && (
          <button
            onClick={onNavigateToOvertime}
            className="text-xs text-amber-400 hover:text-amber-300 flex items-center gap-1 font-medium transition-colors"
          >
            <span>Gestionar T. Extra</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          {/* Horas Ordinarias */}
          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 flex flex-col justify-between">
            <div className="flex items-center justify-between text-muted-foreground mb-1">
              <span className="text-[11px] font-medium">Horas Efectivas</span>
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
            </div>
            <div>
              <div className="text-xl font-bold font-mono text-foreground">
                {totalHoursWorked.toFixed(1)}
                <span className="text-xs text-muted-foreground font-normal ml-1">hrs</span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {totalEvaluated} {totalEvaluated === 1 ? 'colab. activo' : 'colabs. activos'}
              </p>
            </div>
          </div>

          {/* Horas Extra */}
          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 flex flex-col justify-between">
            <div className="flex items-center justify-between text-muted-foreground mb-1">
              <span className="text-[11px] font-medium">Horas Extra</span>
              <Flame className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div>
              <div className="text-xl font-bold font-mono text-amber-400">
                {totalOvertimeHours.toFixed(1)}
                <span className="text-xs text-muted-foreground font-normal ml-1">hrs</span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Registradas / LFT
              </p>
            </div>
          </div>

          {/* Tiempo Retardo */}
          <div className="p-3 rounded-lg bg-muted/40 border border-border/50 flex flex-col justify-between">
            <div className="flex items-center justify-between text-muted-foreground mb-1">
              <span className="text-[11px] font-medium">Tiempo Retardo</span>
              <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
            </div>
            <div>
              <div className="text-xl font-bold font-mono text-rose-400">
                {lateFormatted}
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Minutos acumulados
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

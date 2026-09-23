import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Fingerprint, ShieldCheck, UserCheck, AlertTriangle, ArrowUpRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface BiometricHealthData {
  totalUsers: number;
  usersWithFp: number;
  usersWithoutFp: number;
  totalFingerprints: number;
  coverageRate: number;
}

interface BiometricHealthCardProps {
  data?: BiometricHealthData;
  onNavigateToUsers?: () => void;
  className?: string;
}

export const BiometricHealthCard: React.FC<BiometricHealthCardProps> = ({
  data = {
    totalUsers: 0,
    usersWithFp: 0,
    usersWithoutFp: 0,
    totalFingerprints: 0,
    coverageRate: 100,
  },
  onNavigateToUsers,
  className,
}) => {
  const coverageRate = Math.round(data.coverageRate);

  return (
    <Card className={cn('border-border/80 bg-card/70 backdrop-blur-sm', className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div className="flex items-center space-x-2">
          <div className="rounded-lg bg-emerald-500/10 p-1.5 text-emerald-400">
            <Fingerprint className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="text-sm font-semibold text-foreground">
              Salud Biométrica SilkID
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Cobertura de huellas dactilares 3D en terminales SilkFP
            </p>
          </div>
        </div>

        {onNavigateToUsers && (
          <button
            onClick={onNavigateToUsers}
            className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-medium transition-colors"
          >
            <span>Personal</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Coverage Progress Bar */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1.5 font-mono">
            <span className="text-muted-foreground flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              Tasa de Cobertura
            </span>
            <span className="font-bold text-foreground">{coverageRate}%</span>
          </div>
          <div className="w-full bg-muted/40 h-2 rounded-full overflow-hidden border border-border/40">
            <div
              className={cn(
                'h-full transition-all duration-500 rounded-full',
                coverageRate >= 80
                  ? 'bg-emerald-500'
                  : coverageRate >= 50
                  ? 'bg-amber-500'
                  : 'bg-rose-500'
              )}
              style={{ width: `${coverageRate}%` }}
            />
          </div>
        </div>

        {/* Micro statistics */}
        <div className="grid grid-cols-3 gap-2 pt-1 text-center font-mono">
          <div className="p-2 rounded-md bg-muted/30 border border-border/40">
            <span className="text-[10px] text-muted-foreground block font-sans">
              Plantillas Activas
            </span>
            <span className="text-sm font-bold text-foreground">
              {data.totalFingerprints}
            </span>
          </div>

          <div className="p-2 rounded-md bg-muted/30 border border-border/40">
            <span className="text-[10px] text-muted-foreground block font-sans">
              Con Huella
            </span>
            <span className="text-sm font-bold text-emerald-400">
              {data.usersWithFp} / {data.totalUsers}
            </span>
          </div>

          <div className="p-2 rounded-md bg-muted/30 border border-border/40">
            <span className="text-[10px] text-muted-foreground block font-sans">
              Sin Huella
            </span>
            <span
              className={cn(
                'text-sm font-bold',
                data.usersWithoutFp > 0 ? 'text-amber-400' : 'text-muted-foreground'
              )}
            >
              {data.usersWithoutFp}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

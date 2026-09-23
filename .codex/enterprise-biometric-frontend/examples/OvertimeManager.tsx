import React, { useState, useEffect } from 'react';
import {
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Sparkles,
  Filter,
  RefreshCw,
  UserCheck,
  PlusCircle,
  Trash2,
  Calendar,
} from 'lucide-react';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  getOvertimeList,
  authorizeOvertime,
  createManualOvertime,
  deleteOvertime,
} from '@/api/overtime';
import { getUsers } from '@/api/users';
import type { OvertimeAuthorization, BiometricUser } from '@/types';
import { formatDate } from '@/lib/utils';

export const OvertimeManager: React.FC = () => {
  const [records, setRecords] = useState<OvertimeAuthorization[]>([]);
  const [users, setUsers] = useState<BiometricUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('todos');

  // Modal State for Review/Approval
  const [selectedRecord, setSelectedRecord] = useState<OvertimeAuthorization | null>(null);
  const [horasAutorizar, setHorasAutorizar] = useState<number>(0);
  const [tipoOvertime, setTipoOvertime] = useState<'doble' | 'triple'>('doble');
  const [motivo, setMotivo] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Modal State for Manual Overtime Registration
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [manualUserId, setManualUserId] = useState<string>('');
  const [manualFecha, setManualFecha] = useState<string>(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [manualHoras, setManualHoras] = useState<number>(1.0);
  const [manualTipo, setManualTipo] = useState<'auto' | 'doble' | 'triple'>('auto');
  const [manualStatus, setManualStatus] = useState<'aprobado' | 'pendiente'>('aprobado');
  const [manualMotivo, setManualMotivo] = useState<string>('Jornada extraordinaria autorizada por gerencia');
  const [isSubmittingManual, setIsSubmittingManual] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [data, usersData] = await Promise.all([
        getOvertimeList({
          status: statusFilter === 'todos' ? undefined : statusFilter,
        }),
        getUsers(),
      ]);
      setRecords(data);
      if (usersData && usersData.items) {
        setUsers(usersData.items);
        if (!manualUserId && usersData.items.length > 0) {
          setManualUserId(usersData.items[0].id);
        }
      }
    } catch (err) {
      console.error('Error cargando registros de tiempo extra:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const handleOpenReview = (rec: OvertimeAuthorization) => {
    setSelectedRecord(rec);
    setHorasAutorizar(rec.horas_autorizadas > 0 ? rec.horas_autorizadas : rec.horas_detectadas);
    setTipoOvertime(rec.tipo || 'doble');
    setMotivo(rec.motivo || 'Tiempo extra laboral autorizado');
  };

  const handleAction = async (action: 'aprobar' | 'rechazar') => {
    if (!selectedRecord) return;

    setIsSubmitting(true);
    try {
      await authorizeOvertime(selectedRecord.id, {
        horas_autorizadas: Number(horasAutorizar),
        tipo: tipoOvertime,
        motivo: motivo.trim() || undefined,
        action,
      });
      setSelectedRecord(null);
      await loadData();
    } catch (err) {
      alert('Error al procesar la autorización de tiempo extra');
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualUserId) {
      alert('Por favor selecciona un colaborador');
      return;
    }
    if (manualHoras <= 0) {
      alert('Las horas extraordinarias deben ser mayores a cero');
      return;
    }

    setIsSubmittingManual(true);
    try {
      await createManualOvertime({
        biometric_user_id: manualUserId,
        fecha: manualFecha,
        horas: Number(manualHoras),
        tipo: manualTipo,
        status: manualStatus,
        motivo: manualMotivo.trim() || 'Tiempo extra registrado manualmente',
      });
      setIsManualModalOpen(false);
      await loadData();
    } catch (err) {
      console.error('Error registrando tiempo extra manual:', err);
      alert('Ocurrió un error al registrar el tiempo extra manual.');
    } finally {
      setIsSubmittingManual(false);
    }
  };

  const handleDelete = async (id: string, name?: string) => {
    if (!confirm(`¿Eliminar este registro de tiempo extra para ${name || 'el colaborador'}?`)) {
      return;
    }
    try {
      await deleteOvertime(id);
      await loadData();
    } catch (err) {
      console.error('Error eliminando tiempo extra:', err);
      alert('Error al eliminar el registro de tiempo extra.');
    }
  };

  // Metrics
  const pendingCount = records.filter((r) => r.status === 'pendiente').length;
  const approvedDoubles = records
    .filter((r) => r.status === 'aprobado' && r.tipo === 'doble')
    .reduce((sum, r) => sum + r.horas_autorizadas, 0);
  const approvedTriples = records
    .filter((r) => r.status === 'aprobado' && r.tipo === 'triple')
    .reduce((sum, r) => sum + r.horas_autorizadas, 0);

  const selectedManualUser = users.find((u) => u.id === manualUserId);

  return (
    <div className="space-y-4">
      {/* LFT Compliance Banner */}
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 space-y-2">
        <div className="flex items-center space-x-2 text-xs font-semibold text-foreground">
          <ShieldAlert className="h-4 w-4 text-amber-400" />
          <span>Reglas de Tiempo Extraordinario en México (LFT Arts. 66, 67 y 68)</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-muted-foreground">
          <div className="rounded-lg bg-card/80 p-3 border border-border/60">
            <strong className="text-foreground block mb-1">Tope LFT: 3h/día y 3 días/sem</strong>
            La jornada no debe prolongarse más de 3 horas diarias ni de 3 veces en una semana (máximo 9 horas extraordinarias semanales).
          </div>
          <div className="rounded-lg bg-card/80 p-3 border border-border/60">
            <strong className="text-emerald-400 block mb-1">Horas Dobles (100% Art. 67)</strong>
            Las primeras 9 horas extraordinarias a la semana se pagan con un ciento por ciento más del salario ordinario.
          </div>
          <div className="rounded-lg bg-card/80 p-3 border border-border/60">
            <strong className="text-amber-400 block mb-1">Horas Triples (200% Art. 68)</strong>
            El tiempo extraordinario que exceda de 9 horas a la semana obliga al patrón a pagarlo con doscientos por ciento más de salario.
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="rounded-xl border border-border/80 bg-card p-3 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground font-medium">Pendientes de Evaluación</span>
            <div className="text-xl font-bold font-mono text-foreground mt-0.5">{pendingCount}</div>
          </div>
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
            <Clock className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-xl border border-border/80 bg-card p-3 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground font-medium">Horas Dobles Autorizadas</span>
            <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
              {approvedDoubles.toFixed(2)}h
            </div>
          </div>
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </div>

        <div className="rounded-xl border border-border/80 bg-card p-3 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground font-medium">Horas Triples Autorizadas</span>
            <div className="text-xl font-bold font-mono text-amber-400 mt-0.5">
              {approvedTriples.toFixed(2)}h
            </div>
          </div>
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
            <Sparkles className="h-5 w-5" />
          </div>
        </div>
      </div>

      {/* Filter and Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-card p-3 rounded-xl border border-border/70">
        <div className="flex items-center space-x-2">
          <div className="flex rounded-lg border border-border bg-muted/40 p-0.5">
            {['todos', 'pendiente', 'aprobado', 'rechazado'].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 rounded-md text-xs font-semibold capitalize transition-colors ${
                  statusFilter === st
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {st === 'todos' ? 'Todos' : st}
              </button>
            ))}
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={loadData}
            disabled={loading}
            className="h-8 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        {/* Action Button: Manual Overtime */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => setIsManualModalOpen(true)}
            className="bg-amber-500 hover:bg-amber-600 text-black font-semibold text-xs flex items-center gap-1.5 shadow-sm"
          >
            <PlusCircle className="h-3.5 w-3.5" />
            <span>Registrar Tiempo Extra Manual</span>
          </Button>
        </div>
      </div>

      {/* Overtime Table */}
      <div className="rounded-xl border border-border/80 bg-card overflow-hidden shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Colaborador</TableHead>
              <TableHead className="text-center">Detectado / Solicitado</TableHead>
              <TableHead className="text-center">Autorizado Nómina</TableHead>
              <TableHead>Tipo Pago</TableHead>
              <TableHead>Estatus</TableHead>
              <TableHead>Semana LFT</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center text-xs text-muted-foreground">
                  No hay registros de tiempo extraordinario en este filtro.
                </TableCell>
              </TableRow>
            ) : (
              records.map((rec) => (
                <TableRow key={rec.id}>
                  <TableCell className="font-mono text-xs font-bold text-foreground">
                    {formatDate(rec.fecha)}
                  </TableCell>

                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-semibold text-xs text-foreground">
                        {rec.employee_name || 'Desconocido'}
                      </span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        PIN: {rec.employee_pin}
                      </span>
                    </div>
                  </TableCell>

                  <TableCell className="text-center font-mono text-xs font-bold text-amber-400">
                    +{rec.horas_detectadas.toFixed(2)}h
                  </TableCell>

                  <TableCell className="text-center font-mono text-xs font-bold text-foreground">
                    {rec.status === 'aprobado' ? (
                      <span className="text-emerald-400">+{rec.horas_autorizadas.toFixed(2)}h</span>
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </TableCell>

                  <TableCell>
                    {rec.tipo === 'doble' ? (
                      <Badge variant="success" className="text-[10px]">
                        Doble (100%)
                      </Badge>
                    ) : (
                      <Badge variant="warning" className="text-[10px]">
                        Triple (200%)
                      </Badge>
                    )}
                  </TableCell>

                  <TableCell>
                    {rec.status === 'pendiente' && (
                      <Badge variant="warning" className="text-[10px]">
                        Pendiente
                      </Badge>
                    )}
                    {rec.status === 'aprobado' && (
                      <Badge variant="online" className="text-[10px]">
                        Aprobado
                      </Badge>
                    )}
                    {rec.status === 'rechazado' && (
                      <Badge variant="destructive" className="text-[10px]">
                        Rechazado
                      </Badge>
                    )}
                  </TableCell>

                  <TableCell className="text-xs">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-[11px] text-muted-foreground font-mono">
                        {rec.semana_horas_acumuladas?.toFixed(1) || 0}h en {rec.semana_dias_acumulados || 0} días
                      </span>
                      {rec.lft_warning && (
                        <span
                          className="text-[10px] text-amber-400 flex items-center gap-1 font-medium"
                          title={rec.lft_warning}
                        >
                          <AlertTriangle className="h-3 w-3 shrink-0" />
                          Tope LFT
                        </span>
                      )}
                    </div>
                  </TableCell>

                  <TableCell className="text-right">
                    <div className="flex items-center justify-end space-x-1.5">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenReview(rec)}
                        className="h-7 px-2.5 text-xs font-medium"
                      >
                        {rec.status === 'pendiente' ? 'Evaluar' : 'Revisar'}
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(rec.id, rec.employee_name)}
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                        title="Eliminar registro"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Modal 1: Registro Manual de Tiempo Extra */}
      <Dialog open={isManualModalOpen} onOpenChange={setIsManualModalOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={handleCreateManual}>
            <DialogHeader>
              <div className="flex items-center space-x-2">
                <PlusCircle className="h-5 w-5 text-amber-400" />
                <DialogTitle>Registrar Tiempo Extraordinario Manual</DialogTitle>
              </div>
              <DialogDescription>
                Ingresa horas adicionales para un colaborador. El sistema las reflejará en la pre-nómina y validará los topes legales de la LFT.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* Colaborador */}
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                  Colaborador *
                </label>
                <select
                  value={manualUserId}
                  onChange={(e) => setManualUserId(e.target.value)}
                  required
                  className="w-full h-9 px-3 rounded-md border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="" disabled>
                    Selecciona un colaborador...
                  </option>
                  {users.map((u) => {
                    const fullName = u.nombres
                      ? `${u.nombres} ${u.apellido_paterno || ''}`.trim()
                      : u.nombre_reloj || u.name;
                    return (
                      <option key={u.id} value={u.id}>
                        PIN {u.pin} - {fullName}
                      </option>
                    );
                  })}
                </select>
              </div>

              {/* Fecha y Horas */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                    Fecha Laborada *
                  </label>
                  <Input
                    type="date"
                    required
                    value={manualFecha}
                    onChange={(e) => setManualFecha(e.target.value)}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                    Horas Extra *
                  </label>
                  <Input
                    type="number"
                    step="0.25"
                    min="0.25"
                    max="12"
                    required
                    value={manualHoras}
                    onChange={(e) => setManualHoras(Number(e.target.value))}
                  />
                </div>
              </div>

              {/* Clasificación de Pago y Estado */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                    Clasificación LFT
                  </label>
                  <select
                    value={manualTipo}
                    onChange={(e) => setManualTipo(e.target.value as any)}
                    className="w-full h-9 px-3 rounded-md border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="auto">Automático (LFT Arts. 67-68)</option>
                    <option value="doble">Forzar Doble (100%)</option>
                    <option value="triple">Forzar Triple (200%)</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                    Estatus
                  </label>
                  <select
                    value={manualStatus}
                    onChange={(e) => setManualStatus(e.target.value as any)}
                    className="w-full h-9 px-3 rounded-md border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="aprobado">Aprobar de inmediato</option>
                    <option value="pendiente">Dejar pendiente</option>
                  </select>
                </div>
              </div>

              {/* Motivo */}
              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                  Motivo / Justificación
                </label>
                <Input
                  placeholder="Ej. Cierre de nómina, jornada especial de almacén..."
                  value={manualMotivo}
                  onChange={(e) => setManualMotivo(e.target.value)}
                />
              </div>

              <div className="p-2.5 rounded-lg bg-muted/40 border border-border/50 text-[11px] text-muted-foreground">
                <span className="font-semibold text-foreground block mb-0.5">Impacto en Nómina:</span>
                Al registrarlo como <strong>Aprobado</strong>, el sistema actualizará de inmediato la tarjeta de asistencia y sumará las horas extras al cálculo del periodo.
              </div>
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsManualModalOpen(false)}
                disabled={isSubmittingManual}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={isSubmittingManual}
                className="bg-amber-500 hover:bg-amber-600 text-black font-semibold flex items-center gap-1.5"
              >
                <CheckCircle2 className="h-4 w-4" />
                {isSubmittingManual ? 'Guardando...' : 'Guardar Tiempo Extra'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Modal 2: Evaluación / Autorización de Tiempo Extra Existente */}
      <Dialog open={Boolean(selectedRecord)} onOpenChange={(isOpen) => !isOpen && setSelectedRecord(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <div className="flex items-center space-x-2">
              <Clock className="h-5 w-5 text-primary" />
              <DialogTitle>Evaluación de Tiempo Extraordinario</DialogTitle>
            </div>
            <DialogDescription>
              Valida las horas extraordinarias para aplicarlas formalmente a la tarjeta de asistencia y nómina.
            </DialogDescription>
          </DialogHeader>

          {selectedRecord && (
            <div className="space-y-4">
              {/* Employee & Date Summary */}
              <div className="rounded-lg border border-border p-3 bg-muted/20 space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Colaborador:</span>
                  <span className="font-semibold text-foreground">
                    {selectedRecord.employee_name} (PIN: {selectedRecord.employee_pin})
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Fecha laborada:</span>
                  <span className="font-mono font-medium text-foreground">
                    {formatDate(selectedRecord.fecha)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Horas detectadas/registradas:</span>
                  <span className="font-mono font-bold text-amber-400">
                    +{selectedRecord.horas_detectadas.toFixed(2)} hrs
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Acumulado semana LFT:</span>
                  <span className="font-mono text-foreground">
                    {selectedRecord.semana_horas_acumuladas?.toFixed(2) || 0} hrs (
                    {selectedRecord.semana_dias_acumulados || 0} días)
                  </span>
                </div>
              </div>

              {selectedRecord.lft_warning && (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5 text-xs text-amber-300 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{selectedRecord.lft_warning}</span>
                </div>
              )}

              {/* Horas a autorizar */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                    Horas a Autorizar *
                  </label>
                  <Input
                    type="number"
                    step="0.25"
                    min="0"
                    max="12"
                    value={horasAutorizar}
                    onChange={(e) => setHorasAutorizar(Number(e.target.value))}
                  />
                  <span className="text-[10px] text-muted-foreground">
                    Máx 3h por jornada según Art. 66
                  </span>
                </div>

                <div>
                  <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                    Clasificación de Pago
                  </label>
                  <select
                    value={tipoOvertime}
                    onChange={(e) => setTipoOvertime(e.target.value as 'doble' | 'triple')}
                    className="w-full h-9 px-3 rounded-md border border-input bg-background text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="doble">Doble (100% - Hasta 9h sem)</option>
                    <option value="triple">Triple (200% - Excedente 9h)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 block">
                  Motivo / Justificación *
                </label>
                <Input
                  placeholder="Ej. Cierre de inventario autorizado por gerencia"
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                />
              </div>

              <DialogFooter className="pt-2 flex flex-col sm:flex-row gap-2">
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => handleAction('rechazar')}
                  disabled={isSubmitting}
                  className="flex items-center gap-1.5"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  Rechazar Tiempo Extra
                </Button>

                <Button
                  type="button"
                  size="sm"
                  onClick={() => handleAction('aprobar')}
                  disabled={isSubmitting || horasAutorizar <= 0}
                  className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {isSubmitting ? 'Guardando...' : 'Aprobar y Pasar a Nómina'}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

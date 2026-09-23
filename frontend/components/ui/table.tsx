import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyOf: (row: T, index: number) => string;
  /** Representación en tarjeta para móvil (sin overflow horizontal). */
  renderCard: (row: T, index: number) => ReactNode;
  empty: ReactNode;
  ariaLabel: string;
}

/**
 * Tabla en desktop, lista de tarjetas en móvil.
 * El `empty` lo provee cada página (EmptyState contextual).
 */
export function DataTable<T>({ columns, data, keyOf, renderCard, empty, ariaLabel }: DataTableProps<T>) {
  if (data.length === 0) return <>{empty}</>;

  return (
    <>
      <div className="hidden overflow-hidden rounded-[10px] border border-line-subtle bg-surface-card shadow-card md:block">
        <table aria-label={ariaLabel} className="w-full text-sm">
          <thead>
            <tr className="border-b border-line-subtle bg-surface-raised/80">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={`px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-muted ${col.className ?? ""}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={keyOf(row, i)}
                className="border-b border-line-subtle/70 transition-colors duration-150 last:border-0 hover:bg-surface-hover/70"
              >
                {columns.map((col) => (
                  <td key={col.key} className={`px-4 py-3 align-middle text-foreground ${col.className ?? ""}`}>
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col gap-3 md:hidden">
        {data.map((row, i) => (
          <div
            key={keyOf(row, i)}
            className="rounded-xl border border-line-subtle bg-surface-card p-4 shadow-card"
          >
            {renderCard(row, i)}
          </div>
        ))}
      </div>
    </>
  );
}

export function Pagination({
  offset,
  limit,
  hasMore,
  onPage,
}: {
  offset: number;
  limit: number;
  hasMore: boolean;
  onPage: (offset: number) => void;
}) {
  return (
    <div className="mt-5 flex items-center justify-between gap-3 text-sm">
      <p className="text-muted tabular-nums">
        Mostrando {offset + 1}–{offset + limit}
      </p>
      <div className="flex gap-2">
        <button
          disabled={offset === 0}
          onClick={() => onPage(Math.max(0, offset - limit))}
          className="min-h-11 rounded-lg border border-line-subtle bg-surface-raised px-4 py-1.5 text-foreground shadow-sm transition-colors duration-200 hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40 sm:min-h-0"
        >
          Anterior
        </button>
        <button
          disabled={!hasMore}
          onClick={() => onPage(offset + limit)}
          className="min-h-11 rounded-lg border border-line-subtle bg-surface-raised px-4 py-1.5 text-foreground shadow-sm transition-colors duration-200 hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40 sm:min-h-0"
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}

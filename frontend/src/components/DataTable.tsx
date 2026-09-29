import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { useIsMobile } from "@/hooks/use-media-query";
import { Skeleton } from "./ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    className?: string;
    headerClassName?: string;
  }
}

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  loading?: boolean;
  onRowClick?: (row: T) => void;
  /** Server-side sorting (manual). */
  sorting?: SortingState;
  onSortingChange?: (s: SortingState) => void;
  /** Mobile rendering: each row becomes a card. */
  renderCard: (row: T) => ReactNode;
  getRowId?: (row: T) => string;
  skeletonRows?: number;
  empty?: ReactNode;
  rowLabel?: (row: T) => string;
}

export function DataTable<T>({
  columns,
  data,
  loading,
  onRowClick,
  sorting,
  onSortingChange,
  renderCard,
  getRowId,
  skeletonRows = 8,
  empty,
  rowLabel,
}: DataTableProps<T>) {
  const { t } = useI18n();
  const mobile = useIsMobile();
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    state: { sorting: sorting ?? [] },
    onSortingChange: (updater) => {
      if (!onSortingChange) return;
      const next = typeof updater === "function" ? updater(sorting ?? []) : updater;
      onSortingChange(next);
    },
    enableSorting: !!onSortingChange,
    getRowId,
  });

  if (loading && !data.length) {
    return mobile ? (
      <div className="space-y-2 p-3">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    ) : (
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {table.getFlatHeaders().map((h) => (
              <TableHead key={h.id} className={h.column.columnDef.meta?.headerClassName}>
                {flexRender(h.column.columnDef.header, h.getContext())}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: skeletonRows }, (_, i) => (
            <TableRow key={i} className="hover:bg-transparent">
              {columns.map((_c, j) => (
                <TableCell key={j}>
                  <Skeleton className={cn("h-4", j === 0 ? "w-48" : "w-20")} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  if (!data.length) return <>{empty}</>;

  if (mobile) {
    return (
      <ul className={cn("divide-y transition-opacity", loading && "opacity-60")}>
        {table.getRowModel().rows.map((row) => (
          <li key={row.id}>
            {onRowClick ? (
              <button
                type="button"
                className="w-full px-4 py-3 text-start transition-colors hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none"
                onClick={() => onRowClick(row.original)}
                aria-label={rowLabel?.(row.original)}
              >
                {renderCard(row.original)}
              </button>
            ) : (
              <div className="px-4 py-3">{renderCard(row.original)}</div>
            )}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Table className={cn("transition-opacity", loading && "opacity-60")}>
      <TableHeader>
        {table.getHeaderGroups().map((hg) => (
          <TableRow key={hg.id} className="hover:bg-transparent">
            {hg.headers.map((h) => {
              const canSort = h.column.getCanSort();
              const dir = h.column.getIsSorted();
              return (
                <TableHead
                  key={h.id}
                  className={h.column.columnDef.meta?.headerClassName}
                  aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                >
                  {canSort ? (
                    <button
                      type="button"
                      className="-mx-1 inline-flex items-center gap-1 rounded px-1 py-0.5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={h.column.getToggleSortingHandler()}
                      title={dir === "asc" ? t("common.sortDesc") : t("common.sortAsc")}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {dir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : dir === "desc" ? (
                        <ArrowDown className="h-3 w-3" />
                      ) : (
                        <ChevronsUpDown className="h-3 w-3 opacity-40" />
                      )}
                    </button>
                  ) : (
                    flexRender(h.column.columnDef.header, h.getContext())
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow
            key={row.id}
            className={cn(onRowClick && "cursor-pointer")}
            onClick={onRowClick ? () => onRowClick(row.original) : undefined}
            onKeyDown={
              onRowClick
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onRowClick(row.original);
                    }
                  }
                : undefined
            }
            tabIndex={onRowClick ? 0 : undefined}
            aria-label={onRowClick ? rowLabel?.(row.original) : undefined}
          >
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id} className={cell.column.columnDef.meta?.className}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

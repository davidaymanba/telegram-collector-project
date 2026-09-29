import { ChevronLeft, ChevronRight } from "lucide-react";
import { useI18n } from "@/i18n";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export function Pagination({
  page,
  pages,
  total,
  pageSize,
  onPage,
  onPageSize,
}: {
  page: number;
  pages: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
  onPageSize?: (n: number) => void;
}) {
  const { t, fmtNumber } = useI18n();
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex flex-col-reverse items-center justify-between gap-3 px-1 py-3 text-sm sm:flex-row">
      <p className="text-xs text-muted-foreground tabular">
        {t("common.showing", { from: fmtNumber(from), to: fmtNumber(to), total: fmtNumber(total) })}
      </p>
      <div className="flex items-center gap-3">
        {onPageSize && (
          <div className="hidden items-center gap-2 sm:flex">
            <span className="text-xs text-muted-foreground">{t("common.rowsPerPage")}</span>
            <Select value={String(pageSize)} onValueChange={(v) => onPageSize(Number(v))}>
              <SelectTrigger className="h-8 w-[70px]" aria-label={t("common.rowsPerPage")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 25, 50, 100].map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <span className="text-xs text-muted-foreground tabular">
          {t("common.pageOf", { page: fmtNumber(page), pages: fmtNumber(Math.max(1, pages)) })}
        </span>
        <div className="flex gap-1">
          <Button variant="outline" size="icon-sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t("common.previous")}>
            <ChevronLeft className="rtl-flip" />
          </Button>
          <Button variant="outline" size="icon-sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t("common.next")}>
            <ChevronRight className="rtl-flip" />
          </Button>
        </div>
      </div>
    </div>
  );
}

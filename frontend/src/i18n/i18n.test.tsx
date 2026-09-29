import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ar } from "./ar";
import { en } from "./en";
import { I18nProvider, interpolate, translate, useI18n } from "./index";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : keys(v as object, `${prefix}${k}.`),
  );
}

describe("i18n", () => {
  it("Arabic and English dictionaries have identical keys", () => {
    expect(keys(ar).sort()).toEqual(keys(en).sort());
  });

  it("placeholders match between languages", () => {
    const ph = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
    for (const k of keys(en)) {
      expect(ph(translate("ar", k)), k).toBe(ph(translate("en", k)));
    }
  });

  it("interpolates variables", () => {
    expect(interpolate("Page {page} of {pages}", { page: 2, pages: 9 })).toBe("Page 2 of 9");
    expect(translate("ar", "common.pageOf", { page: 1, pages: 3 })).toBe("صفحة 1 من 3");
  });

  it("sets document direction and formats per locale", () => {
    const wrapper = ({ children }: { children: ReactNode }) => <I18nProvider defaultLang="ar">{children}</I18nProvider>;
    const { result } = renderHook(() => useI18n(), { wrapper });
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(result.current.fmtNumber(1234)).toBe("1,234");
    expect(result.current.fmtBytes(2048)).toContain("2");
    expect(result.current.fmtRelative(new Date(Date.now() - 5 * 60_000).toISOString())).toMatch(/5/);
  });
});

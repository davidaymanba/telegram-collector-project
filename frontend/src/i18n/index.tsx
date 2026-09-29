import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ar } from "./ar";
import { en, type Dict } from "./en";

export type Lang = "ar" | "en";
const DICTS: Record<Lang, Dict> = { ar, en };
const STORAGE_KEY = "tuc.lang";

type Leaves<T, P extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Leaves<T[K], `${P}${K}.`>;
}[keyof T & string];
export type TKey = Leaves<Dict>;
export type Vars = Record<string, string | number>;

function lookup(dict: Dict, key: string): string {
  const value = key.split(".").reduce<unknown>((node, part) => {
    return node && typeof node === "object" ? (node as Record<string, unknown>)[part] : undefined;
  }, dict);
  return typeof value === "string" ? value : key;
}

export function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (m, name: string) => (name in vars ? String(vars[name]) : m));
}

export function translate(lang: Lang, key: TKey | string, vars?: Vars): string {
  return interpolate(lookup(DICTS[lang], key), vars);
}

interface I18nValue {
  lang: Lang;
  dir: "rtl" | "ltr";
  locale: string;
  setLang: (lang: Lang) => void;
  t: (key: TKey, vars?: Vars) => string;
  /** For keys built at runtime (e.g. `status.${value}`) */
  tx: (key: string, vars?: Vars) => string;
  fmtNumber: (n: number, opts?: Intl.NumberFormatOptions) => string;
  fmtPercent: (ratio: number, digits?: number) => string;
  fmtBytes: (bytes: number | null | undefined) => string;
  fmtDate: (iso: string | Date, opts?: Intl.DateTimeFormatOptions) => string;
  fmtDateTime: (iso: string | Date) => string;
  fmtRelative: (iso: string | Date | null | undefined) => string;
  fmtDuration: (seconds: number | null | undefined) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function initialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "ar" || stored === "en") return stored;
  } catch {
    /* storage unavailable */
  }
  return "ar";
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
  ["second", 1],
];

export function I18nProvider({ children, defaultLang }: { children: ReactNode; defaultLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(defaultLang ?? initialLang);
  const dir = lang === "ar" ? "rtl" : "ltr";
  // Arabic UI with Latin digits reads best for hashes/sizes; dates keep Arabic month names.
  const locale = lang === "ar" ? "ar-EG-u-nu-latn" : "en-US";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* ignore */
    }
  }, [lang, dir]);

  const setLang = useCallback((l: Lang) => setLangState(l), []);

  const value = useMemo<I18nValue>(() => {
    const nf = new Intl.NumberFormat(locale);
    const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    const fmtNumber = (n: number, opts?: Intl.NumberFormatOptions) =>
      opts ? new Intl.NumberFormat(locale, opts).format(n) : nf.format(n);
    return {
      lang,
      dir,
      locale,
      setLang,
      t: (key, vars) => translate(lang, key, vars),
      tx: (key, vars) => translate(lang, key, vars),
      fmtNumber,
      fmtPercent: (ratio, digits = 0) =>
        new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: digits }).format(ratio),
      fmtBytes: (bytes) => {
        if (bytes === null || bytes === undefined) return "—";
        const units = lang === "ar" ? ["بايت", "ك.ب", "م.ب", "ج.ب"] : ["B", "KB", "MB", "GB"];
        let v = bytes;
        let i = 0;
        while (v >= 1024 && i < units.length - 1) {
          v /= 1024;
          i++;
        }
        return `${fmtNumber(v, { maximumFractionDigits: i === 0 ? 0 : 1 })} ${units[i]}`;
      },
      fmtDate: (iso, opts) =>
        new Intl.DateTimeFormat(locale, opts ?? { year: "numeric", month: "short", day: "numeric" }).format(
          new Date(iso),
        ),
      fmtDateTime: (iso) =>
        new Intl.DateTimeFormat(locale, {
          year: "numeric",
          month: "long",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        }).format(new Date(iso)),
      fmtRelative: (iso) => {
        if (!iso) return translate(lang, "common.never");
        const diff = (new Date(iso).getTime() - Date.now()) / 1000;
        if (Math.abs(diff) < 30) return translate(lang, "common.justNow");
        for (const [unit, secs] of RELATIVE_UNITS) {
          if (Math.abs(diff) >= secs || unit === "second") {
            return rtf.format(Math.round(diff / secs), unit);
          }
        }
        return "";
      },
      fmtDuration: (seconds) => {
        if (seconds === null || seconds === undefined) return "—";
        const s = Math.max(0, Math.round(seconds));
        if (s < 60) return translate(lang, "common.seconds", { n: fmtNumber(s) });
        return translate(lang, "common.minutes", { n: fmtNumber(Math.floor(s / 60)), s: fmtNumber(s % 60) });
      },
    };
  }, [lang, dir, locale, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

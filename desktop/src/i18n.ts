export const SUPPORTED_LOCALES = ["ko-KR", "en-US"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: SupportedLocale = "ko-KR";
const STORAGE_KEY = "growwise.locale";

const canonicalize = (value: string): string | null => {
  try {
    return Intl.getCanonicalLocales(value)[0] ?? null;
  } catch {
    return null;
  }
};

export function resolveLocale(candidates: readonly string[]): SupportedLocale {
  for (const candidate of candidates) {
    const canonical = canonicalize(candidate);
    if (!canonical) continue;
    const normalized = canonical.toLowerCase();
    if (normalized === "ko-kr" || normalized === "ko") return "ko-KR";
    if (normalized === "en-us" || normalized === "en") return "en-US";
  }
  return DEFAULT_LOCALE;
}

export function loadLocale(storage: Pick<Storage, "getItem"> | null, languages: readonly string[]): SupportedLocale {
  let stored: string | null = null;
  try {
    stored = storage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    // Storage can be unavailable in hardened/private webviews. Locale selection must still work.
  }
  return resolveLocale(stored ? [stored, ...languages] : languages);
}

export function detectBrowserLocale(): SupportedLocale {
  let storage: Pick<Storage, "getItem"> | null = null;
  let languages: readonly string[] = [];
  try {
    storage = window.localStorage;
  } catch {
    // Accessing localStorage itself can throw under restrictive webview policies.
  }
  try {
    languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  } catch {
    // Fall through to the deterministic Korean default.
  }
  return loadLocale(storage, languages);
}

export function persistLocale(storage: Pick<Storage, "setItem"> | null, locale: SupportedLocale): void {
  try {
    storage?.setItem(STORAGE_KEY, locale);
  } catch {
    // Locale persistence is optional and must never prevent the offline desktop shell from starting.
  }
}

export function applyDocumentLocale(locale: SupportedLocale, root: HTMLElement = document.documentElement): void {
  root.lang = locale;
  root.dir = "ltr";
}

export function formatDate(value: Date | number | string, locale: SupportedLocale): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, { year: "numeric", month: "short", day: "numeric" }).format(date);
}

export function formatNumber(value: number, locale: SupportedLocale): string {
  return new Intl.NumberFormat(locale).format(value);
}

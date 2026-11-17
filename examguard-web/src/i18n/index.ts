import { id, type Key } from "./id";

export type { Key };

const dictionaries: Record<string, Partial<Record<Key, string>>> = { id };
let lang = "id";

export function setLanguage(next: string) {
  if (dictionaries[next]) lang = next;
}

/** t("common.updated", { time: "10:02" }) — falls back to Indonesian, then to the key. */
export function t(key: Key, vars?: Record<string, string | number>): string {
  let s = dictionaries[lang]?.[key] ?? id[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

/** Translate a dynamic key such as `status.${status}`; unknown values show the raw code. */
export function tx(prefix: string, value: string | null | undefined): string {
  if (!value) return t("common.none");
  const key = `${prefix}.${value}` as Key;
  return key in id ? t(key) : value;
}

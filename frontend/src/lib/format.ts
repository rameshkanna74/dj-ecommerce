const currency = import.meta.env.VITE_CURRENCY ?? "USD"
const moneyFormat = new Intl.NumberFormat(undefined, { style: "currency", currency })
const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" })
const dateTimeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" })

/** The API sends money as decimal strings; format for display only (never do math on floats). */
export function money(value: string | number | null | undefined) {
  return moneyFormat.format(Number(value ?? 0))
}

export function date(value: string | null | undefined) {
  return value ? dateFormat.format(new Date(value)) : "—"
}

export function dateTime(value: string | null | undefined) {
  return value ? dateTimeFormat.format(new Date(value)) : "—"
}

export function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("")
}

export function pluralize(count: number, word: string, plural = `${word}s`) {
  return `${count} ${count === 1 ? word : plural}`
}

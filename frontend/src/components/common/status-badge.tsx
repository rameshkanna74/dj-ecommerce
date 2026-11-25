import { cn } from "@/lib/utils"

const TONES = {
  neutral: "bg-muted text-muted-foreground",
  info: "bg-chart-2/12 text-chart-2",
  brand: "bg-brand-soft text-brand",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-[oklch(0.5_0.12_70)] dark:text-warning",
  danger: "bg-destructive/10 text-destructive",
} as const

export type Tone = keyof typeof TONES

/** Order, item, payment, ticket and vendor states mapped to one consistent palette. */
const STATUS_TONES: Record<string, Tone> = {
  pending: "warning",
  processing: "info",
  shipped: "brand",
  delivered: "success",
  cancelled: "danger",
  unpaid: "warning",
  paid: "success",
  refunded: "neutral",
  open: "warning",
  in_progress: "info",
  resolved: "success",
  closed: "neutral",
  approved: "success",
  rejected: "danger",
  suspended: "danger",
}

export function StatusBadge({ status, label, tone, className }: { status?: string; label?: string; tone?: Tone; className?: string }) {
  const resolved = tone ?? STATUS_TONES[status ?? ""] ?? "neutral"
  const text = label ?? (status ?? "").replace(/_/g, " ")
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
        TONES[resolved],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {text}
    </span>
  )
}

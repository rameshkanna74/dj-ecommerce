import { type LucideIcon } from "lucide-react"
import { useId, useState, type ReactNode } from "react"

import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

/** KPI tile used by the vendor and admin dashboards. */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: LucideIcon
  tone?: "default" | "brand" | "warning" | "danger"
}) {
  return (
    <Card className="gap-0 py-0 shadow-none">
      <CardContent className="flex flex-col gap-2 p-5">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{label}</span>
          {Icon && (
            <span
              className={cn(
                "flex size-8 items-center justify-center rounded-lg",
                tone === "default" && "bg-muted text-foreground",
                tone === "brand" && "bg-brand-soft text-brand",
                tone === "warning" && "bg-warning-soft text-[oklch(0.5_0.12_70)] dark:text-warning",
                tone === "danger" && "bg-destructive/10 text-destructive",
              )}
            >
              <Icon className="size-4" />
            </span>
          )}
        </div>
        <p className="text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  )
}

export interface Point {
  label: string
  value: number
}

/**
 * Dependency-free responsive area chart (keeps dashboards light: no chart library).
 * Hover/focus a point to see its value.
 */
export function AreaChart({
  data,
  format = (v) => String(v),
  height = 220,
  className,
}: {
  data: Point[]
  format?: (value: number) => string
  height?: number
  className?: string
}) {
  const id = useId()
  const [active, setActive] = useState<number | null>(null)
  if (!data.length) return null

  const width = 640
  const pad = { top: 16, right: 8, bottom: 24, left: 8 }
  const max = Math.max(...data.map((d) => d.value), 1)
  const x = (i: number) => pad.left + (i * (width - pad.left - pad.right)) / Math.max(data.length - 1, 1)
  const y = (v: number) => pad.top + (1 - v / max) * (height - pad.top - pad.bottom)
  const line = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join(" ")
  const area = `${line} L${x(data.length - 1)},${height - pad.bottom} L${x(0)},${height - pad.bottom} Z`
  const ticks = data.length > 10 ? [0, Math.floor((data.length - 1) / 2), data.length - 1] : data.map((_, i) => i)
  const current = active !== null ? data[active] : null

  return (
    <div className={cn("relative", className)}>
      <div className="mb-2 h-5 text-sm tabular-nums" aria-live="polite">
        {current && (
          <span>
            <span className="font-medium">{format(current.value)}</span>
            <span className="text-muted-foreground"> · {current.label}</span>
          </span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full overflow-visible text-chart-1"
        role="img"
        aria-label="Trend chart"
        onMouseLeave={() => setActive(null)}
      >
        <defs>
          <linearGradient id={`${id}-fill`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.28" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={pad.left}
            x2={width - pad.right}
            y1={y(max * f)}
            y2={y(max * f)}
            className="stroke-border"
            strokeDasharray="3 4"
          />
        ))}
        <path d={area} fill={`url(#${id}-fill)`} />
        <path d={line} fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {data.map((d, i) => (
          <g key={d.label}>
            <rect
              x={x(i) - (width / data.length) / 2}
              y={0}
              width={width / data.length}
              height={height}
              fill="transparent"
              tabIndex={0}
              aria-label={`${d.label}: ${format(d.value)}`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
            />
            {active === i && (
              <>
                <line x1={x(i)} x2={x(i)} y1={pad.top} y2={height - pad.bottom} className="stroke-border" />
                <circle cx={x(i)} cy={y(d.value)} r={4} fill="currentColor" className="stroke-background" strokeWidth={2} />
              </>
            )}
          </g>
        ))}
        {ticks.map((i) => (
          <text
            key={i}
            x={x(i)}
            y={height - 6}
            textAnchor={i === 0 ? "start" : i === data.length - 1 ? "end" : "middle"}
            className="fill-muted-foreground text-[11px]"
          >
            {data[i].label}
          </text>
        ))}
      </svg>
    </div>
  )
}

/** Horizontal bars for "top N" lists (best sellers, categories). */
export function BarList({ items, format = (v) => String(v) }: { items: Point[]; format?: (v: number) => string }) {
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.label} className="space-y-1.5">
          <div className="flex justify-between gap-3 text-sm">
            <span className="truncate">{item.label}</span>
            <span className="shrink-0 font-medium tabular-nums">{format(item.value)}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-chart-1" style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

/** 7 / 30 / 90-day range switch for dashboards. */
export function DaysToggle({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div className="inline-flex rounded-lg bg-muted p-0.5" role="radiogroup" aria-label="Date range">
      {[7, 30, 90].map((d) => (
        <button
          key={d}
          type="button"
          role="radio"
          aria-checked={value === d}
          onClick={() => onChange(d)}
          className={cn(
            "rounded-md px-3 py-1 text-xs transition",
            value === d ? "bg-background font-medium shadow-sm" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {d}d
        </button>
      ))}
    </div>
  )
}

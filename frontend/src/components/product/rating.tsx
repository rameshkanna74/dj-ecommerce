import { StarIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export function Stars({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-0.5", className)} aria-label={`${value.toFixed(1)} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => {
        const fill = Math.max(0, Math.min(1, value - (i - 1)))
        return (
          <span key={i} className="relative inline-block size-3.5">
            <StarIcon className="absolute inset-0 size-3.5 text-muted-foreground/30" fill="currentColor" strokeWidth={0} />
            <span className="absolute inset-0 overflow-hidden" style={{ width: `${fill * 100}%` }}>
              <StarIcon className="size-3.5 text-warning" fill="currentColor" strokeWidth={0} />
            </span>
          </span>
        )
      })}
    </span>
  )
}

export function Rating({ average = 0, count = 0, className }: { average?: string | number; count?: number; className?: string }) {
  if (!count) return <span className={cn("text-xs text-muted-foreground", className)}>No reviews yet</span>
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground", className)}>
      <Stars value={Number(average)} />
      <span>
        {Number(average).toFixed(1)} · {count}
      </span>
    </span>
  )
}

/** Interactive 1–5 picker for the review form. */
export function StarInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          type="button"
          role="radio"
          aria-checked={value === i}
          aria-label={`${i} star${i > 1 ? "s" : ""}`}
          onClick={() => onChange(i)}
          className="rounded p-0.5 transition-transform hover:scale-110 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <StarIcon
            className={cn("size-6", i <= value ? "text-warning" : "text-muted-foreground/30")}
            fill="currentColor"
            strokeWidth={0}
          />
        </button>
      ))}
    </div>
  )
}

import { cn } from "@/lib/utils"

// Warm, low-chroma hues so placeholders look intentional next to real photos.
const HUES = [42, 60, 85, 150, 190, 230, 280, 20]

function hash(text: string) {
  let h = 0
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0
  return Math.abs(h)
}

interface ProductImageProps {
  src?: string | null
  name: string
  alt?: string
  className?: string
  /** Large serif monogram for hero/detail placeholders. */
  size?: "sm" | "md" | "lg"
  loading?: "lazy" | "eager"
}

/** Product photo, or a deterministic tinted monogram when the vendor has not uploaded one. */
export function ProductImage({ src, name, alt, className, size = "md", loading = "lazy" }: ProductImageProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={alt ?? name}
        loading={loading}
        decoding="async"
        className={cn("size-full object-cover", className)}
      />
    )
  }
  const hue = HUES[hash(name) % HUES.length]
  const letters = name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
  return (
    <div
      role="img"
      aria-label={alt ?? name}
      className={cn("relative flex size-full items-center justify-center overflow-hidden", className)}
      style={{
        background: `radial-gradient(120% 90% at 20% 10%, oklch(0.97 0.03 ${hue}) 0%, oklch(0.9 0.05 ${hue}) 55%, oklch(0.82 0.07 ${hue}) 100%)`,
      }}
    >
      <div
        className="absolute -right-1/4 -bottom-1/4 size-3/4 rounded-full opacity-40 blur-2xl"
        style={{ background: `oklch(0.75 0.1 ${(hue + 40) % 360})` }}
      />
      <span
        className={cn(
          "font-heading relative select-none",
          size === "sm" && "text-2xl",
          size === "md" && "text-6xl",
          size === "lg" && "text-8xl md:text-9xl",
        )}
        style={{ color: `oklch(0.38 0.06 ${hue})` }}
      >
        {letters}
      </span>
    </div>
  )
}

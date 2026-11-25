import { HeartIcon } from "lucide-react"
import { Link, useNavigate } from "react-router"

import { ProductImage } from "@/components/product/product-image"
import { Rating } from "@/components/product/rating"
import { useToggleWishlist, useWishlistIds } from "@/features/account/wishlist-api"
import type { Product } from "@/features/catalog/api"
import { money } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useAuth } from "@/providers/auth"

export function ProductCard({ product, priority = false }: { product: Product; priority?: boolean }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const saved = useWishlistIds().has(product.id)
  const toggle = useToggleWishlist()

  function onHeart() {
    if (!user) return navigate(`/login?next=/products/${product.slug}`)
    toggle.mutate({ product, saved })
  }

  return (
    <article className="group relative flex flex-col gap-3">
      <div className="relative aspect-[4/5] overflow-hidden rounded-2xl bg-muted">
        <Link to={`/products/${product.slug}`} aria-label={product.name} className="block size-full">
          <ProductImage
            src={product.cover_image}
            name={product.name}
            loading={priority ? "eager" : "lazy"}
            className="transition-transform duration-500 ease-out group-hover:scale-[1.04]"
          />
        </Link>
        <div className="pointer-events-none absolute inset-x-3 top-3 flex items-start justify-between">
          <div className="flex flex-col gap-1.5">
            {!product.is_in_stock ? (
              <span className="rounded-full bg-background/90 px-2.5 py-1 text-[11px] font-medium backdrop-blur">
                Sold out
              </span>
            ) : product.is_low_stock ? (
              <span className="rounded-full bg-brand px-2.5 py-1 text-[11px] font-medium text-brand-foreground">
                Only a few left
              </span>
            ) : null}
          </div>
          {user?.role !== "vendor" && (
            <button
              type="button"
              onClick={onHeart}
              aria-pressed={saved}
              aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
              className="pointer-events-auto flex size-9 items-center justify-center rounded-full bg-background/90 shadow-sm backdrop-blur transition hover:scale-105 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
              <HeartIcon className={cn("size-4", saved ? "fill-brand text-brand" : "text-foreground")} />
            </button>
          )}
        </div>
      </div>
      <div className="flex flex-col gap-1 px-0.5">
        <div className="flex items-start justify-between gap-3">
          <h3 className="line-clamp-2 text-sm leading-snug font-medium">
            <Link to={`/products/${product.slug}`} className="hover:underline">
              {product.name}
            </Link>
          </h3>
          <p className="shrink-0 text-sm font-semibold tabular-nums">
            {product.has_variants && <span className="mr-1 text-xs font-normal text-muted-foreground">from</span>}
            {money(product.price)}
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {product.vendor ? (
            <Link to={`/stores/${product.vendor.store_slug}`} className="hover:text-foreground">
              {product.vendor.business_name}
            </Link>
          ) : (
            "CoreCart"
          )}
          <span className="mx-1.5">·</span>
          {product.category.name}
        </p>
        <Rating average={product.average_rating} count={product.review_count} />
      </div>
    </article>
  )
}

export function ProductCardSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden>
      <div className="aspect-[4/5] animate-pulse rounded-2xl bg-muted" />
      <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
      <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
    </div>
  )
}

export function ProductGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("grid grid-cols-2 gap-x-4 gap-y-8 sm:gap-x-6 md:grid-cols-3 lg:grid-cols-4", className)}>
      {children}
    </div>
  )
}

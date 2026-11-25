import { AlertTriangleIcon, ArrowRightIcon, BookmarkIcon, MinusIcon, PlusIcon, ShoppingBagIcon, Trash2Icon } from "lucide-react"
import { Link } from "react-router"

import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useCart, useRemoveCartItem, useUpdateCartItem, type CartItem } from "@/features/cart/api"
import { money, pluralize } from "@/lib/format"
import { cn } from "@/lib/utils"

function Line({ item, saved = false }: { item: CartItem; saved?: boolean }) {
  const update = useUpdateCartItem()
  const remove = useRemoveCartItem()
  const busy = update.isPending || remove.isPending
  const quantity = item.quantity ?? 1
  const max = Math.min(item.available_stock, 99)

  return (
    <li className={cn("flex gap-4 py-6", busy && "opacity-60")}>
      <Link
        to={`/products/${item.product.slug}`}
        className="size-24 shrink-0 overflow-hidden rounded-xl bg-muted sm:size-28"
      >
        <ProductImage src={item.product.cover_image} name={item.product.name} size="sm" />
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex justify-between gap-4">
          <div className="min-w-0">
            <Link to={`/products/${item.product.slug}`} className="line-clamp-2 font-medium hover:underline">
              {item.product.name}
            </Link>
            <p className="text-xs text-muted-foreground">
              {item.product.vendor?.business_name ?? "CoreCart"}
              {item.variant && <> · {item.variant.label}</>}
            </p>
          </div>
          <p className="shrink-0 font-semibold tabular-nums">{money(item.subtotal)}</p>
        </div>
        <p className="text-xs text-muted-foreground tabular-nums">{money(item.unit_price)} each</p>
        {item.problem && !saved && (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertTriangleIcon className="size-3.5" /> {item.problem}
          </p>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
          {!saved && (
            <div className="inline-flex h-9 items-center rounded-full border">
              <button
                type="button"
                className="flex size-9 items-center justify-center rounded-full hover:bg-muted disabled:opacity-40"
                disabled={busy || quantity <= 1}
                onClick={() => update.mutate({ id: item.id, quantity: quantity - 1 })}
                aria-label="Decrease quantity"
              >
                <MinusIcon className="size-3.5" />
              </button>
              <span className="w-7 text-center text-sm tabular-nums">{quantity}</span>
              <button
                type="button"
                className="flex size-9 items-center justify-center rounded-full hover:bg-muted disabled:opacity-40"
                disabled={busy || quantity >= max}
                onClick={() => update.mutate({ id: item.id, quantity: quantity + 1 })}
                aria-label="Increase quantity"
              >
                <PlusIcon className="size-3.5" />
              </button>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => update.mutate({ id: item.id, is_saved_for_later: !saved })}
          >
            {saved ? <ShoppingBagIcon /> : <BookmarkIcon />}
            {saved ? "Move to cart" : "Save for later"}
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => remove.mutate(item.id)} className="text-muted-foreground">
            <Trash2Icon /> Remove
          </Button>
        </div>
      </div>
    </li>
  )
}

export default function CartPage() {
  const { data: cart, isPending, isError, error, refetch } = useCart()

  if (isPending) return <PageLoader />
  if (isError)
    return (
      <div className="container-page py-16">
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    )

  return (
    <div className="container-page space-y-8 py-10">
      <Title>Your cart</Title>
      <PageHeader title="Your cart" description={cart.items.length ? pluralize(cart.total_quantity, "item") : undefined} />

      {!cart.items.length ? (
        <EmptyState
          icon={ShoppingBagIcon}
          title="Your cart is empty"
          description="Find something you love from our makers."
          action={
            <Button asChild>
              <Link to="/products">Start shopping</Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-10 lg:grid-cols-[1fr_22rem]">
          <ul className="divide-y border-y">
            {cart.items.map((item) => (
              <Line key={item.id} item={item} />
            ))}
          </ul>
          <aside className="h-fit space-y-4 rounded-2xl bg-muted/50 p-6 lg:sticky lg:top-24">
            <p className="font-medium">Order summary</p>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="tabular-nums">{money(cart.subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Shipping</span>
              <span>Calculated by each maker</span>
            </div>
            <Separator />
            <div className="flex justify-between font-semibold">
              <span>Total</span>
              <span className="tabular-nums">{money(cart.subtotal)}</span>
            </div>
            {cart.has_problems && (
              <p className="flex gap-2 rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
                <AlertTriangleIcon className="size-4 shrink-0" />
                Some items need attention before you can check out.
              </p>
            )}
            <Button size="lg" className="w-full" disabled={cart.has_problems} asChild={!cart.has_problems}>
              {cart.has_problems ? (
                <span>Checkout</span>
              ) : (
                <Link to="/checkout">
                  Checkout <ArrowRightIcon />
                </Link>
              )}
            </Button>
            <p className="text-center text-xs text-muted-foreground">Coupons can be applied at checkout.</p>
          </aside>
        </div>
      )}

      {cart.saved_items.length > 0 && (
        <section className="space-y-2 pt-6">
          <h2 className="font-heading text-2xl">Saved for later</h2>
          <ul className="divide-y border-y">
            {cart.saved_items.map((item) => (
              <Line key={item.id} item={item} saved />
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

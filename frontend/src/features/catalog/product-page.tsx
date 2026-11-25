import {
  BellIcon,
  CheckIcon,
  HeartIcon,
  MessageCircleQuestionIcon,
  MinusIcon,
  PlusIcon,
  ShieldCheckIcon,
  ShoppingBagIcon,
  StarIcon,
  TruckIcon,
} from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { toast } from "sonner"

import { ApiError } from "@/api/client"
import { Pager } from "@/components/common/pager"
import { EmptyState, ErrorState, PageLoader, Spinner, errorMessage } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"
import { Rating, StarInput, Stars } from "@/components/product/rating"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useToggleWishlist, useWishlistIds } from "@/features/account/wishlist-api"
import { useAddToCart } from "@/features/cart/api"
import {
  useAskQuestion,
  useCreateReview,
  useProduct,
  useQuestions,
  useReviews,
  useStockAlert,
  type ProductDetail,
  type Variant,
} from "@/features/catalog/api"
import { date, money, pluralize } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useAuth } from "@/providers/auth"

function Gallery({ product }: { product: ProductDetail }) {
  const images = [
    ...(product.cover_image ? [{ id: 0, image: product.cover_image, alt_text: product.name }] : []),
    ...product.images.filter((img) => img.image !== product.cover_image),
  ]
  const [index, setIndex] = useState(0)
  const current = images[index]
  return (
    <div className="space-y-3">
      <div className="aspect-square overflow-hidden rounded-3xl bg-muted">
        <ProductImage
          src={current?.image}
          name={product.name}
          alt={current?.alt_text || product.name}
          size="lg"
          loading="eager"
        />
      </div>
      {images.length > 1 && (
        <div className="grid grid-cols-5 gap-3">
          {images.map((img, i) => (
            <button
              key={img.id}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Show image ${i + 1}`}
              aria-current={i === index}
              className={cn(
                "aspect-square overflow-hidden rounded-xl ring-offset-2 ring-offset-background transition",
                i === index ? "ring-2 ring-foreground" : "opacity-70 hover:opacity-100",
              )}
            >
              <ProductImage src={img.image} name={product.name} alt="" size="sm" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function VariantPicker({
  variants,
  selected,
  onSelect,
}: {
  variants: Variant[]
  selected?: Variant
  onSelect: (v: Variant) => void
}) {
  const groups = Object.entries(
    variants.reduce<Record<string, Variant[]>>((acc, v) => {
      ;(acc[v.attribute_name] ??= []).push(v)
      return acc
    }, {}),
  )
  return (
    <div className="space-y-4">
      {groups.map(([name, options]) => (
        <fieldset key={name} className="space-y-2">
          <legend className="text-sm">
            {name}
            {selected?.attribute_name === name && (
              <span className="text-muted-foreground">: {selected.attribute_value}</span>
            )}
          </legend>
          <div className="flex flex-wrap gap-2">
            {options.map((v) => {
              const soldOut = (v.stock ?? 0) <= 0
              const active = selected?.id === v.id
              return (
                <button
                  key={v.id}
                  type="button"
                  disabled={soldOut}
                  onClick={() => onSelect(v)}
                  aria-pressed={active}
                  className={cn(
                    "min-w-12 rounded-full border px-4 py-2 text-sm transition",
                    active ? "border-foreground bg-foreground text-background" : "hover:border-foreground/50",
                    soldOut && "cursor-not-allowed text-muted-foreground line-through opacity-50",
                  )}
                >
                  {v.attribute_value}
                </button>
              )
            })}
          </div>
        </fieldset>
      ))}
    </div>
  )
}

function QuantityStepper({ value, max, onChange }: { value: number; max: number; onChange: (v: number) => void }) {
  return (
    <div className="inline-flex h-11 items-center rounded-full border">
      <button
        type="button"
        className="flex size-11 items-center justify-center rounded-full hover:bg-muted disabled:opacity-40"
        onClick={() => onChange(value - 1)}
        disabled={value <= 1}
        aria-label="Decrease quantity"
      >
        <MinusIcon className="size-4" />
      </button>
      <span className="w-8 text-center text-sm tabular-nums" aria-live="polite">
        {value}
      </span>
      <button
        type="button"
        className="flex size-11 items-center justify-center rounded-full hover:bg-muted disabled:opacity-40"
        onClick={() => onChange(value + 1)}
        disabled={value >= max}
        aria-label="Increase quantity"
      >
        <PlusIcon className="size-4" />
      </button>
    </div>
  )
}

function BuyBox({ product }: { product: ProductDetail }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const addToCart = useAddToCart()
  const stockAlert = useStockAlert(product.slug)
  const toggleWishlist = useToggleWishlist()
  const saved = useWishlistIds().has(product.id)
  const variants = product.variants.filter((v) => v.is_active !== false)
  const [variant, setVariant] = useState<Variant | undefined>(() => variants.find((v) => (v.stock ?? 0) > 0))
  const [quantity, setQuantity] = useState(1)

  const canBuy = !user || user.role === "customer"
  const price = variant?.price ?? product.price
  const stock = product.has_variants ? (variant?.stock ?? 0) : product.total_available_stock
  const inStock = product.has_variants ? stock > 0 : product.is_in_stock
  const max = Math.min(stock, 99)
  const needsLogin = () => navigate(`/login?next=${encodeURIComponent(`/products/${product.slug}`)}`)

  function add() {
    if (!user) return needsLogin()
    addToCart.mutate(
      { product: product.id, variant: variant?.id, quantity },
      {
        onSuccess: () =>
          toast.success(`Added to cart`, {
            description: `${quantity} × ${product.name}${variant ? ` (${variant.label})` : ""}`,
            action: { label: "View cart", onClick: () => navigate("/cart") },
          }),
      },
    )
  }

  function notify() {
    if (!user) return needsLogin()
    stockAlert.mutate(undefined, {
      onSuccess: () => toast.success("We’ll email you when it’s back in stock."),
      onError: (e) => toast.error(errorMessage(e)),
    })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {product.vendor ? (
            <Link to={`/stores/${product.vendor.store_slug}`} className="hover:text-foreground hover:underline">
              {product.vendor.business_name}
            </Link>
          ) : (
            "CoreCart"
          )}
          <span className="mx-1.5">·</span>
          <Link to={`/products?category=${product.category.slug}`} className="hover:text-foreground hover:underline">
            {product.category.name}
          </Link>
        </p>
        <h1 className="font-heading text-4xl leading-tight md:text-5xl">{product.name}</h1>
        <a href="#reviews" className="inline-block">
          <Rating average={product.average_rating} count={product.review_count} className="text-sm" />
        </a>
      </div>

      <p className="text-3xl font-semibold tabular-nums">{money(price)}</p>

      {variants.length > 0 && (
        <VariantPicker
          variants={variants}
          selected={variant}
          onSelect={(v) => {
            setVariant(v)
            setQuantity(1)
          }}
        />
      )}

      <p
        className={cn(
          "flex items-center gap-2 text-sm",
          !inStock ? "text-muted-foreground" : stock <= 5 ? "text-[oklch(0.55_0.13_65)] dark:text-warning" : "text-success",
        )}
      >
        <span className={cn("size-2 rounded-full", !inStock ? "bg-muted-foreground" : stock <= 5 ? "bg-warning" : "bg-success")} />
        {!inStock
          ? product.has_variants && !variant
            ? "Choose an option"
            : "Out of stock"
          : stock <= 5
            ? `Only ${stock} left`
            : "In stock, ready to ship"}
      </p>

      {canBuy && (
        <div className="flex flex-wrap items-center gap-3">
          {inStock ? (
            <>
              <QuantityStepper value={quantity} max={max} onChange={(v) => setQuantity(Math.max(1, Math.min(max, v)))} />
              <Button size="lg" className="h-11 flex-1 rounded-full" onClick={add} disabled={addToCart.isPending}>
                {addToCart.isPending ? <Spinner /> : <ShoppingBagIcon />}
                Add to cart
              </Button>
            </>
          ) : (
            <Button
              size="lg"
              variant="outline"
              className="h-11 flex-1 rounded-full"
              onClick={notify}
              disabled={stockAlert.isPending || stockAlert.isSuccess}
            >
              {stockAlert.isSuccess ? <CheckIcon /> : <BellIcon />}
              {stockAlert.isSuccess ? "We’ll let you know" : "Notify me when available"}
            </Button>
          )}
          <Button
            size="icon"
            variant="outline"
            className="size-11 rounded-full"
            aria-pressed={saved}
            aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
            onClick={() => (user ? toggleWishlist.mutate({ product, saved }) : needsLogin())}
          >
            <HeartIcon className={cn(saved && "fill-brand text-brand")} />
          </Button>
        </div>
      )}

      <ul className="space-y-2.5 rounded-2xl bg-muted/50 p-4 text-sm">
        <li className="flex items-center gap-3">
          <TruckIcon className="size-4 text-brand" /> Ships from the maker with tracking
        </li>
        <li className="flex items-center gap-3">
          <ShieldCheckIcon className="size-4 text-brand" /> Pay on delivery or by bank transfer
        </li>
      </ul>
    </div>
  )
}

function ReviewForm({ slug }: { slug: string }) {
  const create = useCreateReview(slug)
  const [rating, setRating] = useState(0)
  const [comment, setComment] = useState("")

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!rating) return toast.error("Please choose a star rating.")
    create.mutate(
      { rating, comment },
      {
        onSuccess: () => {
          toast.success("Thanks for your review!")
          setRating(0)
          setComment("")
        },
      },
    )
  }

  const err = create.error instanceof ApiError ? create.error : null
  if (err?.code === "duplicate_review")
    return <p className="text-sm text-muted-foreground">You have already reviewed this product. Thank you!</p>

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border p-5">
      <p className="font-medium">Write a review</p>
      <StarInput value={rating} onChange={setRating} />
      <Textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="What did you like or dislike?"
        aria-label="Review"
        rows={3}
        aria-invalid={Boolean(err?.fields.comment)}
      />
      {err && <p className="text-xs text-destructive">{err.fields.comment || err.fields.rating || err.message}</p>}
      <Button type="submit" disabled={create.isPending}>
        {create.isPending && <Spinner />} Post review
      </Button>
    </form>
  )
}

function Reviews({ product }: { product: ProductDetail }) {
  const { user } = useAuth()
  const [page, setPage] = useState(1)
  const { data, isPending } = useReviews(product.slug, page)
  const total = product.review_count ?? 0

  return (
    <div className="grid gap-10 md:grid-cols-[16rem_1fr]">
      <div className="space-y-5">
        <div>
          <p className="font-heading text-6xl">{Number(product.average_rating ?? 0).toFixed(1)}</p>
          <Stars value={Number(product.average_rating ?? 0)} />
          <p className="mt-1 text-sm text-muted-foreground">{pluralize(total, "review")}</p>
        </div>
        <div className="space-y-1.5">
          {[5, 4, 3, 2, 1].map((star) => {
            const n = product.rating_breakdown[String(star)] ?? 0
            return (
              <div key={star} className="flex items-center gap-2 text-xs">
                <span className="flex w-6 items-center gap-0.5 tabular-nums">
                  {star}
                  <StarIcon className="size-3 text-warning" fill="currentColor" strokeWidth={0} />
                </span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-warning" style={{ width: total ? `${(n / total) * 100}%` : 0 }} />
                </div>
                <span className="w-6 text-right text-muted-foreground tabular-nums">{n}</span>
              </div>
            )
          })}
        </div>
      </div>

      <div className="space-y-6">
        {user?.role === "customer" && <ReviewForm slug={product.slug} />}
        {!user && (
          <p className="text-sm text-muted-foreground">
            <Link to={`/login?next=/products/${product.slug}`} className="text-foreground underline">
              Sign in
            </Link>{" "}
            to write a review.
          </p>
        )}
        {isPending ? (
          <PageLoader />
        ) : !data?.results.length ? (
          <EmptyState icon={StarIcon} title="No reviews yet" description="Be the first to share your thoughts." />
        ) : (
          <ul className="divide-y">
            {data.results.map((r) => (
              <li key={r.id} className="space-y-2 py-5 first:pt-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Stars value={r.rating ?? 0} />
                  <span className="text-sm font-medium">{r.author}</span>
                  {r.is_verified_purchase && (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <CheckIcon className="size-3" /> Verified purchase
                    </span>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">{date(r.created_at)}</span>
                </div>
                {r.comment && <p className="text-sm leading-relaxed text-muted-foreground">{r.comment}</p>}
              </li>
            ))}
          </ul>
        )}
        {data && <Pager page={page} count={data.count} onPage={setPage} />}
      </div>
    </div>
  )
}

function Questions({ slug }: { slug: string }) {
  const { user } = useAuth()
  const [page, setPage] = useState(1)
  const { data, isPending } = useQuestions(slug, page)
  const ask = useAskQuestion(slug)
  const [question, setQuestion] = useState("")

  function submit(e: FormEvent) {
    e.preventDefault()
    ask.mutate(question, {
      onSuccess: () => {
        setQuestion("")
        toast.success("Question sent to the maker.")
      },
      onError: (err) => toast.error(err instanceof ApiError ? err.fields.question || err.message : errorMessage(err)),
    })
  }

  return (
    <div className="max-w-3xl space-y-6">
      {user?.role === "customer" && (
        <form onSubmit={submit} className="flex gap-2">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask the maker about sizing, materials, care…"
            aria-label="Your question"
            rows={2}
            required
          />
          <Button type="submit" className="self-end" disabled={ask.isPending || !question.trim()}>
            {ask.isPending && <Spinner />} Ask
          </Button>
        </form>
      )}
      {isPending ? (
        <PageLoader />
      ) : !data?.results.length ? (
        <EmptyState icon={MessageCircleQuestionIcon} title="No questions yet" description="Questions and answers appear here." />
      ) : (
        <ul className="space-y-4">
          {data.results.map((q) => (
            <li key={q.id} className="space-y-2 rounded-2xl border p-4">
              <p className="text-sm font-medium">Q: {q.question}</p>
              {q.is_answered ? (
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">A:</span> {q.answer}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Awaiting an answer from the maker</p>
              )}
              <p className="text-xs text-muted-foreground">
                {q.author} · {date(q.created_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
      {data && <Pager page={page} count={data.count} onPage={setPage} />}
    </div>
  )
}

export default function ProductPage() {
  const { slug = "" } = useParams()
  const { data: product, isPending, isError, error, refetch } = useProduct(slug)

  if (isPending) return <PageLoader />
  if (isError)
    return (
      <div className="container-page py-16">
        <ErrorState error={error} onRetry={() => refetch()} />
      </div>
    )

  return (
    <div className="container-page space-y-16 py-8 md:py-12">
      <Title>{product.name}</Title>
      <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
        <Link to="/products" className="hover:text-foreground">
          Shop
        </Link>
        <span className="mx-2">/</span>
        <Link to={`/products?category=${product.category.slug}`} className="hover:text-foreground">
          {product.category.name}
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">{product.name}</span>
      </nav>

      <div className="grid gap-10 md:grid-cols-2 lg:gap-16">
        <Gallery product={product} />
        <BuyBox key={product.id} product={product} />
      </div>

      <Tabs defaultValue="details" id="reviews" className="scroll-mt-24">
        <TabsList className="mb-6">
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="reviews">Reviews ({product.review_count ?? 0})</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
        </TabsList>
        <TabsContent value="details">
          <div className="max-w-3xl leading-relaxed whitespace-pre-line text-muted-foreground">
            {product.description || "The maker hasn’t added a description yet."}
          </div>
        </TabsContent>
        <TabsContent value="reviews">
          <Reviews product={product} />
        </TabsContent>
        <TabsContent value="questions">
          <Questions slug={product.slug} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

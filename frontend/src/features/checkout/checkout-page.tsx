import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BanknoteIcon, LockIcon, TagIcon, TruckIcon, XIcon } from "lucide-react"
import { useRef, useState, type FormEvent } from "react"
import { Link, Navigate, useNavigate } from "react-router"
import { toast } from "sonner"

import { api, ApiError, unwrap, type Schemas } from "@/api/client"
import { Field, formValues, TextField } from "@/components/common/field"
import { PageLoader, Spinner, errorMessage } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Separator } from "@/components/ui/separator"
import { CART_KEY } from "@/features/cart/api"
import { money } from "@/lib/format"
import { cn } from "@/lib/utils"
import { ME_KEY, useAuth } from "@/providers/auth"

type Preview = Schemas["CheckoutPreview"]

function usePreview(coupon: string) {
  return useQuery({
    queryKey: ["checkout-preview", coupon],
    queryFn: () => unwrap(api.POST("/api/v1/checkout/preview/", { body: { coupon_code: coupon } })),
    placeholderData: (prev) => prev,
  })
}

function usePaymentMethods() {
  return useQuery({
    queryKey: ["payment-methods"],
    queryFn: () => unwrap(api.GET("/api/v1/checkout/payment-methods/")) as Promise<{ value: string; label: string }[]>,
    staleTime: Infinity,
  })
}

const METHOD_ICONS: Record<string, typeof TruckIcon> = { cod: TruckIcon, bank_transfer: BanknoteIcon }

function Summary({ preview, coupon, onCoupon }: { preview: Preview; coupon: string; onCoupon: (c: string) => void }) {
  const [code, setCode] = useState(coupon)
  return (
    <aside className="h-fit space-y-5 rounded-2xl bg-muted/50 p-6 lg:sticky lg:top-24">
      <p className="font-medium">Order summary</p>
      <ul className="space-y-4">
        {preview.items.map((item) => (
          <li key={item.id} className="flex gap-3">
            <div className="relative size-14 shrink-0 overflow-hidden rounded-lg bg-muted">
              <ProductImage src={item.product.cover_image} name={item.product.name} size="sm" />
              <span className="absolute -top-0 -right-0 rounded-bl-md bg-foreground px-1.5 text-[10px] text-background tabular-nums">
                {item.quantity}
              </span>
            </div>
            <div className="min-w-0 flex-1 text-sm">
              <p className="line-clamp-1">{item.product.name}</p>
              {item.variant && <p className="text-xs text-muted-foreground">{item.variant.label}</p>}
              {item.problem && <p className="text-xs text-destructive">{item.problem}</p>}
            </div>
            <p className="text-sm tabular-nums">{money(item.subtotal)}</p>
          </li>
        ))}
      </ul>

      <Separator />
      {preview.coupon_code ? (
        <div className="flex items-center justify-between rounded-lg bg-success-soft px-3 py-2 text-sm">
          <span className="flex items-center gap-2 text-success">
            <TagIcon className="size-4" /> {preview.coupon_code}
          </span>
          <button type="button" onClick={() => (setCode(""), onCoupon(""))} aria-label="Remove coupon" className="text-muted-foreground hover:text-foreground">
            <XIcon className="size-4" />
          </button>
        </div>
      ) : (
        <form
          className="space-y-1.5"
          onSubmit={(e) => {
            e.preventDefault()
            onCoupon(code.trim())
          }}
        >
          <div className="flex gap-2">
            <Input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="Coupon code" aria-label="Coupon code" />
            <Button type="submit" variant="outline" disabled={!code.trim()}>
              Apply
            </Button>
          </div>
          {preview.coupon_error && coupon && <p className="text-xs text-destructive">{preview.coupon_error}</p>}
        </form>
      )}

      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Subtotal</dt>
          <dd className="tabular-nums">{money(preview.subtotal)}</dd>
        </div>
        {Number(preview.discount) > 0 && (
          <div className="flex justify-between text-success">
            <dt>Discount</dt>
            <dd className="tabular-nums">−{money(preview.discount)}</dd>
          </div>
        )}
        <Separator />
        <div className="flex justify-between text-base font-semibold">
          <dt>Total</dt>
          <dd className="tabular-nums">{money(preview.total)}</dd>
        </div>
      </dl>
    </aside>
  )
}

export default function CheckoutPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [coupon, setCoupon] = useState("")
  const preview = usePreview(coupon)
  const methods = usePaymentMethods()
  const [method, setMethod] = useState<string>()
  // One key per checkout attempt: retries (double click, flaky network) return the same order.
  const idempotencyKey = useRef(crypto.randomUUID())

  const place = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      unwrap(
        api.POST("/api/v1/checkout/", {
          body: body as unknown as Schemas["CheckoutRequest"],
          params: { header: { "Idempotency-Key": idempotencyKey.current } },
        }),
      ),
    onSuccess: (order) => {
      qc.removeQueries({ queryKey: ["checkout-preview"] })
      qc.invalidateQueries({ queryKey: CART_KEY })
      qc.invalidateQueries({ queryKey: ME_KEY })
      navigate(`/checkout/success/${order.order_number}`, { replace: true })
    },
    onError: (err) => {
      // Stock/price conflicts: the cart changed, so refresh totals and allow a new attempt.
      if (err instanceof ApiError && err.status === 409) {
        idempotencyKey.current = crypto.randomUUID()
        preview.refetch()
        qc.invalidateQueries({ queryKey: CART_KEY })
      }
      if (!(err instanceof ApiError && Object.keys(err.fields).length)) toast.error(errorMessage(err))
    },
  })

  if (preview.isPending || methods.isPending) return <PageLoader />
  if (preview.data && !preview.data.items.length && !place.isPending) return <Navigate to="/cart" replace />
  if (!preview.data) return <PageLoader />

  const profile = user?.customer_profile
  const fields = place.error instanceof ApiError ? place.error.fields : {}
  const selected = method ?? methods.data?.[0]?.value
  const blocked = preview.data.problems.length > 0

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const values = formValues(e.currentTarget)
    place.mutate({
      ...values,
      payment_method: selected,
      coupon_code: preview.data?.coupon_code ?? "",
      save_address: values.save_address === "on",
    })
  }

  return (
    <div className="container-page py-10">
      <Title>Checkout</Title>
      <div className="mb-8 flex items-center justify-between">
        <h1 className="font-heading text-4xl">Checkout</h1>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <LockIcon className="size-3.5" /> Secure checkout
        </p>
      </div>
      <div className="grid gap-10 lg:grid-cols-[1fr_24rem]">
        <form id="checkout" onSubmit={submit} className="space-y-10">
          {blocked && (
            <Alert variant="destructive">
              <AlertDescription>
                {preview.data.problems.join(" ")}{" "}
                <Link to="/cart" className="underline">
                  Review your cart
                </Link>
              </AlertDescription>
            </Alert>
          )}

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Delivery address</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Full name"
                name="full_name"
                autoComplete="name"
                required
                defaultValue={[user?.first_name, user?.last_name].filter(Boolean).join(" ")}
                error={fields.full_name}
              />
              <Field label="Phone" name="phone" type="tel" autoComplete="tel" required defaultValue={user?.phone} error={fields.phone} />
            </div>
            <Field label="Address" name="address" autoComplete="street-address" required defaultValue={profile?.address} error={fields.address} />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="City" name="city" autoComplete="address-level2" required defaultValue={profile?.city} error={fields.city} />
              <Field label="State" name="state" autoComplete="address-level1" defaultValue={profile?.state} error={fields.state} />
              <Field label="Postal code" name="postal_code" autoComplete="postal-code" required defaultValue={profile?.zip_code} error={fields.postal_code} />
            </div>
            <Field label="Country" name="country" autoComplete="country-name" required defaultValue={profile?.country || "USA"} error={fields.country} />
            <div className="flex items-center gap-2">
              <Checkbox id="save_address" name="save_address" defaultChecked={!profile?.address} />
              <Label htmlFor="save_address" className="font-normal">
                Save this address to my account
              </Label>
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Payment</h2>
            <RadioGroup value={selected} onValueChange={setMethod} className="gap-3">
              {methods.data?.map((m) => {
                const Icon = METHOD_ICONS[m.value] ?? BanknoteIcon
                return (
                  <Label
                    key={m.value}
                    htmlFor={`pm-${m.value}`}
                    className={cn(
                      "flex cursor-pointer items-center gap-4 rounded-xl border p-4 font-normal transition",
                      selected === m.value && "border-foreground bg-muted/40",
                    )}
                  >
                    <RadioGroupItem id={`pm-${m.value}`} value={m.value} />
                    <Icon className="size-5 text-brand" />
                    <span className="text-sm">{m.label}</span>
                  </Label>
                )
              })}
            </RadioGroup>
            {fields.payment_method && <p className="text-xs text-destructive">{fields.payment_method}</p>}
            <p className="text-xs text-muted-foreground">
              No card needed. Your order is confirmed now and marked paid once payment is received.
            </p>
          </section>

          <TextField label="Note for the maker (optional)" name="customer_note" rows={2} maxLength={500} error={fields.customer_note} />

          <Button type="submit" size="lg" className="w-full lg:hidden" disabled={place.isPending || blocked}>
            {place.isPending && <Spinner />} Place order · {money(preview.data.total)}
          </Button>
        </form>

        <div className="space-y-4">
          <Summary preview={preview.data} coupon={coupon} onCoupon={setCoupon} />
          <Button type="submit" form="checkout" size="lg" className="hidden w-full lg:flex" disabled={place.isPending || blocked}>
            {place.isPending && <Spinner />} Place order · {money(preview.data.total)}
          </Button>
        </div>
      </div>
    </div>
  )
}

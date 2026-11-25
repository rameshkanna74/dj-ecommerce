import { ShoppingBagIcon, StoreIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"

import { ApiError } from "@/api/client"
import { Field, formValues, TextField } from "@/components/common/field"
import { homeFor } from "@/components/common/guards"
import { Spinner, errorMessage } from "@/components/common/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { AuthShell } from "@/features/auth/auth-shell"
import { cn } from "@/lib/utils"
import { useAuth } from "@/providers/auth"

type Kind = "customer" | "vendor"

export default function RegisterPage() {
  const { acceptTokens } = useAuth()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const kind: Kind = params.get("type") === "vendor" ? "vendor" : "customer"
  const [fields, setFields] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const values: Record<string, unknown> = { ...formValues(form), use_cookie: true }
    values.newsletter_subscribed = values.newsletter_subscribed === "on"
    values.accept_terms = values.accept_terms === "on"
    setPending(true)
    setError(null)
    setFields({})
    try {
      const res = await fetch(`/api/v1/auth/register/${kind}/`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new ApiError(res.status, body)
      const user = await acceptTokens((body as { access: string }).access)
      navigate(homeFor(user), { replace: true })
    } catch (err) {
      if (err instanceof ApiError) setFields(err.fields)
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  const f = (name: string) => fields[name]

  return (
    <AuthShell
      wide
      title={kind === "vendor" ? "Open your store" : "Create your account"}
      subtitle={
        kind === "vendor"
          ? "Tell us about your business. We review every application, usually within two working days."
          : "Join to check out, track orders and save favourites."
      }
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <div className="mb-6 grid grid-cols-2 gap-2 rounded-xl bg-muted p-1" role="tablist" aria-label="Account type">
        {(
          [
            ["customer", "I want to shop", ShoppingBagIcon],
            ["vendor", "I want to sell", StoreIcon],
          ] as const
        ).map(([value, label, Icon]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={kind === value}
            onClick={() => {
              setParams(value === "vendor" ? { type: "vendor" } : {}, { replace: true })
              setFields({})
              setError(null)
            }}
            className={cn(
              "flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm transition",
              kind === value ? "bg-background font-medium shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-4" /> {label}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-4" noValidate={false}>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First name" name="first_name" autoComplete="given-name" required error={f("first_name")} />
          <Field label="Last name" name="last_name" autoComplete="family-name" required error={f("last_name")} />
        </div>
        <Field label="Email" name="email" type="email" autoComplete="email" required error={f("email")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Username" name="username" autoComplete="username" required error={f("username")} />
          <Field label="Phone (optional)" name="phone" type="tel" autoComplete="tel" error={f("phone")} />
        </div>
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          error={f("password")}
          hint="At least 8 characters; avoid common passwords."
        />

        {kind === "vendor" ? (
          <>
            <Separator className="my-2" />
            <p className="text-sm font-medium">Business details</p>
            <Field label="Business name" name="business_name" required error={f("business_name")} />
            <TextField
              label="What do you make?"
              name="business_description"
              rows={2}
              error={f("business_description")}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Business email" name="business_email" type="email" required error={f("business_email")} />
              <Field label="Business phone" name="business_phone" type="tel" required error={f("business_phone")} />
            </div>
            <Field label="Address" name="business_address" autoComplete="street-address" required error={f("business_address")} />
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="City" name="business_city" required error={f("business_city")} />
              <Field label="State" name="business_state" required error={f("business_state")} />
              <Field label="ZIP" name="business_zip_code" required error={f("business_zip_code")} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Country" name="business_country" defaultValue="USA" error={f("business_country")} />
              <Field label="Tax ID (optional)" name="tax_id" error={f("tax_id")} />
            </div>
            <div className="flex items-start gap-2">
              <Checkbox id="accept_terms" name="accept_terms" required className="mt-0.5" />
              <Label htmlFor="accept_terms" className="leading-snug font-normal">
                I agree to the seller terms and the platform commission.
              </Label>
            </div>
            {f("accept_terms") && <p className="text-xs text-destructive">{f("accept_terms")}</p>}
          </>
        ) : (
          <div className="flex items-start gap-2">
            <Checkbox id="newsletter" name="newsletter_subscribed" className="mt-0.5" />
            <Label htmlFor="newsletter" className="leading-snug font-normal">
              Send me new arrivals and occasional offers
            </Label>
          </div>
        )}

        <Button type="submit" className="w-full" size="lg" disabled={pending}>
          {pending && <Spinner />} {kind === "vendor" ? "Submit application" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  )
}

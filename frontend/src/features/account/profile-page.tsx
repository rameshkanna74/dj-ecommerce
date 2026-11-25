import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"
import { toast } from "sonner"

import { api, ApiError, unwrap, type Schemas } from "@/api/client"
import { Field, formValues } from "@/components/common/field"
import { PageHeader } from "@/components/common/page-header"
import { Spinner, errorMessage } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { date } from "@/lib/format"
import { ME_KEY, useAuth } from "@/providers/auth"

export default function ProfilePage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [email, setEmail] = useState(user?.email ?? "")
  const save = useMutation({
    mutationFn: (body: Schemas["PatchedUserRequest"]) => unwrap(api.PATCH("/api/v1/me/", { body })),
    onSuccess: (fresh) => {
      qc.setQueryData(ME_KEY, fresh)
      toast.success("Profile saved")
    },
    onError: (err) => {
      if (!(err instanceof ApiError && Object.keys(err.fields).length)) toast.error(errorMessage(err))
    },
  })
  if (!user) return null

  const fields = save.error instanceof ApiError ? save.error.fields : {}
  const emailChanged = email.trim().toLowerCase() !== user.email.toLowerCase()
  const profile = user.customer_profile

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const v = formValues(e.currentTarget)
    const body: Schemas["PatchedUserRequest"] = {
      first_name: v.first_name,
      last_name: v.last_name,
      phone: v.phone,
      email: v.email,
      ...(emailChanged ? { current_password: v.current_password } : {}),
    }
    if (user?.role === "customer") {
      body.customer_profile = {
        address: v.address,
        city: v.city,
        state: v.state,
        zip_code: v.zip_code,
        country: v.country,
        newsletter_subscribed: v.newsletter_subscribed === "on",
        email_notifications: v.email_notifications === "on",
      }
    }
    save.mutate(body)
  }

  return (
    <div className="max-w-3xl space-y-8">
      <Title>Profile</Title>
      <PageHeader
        title="Profile"
        description={`Member since ${date(user.date_joined)} · @${user.username}`}
        actions={user.vendor && <StatusBadge status={user.vendor.approval_status} label={`Vendor: ${user.vendor.approval_status_display}`} />}
      />
      <form onSubmit={submit} className="space-y-6">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>Personal details</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="First name" name="first_name" defaultValue={user.first_name} error={fields.first_name} />
            <Field label="Last name" name="last_name" defaultValue={user.last_name} error={fields.last_name} />
            <Field
              label="Email"
              name="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={fields.email}
            />
            <Field label="Phone" name="phone" type="tel" defaultValue={user.phone} error={fields.phone} />
            {emailChanged && (
              <Field
                className="sm:col-span-2"
                label="Current password"
                name="current_password"
                type="password"
                autoComplete="current-password"
                required
                hint="Required to change your email address."
                error={fields.current_password}
              />
            )}
          </CardContent>
        </Card>

        {user.role === "customer" && profile && (
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>Default delivery address</CardTitle>
              <CardDescription>Pre-filled at checkout.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <Field className="sm:col-span-2" label="Address" name="address" defaultValue={profile.address} />
              <Field label="City" name="city" defaultValue={profile.city} />
              <Field label="State" name="state" defaultValue={profile.state} />
              <Field label="Postal code" name="zip_code" defaultValue={profile.zip_code} />
              <Field label="Country" name="country" defaultValue={profile.country} />
              <div className="flex items-center justify-between gap-3 sm:col-span-2">
                <Label htmlFor="newsletter_subscribed" className="font-normal">
                  Newsletter: new arrivals and offers
                </Label>
                <Switch id="newsletter_subscribed" name="newsletter_subscribed" defaultChecked={profile.newsletter_subscribed} />
              </div>
              <div className="flex items-center justify-between gap-3 sm:col-span-2">
                <Label htmlFor="email_notifications" className="font-normal">
                  Order update emails
                </Label>
                <Switch id="email_notifications" name="email_notifications" defaultChecked={profile.email_notifications} />
              </div>
            </CardContent>
          </Card>
        )}

        <Button type="submit" disabled={save.isPending}>
          {save.isPending && <Spinner />} Save changes
        </Button>
      </form>
    </div>
  )
}

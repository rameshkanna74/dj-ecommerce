import { useMutation } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"
import { toast } from "sonner"

import { api, ApiError, setAccessToken, unwrap } from "@/api/client"
import { Field, formValues } from "@/components/common/field"
import { PageHeader } from "@/components/common/page-header"
import { Spinner, errorMessage } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

export default function SecurityPage() {
  const [mismatch, setMismatch] = useState<string>()
  const change = useMutation({
    mutationFn: (body: { old_password: string; new_password: string }) =>
      unwrap(api.POST("/api/v1/auth/password/change/", { body })),
    onSuccess: (tokens) => {
      // Every older token is revoked server-side; keep this session alive with the new pair.
      setAccessToken((tokens as { access: string }).access)
      toast.success("Password changed. Other devices have been signed out.")
    },
    onError: (err) => {
      if (!(err instanceof ApiError && Object.keys(err.fields).length)) toast.error(errorMessage(err))
    },
  })
  const fields = change.error instanceof ApiError ? change.error.fields : {}

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const v = formValues(form)
    if (v.new_password !== v.confirm) return setMismatch("The two passwords don’t match.")
    setMismatch(undefined)
    change.mutate({ old_password: v.old_password, new_password: v.new_password }, { onSuccess: () => form.reset() })
  }

  return (
    <div className="max-w-xl space-y-8">
      <Title>Password</Title>
      <PageHeader title="Password" description="Changing your password signs you out everywhere else." />
      <Card className="shadow-none">
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Current password" name="old_password" type="password" autoComplete="current-password" required error={fields.old_password} />
            <Field label="New password" name="new_password" type="password" autoComplete="new-password" required minLength={8} error={fields.new_password} />
            <Field label="Confirm new password" name="confirm" type="password" autoComplete="new-password" required error={mismatch} />
            <Button type="submit" disabled={change.isPending}>
              {change.isPending && <Spinner />} Update password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

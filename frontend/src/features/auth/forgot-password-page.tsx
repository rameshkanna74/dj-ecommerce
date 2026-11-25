import { MailCheckIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link } from "react-router"

import { api, unwrap } from "@/api/client"
import { Field, formValues } from "@/components/common/field"
import { Spinner, errorMessage } from "@/components/common/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AuthShell } from "@/features/auth/auth-shell"

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const { email } = formValues(e.currentTarget)
    setPending(true)
    setError(null)
    try {
      await unwrap(api.POST("/api/v1/auth/password/reset/", { body: { email } }))
      setSent(email)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter the email you signed up with and we’ll send you a reset link."
      footer={
        <Link to="/login" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl bg-success-soft p-6 text-center">
          <MailCheckIcon className="size-8 text-success" />
          <p className="font-medium">Check your inbox</p>
          <p className="text-sm text-muted-foreground">
            If an account exists for <span className="font-medium text-foreground">{sent}</span>, a reset link is on its
            way. It expires in a few days.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Field label="Email" name="email" type="email" autoComplete="email" required autoFocus />
          <Button type="submit" className="w-full" size="lg" disabled={pending}>
            {pending && <Spinner />} Send reset link
          </Button>
        </form>
      )}
    </AuthShell>
  )
}

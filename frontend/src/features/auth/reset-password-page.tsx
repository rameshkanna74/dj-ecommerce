import { CircleCheckIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useSearchParams } from "react-router"

import { api, ApiError, unwrap } from "@/api/client"
import { Field, formValues } from "@/components/common/field"
import { Spinner, errorMessage } from "@/components/common/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AuthShell } from "@/features/auth/auth-shell"

/** Target of the reset email link: /reset-password?uid=…&token=… */
export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const uid = params.get("uid") ?? ""
  const token = params.get("token") ?? ""
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string>()
  const [pending, setPending] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const { new_password, confirm } = formValues(e.currentTarget)
    if (new_password !== confirm) return setFieldError("The two passwords don’t match.")
    setPending(true)
    setError(null)
    setFieldError(undefined)
    try {
      await unwrap(api.POST("/api/v1/auth/password/reset/confirm/", { body: { uid, token, new_password } }))
      setDone(true)
    } catch (err) {
      if (err instanceof ApiError && (err.fields.new_password || err.fields.token)) {
        setFieldError(err.fields.new_password)
        setError(err.fields.token ?? null)
      } else setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  if (!uid || !token)
    return (
      <AuthShell title="Invalid link" subtitle="This reset link is incomplete.">
        <Button asChild className="w-full">
          <Link to="/forgot-password">Request a new link</Link>
        </Button>
      </AuthShell>
    )

  return (
    <AuthShell title="Choose a new password" subtitle="You’ll be signed out on every other device.">
      {done ? (
        <div className="space-y-4 text-center">
          <CircleCheckIcon className="mx-auto size-10 text-success" />
          <p className="font-medium">Your password has been changed.</p>
          <Button asChild className="w-full" size="lg">
            <Link to="/login">Sign in</Link>
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>
                {error}{" "}
                <Link to="/forgot-password" className="underline">
                  Request a new link
                </Link>
              </AlertDescription>
            </Alert>
          )}
          <Field label="New password" name="new_password" type="password" autoComplete="new-password" required minLength={8} error={fieldError} />
          <Field label="Confirm password" name="confirm" type="password" autoComplete="new-password" required />
          <Button type="submit" className="w-full" size="lg" disabled={pending}>
            {pending && <Spinner />} Save password
          </Button>
        </form>
      )}
    </AuthShell>
  )
}

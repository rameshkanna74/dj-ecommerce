import { useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"

import { Field, formValues } from "@/components/common/field"
import { homeFor, safeNext } from "@/components/common/guards"
import { Spinner, errorMessage } from "@/components/common/states"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { AuthShell } from "@/features/auth/auth-shell"
import { useAuth } from "@/providers/auth"

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const { username, password } = formValues(e.currentTarget)
    setPending(true)
    setError(null)
    try {
      const user = await login(username.trim(), password)
      navigate(safeNext(params.get("next"), homeFor(user)), { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to track orders, save favourites and check out faster."
      footer={
        <>
          New here?{" "}
          <Link to="/register" className="font-medium text-foreground underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Field label="Email or username" name="username" autoComplete="username" required autoFocus />
        <div className="space-y-1.5">
          <Field label="Password" name="password" type="password" autoComplete="current-password" required />
          <div className="text-right">
            <Link to="/forgot-password" className="text-xs text-muted-foreground hover:text-foreground">
              Forgot password?
            </Link>
          </div>
        </div>
        <Button type="submit" className="w-full" size="lg" disabled={pending}>
          {pending && <Spinner />} Sign in
        </Button>
      </form>
    </AuthShell>
  )
}

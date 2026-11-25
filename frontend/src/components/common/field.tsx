import { useId, type ComponentProps, type ReactNode } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

interface FieldShellProps {
  label: ReactNode
  error?: string
  hint?: ReactNode
  className?: string
  children: (id: string, describedBy?: string) => ReactNode
}

export function FieldShell({ label, error, hint, className, children }: FieldShellProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className={cn("grid gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children(id, describedBy)}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  )
}

type FieldProps = ComponentProps<typeof Input> & { label: ReactNode; error?: string; hint?: ReactNode }

/** Labelled input that shows a DRF field error (``ApiError.fields[name]``). */
export function Field({ label, error, hint, className, ...props }: FieldProps) {
  return (
    <FieldShell label={label} error={error} hint={hint} className={className}>
      {(id, describedBy) => (
        <Input id={id} aria-invalid={Boolean(error)} aria-describedby={describedBy} {...props} />
      )}
    </FieldShell>
  )
}

type TextFieldProps = ComponentProps<typeof Textarea> & { label: ReactNode; error?: string; hint?: ReactNode }

export function TextField({ label, error, hint, className, ...props }: TextFieldProps) {
  return (
    <FieldShell label={label} error={error} hint={hint} className={className}>
      {(id, describedBy) => (
        <Textarea id={id} aria-invalid={Boolean(error)} aria-describedby={describedBy} {...props} />
      )}
    </FieldShell>
  )
}

/** Read a <form> into a plain object of strings (checkboxes become booleans). */
export function formValues(form: HTMLFormElement): Record<string, string> {
  return Object.fromEntries(new FormData(form).entries()) as Record<string, string>
}

import { SearchIcon } from "lucide-react"
import { useDeferredValue, useState, type ReactNode } from "react"

import { Spinner } from "@/components/common/states"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

/** Debounced-by-render search box; returns the deferred value for queries. */
export function useSearch() {
  const [value, setValue] = useState("")
  const deferred = useDeferredValue(value.trim())
  return { value, setValue, query: deferred || undefined }
}

export function SearchInput({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <div className="relative w-full sm:w-72">
      <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} className="pl-9" />
    </div>
  )
}

/**
 * Confirmation dialog with an optional free-text field (reason, payment reference, ...).
 * ``onConfirm`` returns a promise; the dialog stays open on failure so the admin can retry.
 */
export function ConfirmAction({
  trigger,
  title,
  description,
  confirmLabel,
  inputLabel,
  inputPlaceholder,
  inputRequired = false,
  destructive = false,
  onConfirm,
}: {
  trigger: ReactNode
  title: string
  description?: ReactNode
  confirmLabel: string
  inputLabel?: string
  inputPlaceholder?: string
  inputRequired?: boolean
  destructive?: boolean
  onConfirm: (text: string) => Promise<unknown>
}) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const [pending, setPending] = useState(false)

  async function confirm() {
    setPending(true)
    try {
      await onConfirm(text.trim())
      setOpen(false)
      setText("")
    } catch {
      /* the mutation already toasted the error */
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {inputLabel && (
          <div className="grid gap-1.5">
            <Label htmlFor="confirm-input">{inputLabel}</Label>
            <Textarea id="confirm-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={inputPlaceholder} rows={3} maxLength={500} />
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant={destructive ? "destructive" : "default"} onClick={confirm} disabled={pending || (inputRequired && !text.trim())}>
            {pending && <Spinner />} {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function TableShell({ children, dimmed }: { children: ReactNode; dimmed?: boolean }) {
  return <div className={cn("overflow-x-auto rounded-2xl border", dimmed && "opacity-60 transition-opacity")}>{children}</div>
}

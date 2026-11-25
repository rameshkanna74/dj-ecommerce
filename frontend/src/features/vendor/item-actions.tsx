import { TruckIcon } from "lucide-react"
import { useState, type FormEvent } from "react"

import { Spinner } from "@/components/common/states"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { ItemStatus } from "@/features/vendor/api"

const ACTION_LABELS: Record<string, string> = {
  processing: "Start processing",
  shipped: "Mark shipped",
  delivered: "Mark delivered",
  cancelled: "Cancel item",
}
const ORDER = ["processing", "shipped", "delivered", "cancelled"]

/**
 * Buttons for the transitions the API allows (``allowed_next_statuses``). Shipping asks for
 * a tracking number, which the backend requires. Reused by the vendor and staff consoles.
 */
export function ItemActions({
  allowed,
  currentTracking,
  pending,
  onChange,
  size = "sm",
}: {
  allowed: string[]
  currentTracking?: string | null
  pending?: boolean
  onChange: (status: ItemStatus, tracking?: string) => void
  size?: "sm" | "xs"
}) {
  const [shipping, setShipping] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [tracking, setTracking] = useState(currentTracking ?? "")
  const actions = ORDER.filter((s) => allowed.includes(s))
  if (!actions.length) return null

  function confirmShip(e: FormEvent) {
    e.preventDefault()
    onChange("shipped", tracking.trim())
    setShipping(false)
  }

  return (
    <div className="flex flex-wrap justify-end gap-1.5">
      {actions.map((status) => (
        <Button
          key={status}
          size={size}
          variant={status === "cancelled" ? "ghost" : status === actions[0] ? "default" : "outline"}
          className={status === "cancelled" ? "text-destructive hover:text-destructive" : undefined}
          disabled={pending}
          onClick={(e) => {
            e.stopPropagation()
            if (status === "shipped") setShipping(true)
            else if (status === "cancelled") setCancelling(true)
            else onChange(status as ItemStatus)
          }}
        >
          {pending && status === actions[0] && <Spinner />}
          {ACTION_LABELS[status]}
        </Button>
      ))}
      <Dialog open={cancelling} onOpenChange={setCancelling}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Cancel this item?</DialogTitle>
            <DialogDescription>
              The stock goes back to inventory and the order total is recalculated. This can’t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCancelling(false)}>
              Keep item
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                onChange("cancelled")
                setCancelling(false)
              }}
            >
              Cancel item
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={shipping} onOpenChange={setShipping}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <form onSubmit={confirmShip} className="space-y-4">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <TruckIcon className="size-5 text-brand" /> Mark as shipped
              </DialogTitle>
              <DialogDescription>The customer sees this tracking number on their order.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-1.5">
              <Label htmlFor="tracking">Tracking number</Label>
              <Input id="tracking" value={tracking} onChange={(e) => setTracking(e.target.value)} required maxLength={100} autoFocus />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setShipping(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!tracking.trim()}>
                Confirm shipment
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

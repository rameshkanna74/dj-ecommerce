import { PencilIcon, PlusIcon, TicketPercentIcon, Trash2Icon } from "lucide-react"
import { useState, type FormEvent } from "react"

import { ApiError } from "@/api/client"
import { Field, FieldShell, formValues, TextField } from "@/components/common/field"
import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useCoupons, useDeleteCoupon, useSaveCoupon, type Coupon } from "@/features/staff/api"
import { ConfirmAction, TableShell } from "@/features/staff/shared"
import { date, money } from "@/lib/format"

/** ISO string -> value for <input type="datetime-local"> in the viewer's timezone. */
function toLocalInput(iso?: string) {
  const d = iso ? new Date(iso) : new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function couponState(c: Coupon) {
  const now = Date.now()
  if (!c.active) return { tone: "neutral" as const, label: "Off" }
  if (new Date(c.valid_to).getTime() < now) return { tone: "danger" as const, label: "Expired" }
  if (new Date(c.valid_from).getTime() > now) return { tone: "info" as const, label: "Scheduled" }
  if ((c.used_count ?? 0) >= (c.usage_limit ?? Infinity)) return { tone: "warning" as const, label: "Used up" }
  return { tone: "success" as const, label: "Live" }
}

function CouponDialog({ coupon, onClose }: { coupon?: Coupon; onClose: () => void }) {
  const save = useSaveCoupon()
  const [type, setType] = useState<string>(coupon?.discount_type ?? "percentage")
  const [active, setActive] = useState(coupon?.active ?? true)
  const [defaultEnd] = useState(() => new Date(Date.now() + 30 * 86_400_000).toISOString())
  const fields = save.error instanceof ApiError ? save.error.fields : {}

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const v = formValues(e.currentTarget)
    save.mutate(
      {
        id: coupon?.id,
        code: v.code.toUpperCase(),
        description: v.description,
        discount_type: type as Coupon["discount_type"],
        value: v.value,
        min_order_amount: v.min_order_amount || "0",
        usage_limit: Number(v.usage_limit),
        valid_from: new Date(v.valid_from).toISOString(),
        valid_to: new Date(v.valid_to).toISOString(),
        active,
      },
      { onSuccess: onClose },
    )
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{coupon ? `Edit ${coupon.code}` : "New coupon"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Code" name="code" required maxLength={50} defaultValue={coupon?.code} error={fields.code} className="uppercase" />
          <FieldShell label="Type" error={fields.discount_type}>
            {(id) => (
              <Select value={type} onValueChange={setType}>
                <SelectTrigger id={id} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="percentage">Percentage off</SelectItem>
                  <SelectItem value="fixed">Fixed amount off</SelectItem>
                </SelectContent>
              </Select>
            )}
          </FieldShell>
          <Field label={type === "percentage" ? "Percent (1–100)" : "Amount"} name="value" type="number" step="0.01" min="0.01" max={type === "percentage" ? 100 : undefined} required defaultValue={coupon?.value} error={fields.value} />
          <Field label="Minimum order" name="min_order_amount" type="number" step="0.01" min="0" defaultValue={coupon?.min_order_amount ?? "0"} error={fields.min_order_amount} />
          <Field label="Valid from" name="valid_from" type="datetime-local" required defaultValue={toLocalInput(coupon?.valid_from)} error={fields.valid_from} />
          <Field
            label="Valid until"
            name="valid_to"
            type="datetime-local"
            required
            defaultValue={toLocalInput(coupon?.valid_to ?? defaultEnd)}
            error={fields.valid_to}
          />
          <Field
            label="Usage limit"
            name="usage_limit"
            type="number"
            min={coupon?.used_count ?? 1}
            required
            defaultValue={coupon?.usage_limit ?? 100}
            error={fields.usage_limit}
            hint={coupon ? `Used ${coupon.used_count} times so far` : undefined}
          />
          <div className="flex items-center justify-between gap-3 self-end rounded-lg border px-3 py-2">
            <Label htmlFor="coupon-active" className="font-normal">
              Active
            </Label>
            <Switch id="coupon-active" checked={active} onCheckedChange={setActive} />
          </div>
          <TextField className="sm:col-span-2" label="Description (internal)" name="description" rows={2} defaultValue={coupon?.description} error={fields.description} />
          {fields.non_field_errors && <p className="text-xs text-destructive sm:col-span-2">{fields.non_field_errors}</p>}
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Spinner />} Save coupon
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function StaffCouponsPage() {
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Coupon | "new" | null>(null)
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useCoupons(page)
  const remove = useDeleteCoupon()

  return (
    <div className="space-y-6">
      <Title>Coupons</Title>
      <PageHeader
        title="Coupons"
        description="Discounts are funded by the platform and don’t reduce vendor earnings."
        actions={
          <Button onClick={() => setEditing("new")}>
            <PlusIcon /> New coupon
          </Button>
        }
      />
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={TicketPercentIcon} title="No coupons yet" action={<Button onClick={() => setEditing("new")}>Create one</Button>} />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Discount</TableHead>
                  <TableHead>Valid</TableHead>
                  <TableHead className="text-right">Used</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((c) => {
                  const state = couponState(c)
                  return (
                    <TableRow key={c.id}>
                      <TableCell>
                        <p className="font-mono font-medium">{c.code}</p>
                        {c.description && <p className="max-w-56 truncate text-xs text-muted-foreground">{c.description}</p>}
                      </TableCell>
                      <TableCell>
                        {c.discount_type === "percentage" ? `${Number(c.value)}% off` : `${money(c.value)} off`}
                        {Number(c.min_order_amount) > 0 && <p className="text-xs text-muted-foreground">min {money(c.min_order_amount)}</p>}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {date(c.valid_from)} – {date(c.valid_to)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {c.used_count} / {c.usage_limit}
                      </TableCell>
                      <TableCell>
                        <StatusBadge tone={state.tone} label={state.label} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button size="icon" variant="ghost" onClick={() => setEditing(c)} aria-label={`Edit ${c.code}`}>
                            <PencilIcon />
                          </Button>
                          <ConfirmAction
                            trigger={
                              <Button size="icon" variant="ghost" aria-label={`Delete ${c.code}`}>
                                <Trash2Icon />
                              </Button>
                            }
                            title={`Delete ${c.code}?`}
                            description="Past orders keep their discount. Consider switching it off instead."
                            confirmLabel="Delete"
                            destructive
                            onConfirm={() => remove.mutateAsync(c.id)}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableShell>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
      {editing && <CouponDialog coupon={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

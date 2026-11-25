import { BanIcon, CheckIcon, StoreIcon, XIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useSearchParams } from "react-router"

import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useStaffVendors, useUpdateVendor, useVendorAction, type StaffVendor } from "@/features/staff/api"
import { ConfirmAction, TableShell } from "@/features/staff/shared"
import { date } from "@/lib/format"

function Detail({ vendor, onClose }: { vendor: StaffVendor; onClose: () => void }) {
  const act = useVendorAction()
  const update = useUpdateVendor()
  const [rate, setRate] = useState(vendor.commission_rate ?? "")
  const rows: [string, string | undefined | null][] = [
    ["Account", `${vendor.username} · ${vendor.email}`],
    ["Business email", vendor.business_email],
    ["Phone", vendor.business_phone],
    ["Address", [vendor.business_address, vendor.business_city, vendor.business_state, vendor.business_zip_code, vendor.business_country].filter(Boolean).join(", ")],
    ["Tax ID", vendor.tax_id],
    ["Registration no.", vendor.business_registration_number],
    ["Applied", date(vendor.created_at)],
    ["Approved", vendor.approved_at ? date(vendor.approved_at) : null],
  ]

  function saveRate(e: FormEvent) {
    e.preventDefault()
    update.mutate({ id: vendor.id, commission_rate: rate })
  }

  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="font-heading text-2xl">{vendor.business_name}</SheetTitle>
          <SheetDescription asChild>
            <div className="flex items-center gap-2">
              <StatusBadge status={vendor.approval_status} />
              {vendor.approval_status === "approved" && (
                <Link to={`/stores/${vendor.store_slug}`} className="text-xs text-brand hover:underline">
                  View store →
                </Link>
              )}
            </div>
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-6 px-4 pb-6">
          <dl className="space-y-2 text-sm">
            {rows
              .filter(([, v]) => v)
              .map(([k, v]) => (
                <div key={k} className="grid grid-cols-[8rem_1fr] gap-2">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="break-words">{v}</dd>
                </div>
              ))}
          </dl>
          {vendor.rejection_reason && (
            <p className="rounded-lg bg-destructive/10 p-3 text-sm">
              <span className="font-medium">Reason given: </span>
              {vendor.rejection_reason}
            </p>
          )}

          <form onSubmit={saveRate} className="flex items-end gap-2">
            <div className="grid flex-1 gap-1.5">
              <Label htmlFor="commission">Commission rate (%)</Label>
              <Input id="commission" type="number" min="0" max="100" step="0.01" value={rate} onChange={(e) => setRate(e.target.value)} />
            </div>
            <Button type="submit" variant="outline" disabled={update.isPending || rate === vendor.commission_rate}>
              {update.isPending && <Spinner />} Save
            </Button>
          </form>
          <p className="-mt-4 text-xs text-muted-foreground">Applies to new orders; existing order lines keep the rate they were sold at.</p>

          <div className="flex flex-wrap gap-2 border-t pt-6">
            {vendor.approval_status !== "approved" && (
              <ConfirmAction
                trigger={
                  <Button>
                    <CheckIcon /> Approve
                  </Button>
                }
                title={`Approve ${vendor.business_name}?`}
                description="They can start listing and selling immediately and will be notified by email."
                confirmLabel="Approve"
                onConfirm={() => act.mutateAsync({ id: vendor.id, action: "approve" })}
              />
            )}
            {vendor.approval_status === "pending" && (
              <ConfirmAction
                trigger={
                  <Button variant="outline">
                    <XIcon /> Reject
                  </Button>
                }
                title="Reject application"
                description="The applicant sees this reason on their status page and in an email."
                inputLabel="Reason"
                inputRequired
                confirmLabel="Reject"
                destructive
                onConfirm={(reason) => act.mutateAsync({ id: vendor.id, action: "reject", reason })}
              />
            )}
            {vendor.approval_status === "approved" && (
              <ConfirmAction
                trigger={
                  <Button variant="outline" className="text-destructive hover:text-destructive">
                    <BanIcon /> Suspend
                  </Button>
                }
                title="Suspend this store?"
                description="Their products are hidden from the shop immediately. Existing orders are unaffected."
                inputLabel="Reason"
                inputRequired
                confirmLabel="Suspend"
                destructive
                onConfirm={(reason) => act.mutateAsync({ id: vendor.id, action: "suspend", reason })}
              />
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function StaffVendorsPage() {
  const [params, setParams] = useSearchParams()
  const status = params.get("status") ?? "all"
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(null)
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useStaffVendors({
    page,
    status: status === "all" ? undefined : status,
  })
  const current = data?.results.find((v) => v.id === selected)

  return (
    <div className="space-y-6">
      <Title>Vendors</Title>
      <PageHeader title="Vendors" description="Review applications, set commission and suspend stores." />
      <Tabs value={status} onValueChange={(v) => (setParams(v === "all" ? {} : { status: v }), setPage(1))}>
        <TabsList>
          {["all", "pending", "approved", "rejected", "suspended"].map((s) => (
            <TabsTrigger key={s} value={s} className="capitalize">
              {s}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={StoreIcon} title={status === "pending" ? "No pending applications" : "No vendors"} />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Store</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Commission</TableHead>
                  <TableHead>Applied</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((v) => (
                  <TableRow key={v.id} className="cursor-pointer" onClick={() => setSelected(v.id)}>
                    <TableCell>
                      <p className="font-medium">{v.business_name}</p>
                      <p className="text-xs text-muted-foreground">{v.email}</p>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{[v.business_city, v.business_country].filter(Boolean).join(", ")}</TableCell>
                    <TableCell>
                      <StatusBadge status={v.approval_status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{Number(v.commission_rate)}%</TableCell>
                    <TableCell className="text-muted-foreground">{date(v.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableShell>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
      {current && <Detail key={`${current.id}-${current.approval_status}-${current.commission_rate}`} vendor={current} onClose={() => setSelected(null)} />}
    </div>
  )
}

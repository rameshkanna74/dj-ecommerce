import { ChevronRightIcon, LifeBuoyIcon, PlusIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { toast } from "sonner"

import { ApiError } from "@/api/client"
import { Field, formValues, TextField } from "@/components/common/field"
import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader, Spinner, errorMessage } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { useCreateTicket, useTickets } from "@/features/account/orders-api"
import { dateTime, pluralize } from "@/lib/format"

function NewTicket({ order }: { order?: string }) {
  const [open, setOpen] = useState(Boolean(order))
  const create = useCreateTicket()
  const navigate = useNavigate()
  const fields = create.error instanceof ApiError ? create.error.fields : {}

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const v = formValues(e.currentTarget)
    create.mutate(
      { subject: v.subject, message: v.message, ...(v.order ? { order: v.order } : {}) },
      {
        onSuccess: (ticket) => {
          toast.success("Ticket created. We usually reply within a day.")
          navigate(`/account/support/${ticket.id}`)
        },
        onError: (err) => {
          if (!(err instanceof ApiError && Object.keys(err.fields).length)) toast.error(errorMessage(err))
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon /> New ticket
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>How can we help?</DialogTitle>
          <DialogDescription>Tell us what happened and we’ll get back to you by email.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Subject" name="subject" required maxLength={200} error={fields.subject} autoFocus />
          <Field label="Order number (optional)" name="order" defaultValue={order} error={fields.order} />
          <TextField label="Message" name="message" required rows={5} error={fields.message} />
          <Button type="submit" className="w-full" disabled={create.isPending}>
            {create.isPending && <Spinner />} Send
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function SupportPage() {
  const [params] = useSearchParams()
  const [page, setPage] = useState(1)
  const { data, isPending, isError, error, refetch } = useTickets(page)

  return (
    <div className="space-y-6">
      <Title>Support</Title>
      <PageHeader
        title="Support"
        description="Questions about an order, a refund or your account? We’re here."
        actions={<NewTicket order={params.get("order") ?? undefined} />}
      />
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={LifeBuoyIcon} title="No tickets" description="Your conversations with our team will appear here." />
      ) : (
        <>
          <ul className="divide-y rounded-2xl border">
            {data.results.map((t) => (
              <li key={t.id}>
                <Link to={`/account/support/${t.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 p-4 hover:bg-muted/40">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{t.subject}</p>
                    <p className="text-xs text-muted-foreground">
                      #{t.id} · Updated {dateTime(t.updated_at)} · {pluralize(t.reply_count, "reply", "replies")}
                    </p>
                  </div>
                  <StatusBadge status={t.status} label={t.status_display} />
                  <ChevronRightIcon className="size-4 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}

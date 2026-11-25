import { ArrowLeftIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useParams } from "react-router"
import { toast } from "sonner"

import { ErrorState, PageLoader, Spinner, errorMessage } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useCloseTicket, useReplyTicket, useTicket } from "@/features/account/orders-api"
import { dateTime } from "@/lib/format"
import { cn } from "@/lib/utils"

export default function TicketPage() {
  const id = Number(useParams().id)
  const { data: ticket, isPending, isError, error, refetch } = useTicket(id)
  const reply = useReplyTicket(id)
  const close = useCloseTicket(id)
  const [body, setBody] = useState("")

  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />
  const closed = ticket.status === "closed"

  function submit(e: FormEvent) {
    e.preventDefault()
    reply.mutate(body, { onSuccess: () => setBody(""), onError: (err) => toast.error(errorMessage(err)) })
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Title>{ticket.subject}</Title>
      <Link to="/account/support" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" /> All tickets
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-heading text-3xl">{ticket.subject}</h1>
          <p className="text-sm text-muted-foreground">
            #{ticket.id} · Opened {dateTime(ticket.created_at)}
            {ticket.order && <> · Order {ticket.order}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={ticket.status} label={ticket.status_display} />
          {!closed && (
            <Button variant="outline" size="sm" disabled={close.isPending} onClick={() => close.mutate()}>
              Close ticket
            </Button>
          )}
        </div>
      </div>

      <ol className="space-y-4">
        <li className="rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">You · {dateTime(ticket.created_at)}</p>
          <p className="mt-1 text-sm whitespace-pre-line">{ticket.message}</p>
        </li>
        {ticket.messages.map((m) =>
          m.body ? (
            <li
              key={m.id}
              className={cn("rounded-2xl p-4", m.is_staff_reply ? "ml-6 bg-brand-soft/60 dark:bg-brand-soft/30" : "mr-6 border bg-card")}
            >
              <p className="text-xs text-muted-foreground">
                {m.is_staff_reply ? "Support team" : "You"} · {dateTime(m.created_at)}
              </p>
              <p className="mt-1 text-sm whitespace-pre-line">{m.body}</p>
              {m.status_change_display && <p className="mt-2 text-xs text-muted-foreground">Status → {m.status_change_display}</p>}
            </li>
          ) : (
            <li key={m.id} className="text-center text-xs text-muted-foreground">
              Status changed to {m.status_change_display} · {dateTime(m.created_at)}
            </li>
          ),
        )}
      </ol>

      {closed ? (
        <p className="rounded-xl bg-muted p-4 text-center text-sm text-muted-foreground">
          This ticket is closed. <Link to="/account/support" className="underline">Open a new one</Link> if you need more help.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write a reply…" rows={4} aria-label="Reply" required />
          <Button type="submit" disabled={reply.isPending || !body.trim()}>
            {reply.isPending && <Spinner />} Send reply
          </Button>
        </form>
      )}
    </div>
  )
}

import { ArrowLeftIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link, useParams } from "react-router"

import type { Schemas } from "@/api/client"
import { ErrorState, PageLoader, Spinner } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useRespondTicket, useStaffTicket } from "@/features/staff/api"
import { dateTime } from "@/lib/format"
import { cn } from "@/lib/utils"

type TicketStatus = Schemas["TicketStatusEnum"]

export default function StaffTicketPage() {
  const id = Number(useParams().id)
  const { data: ticket, isPending, isError, error, refetch } = useStaffTicket(id)
  const respond = useRespondTicket(id)
  const [body, setBody] = useState("")
  const [status, setStatus] = useState<TicketStatus | "keep">("keep")

  if (isPending) return <PageLoader />
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />

  function submit(e: FormEvent) {
    e.preventDefault()
    respond.mutate(
      { body, status: status === "keep" ? "" : status },
      {
        onSuccess: () => {
          setBody("")
          setStatus("keep")
        },
      },
    )
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Title>{ticket.subject}</Title>
      <Link to="/staff/support" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" /> Support queue
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="font-heading text-3xl">{ticket.subject}</h1>
          <p className="text-sm text-muted-foreground">
            #{ticket.id} · {ticket.user.username} ({ticket.user.email}) · {ticket.user.role}
            {ticket.order && (
              <>
                {" · "}
                <Link to={`/staff/orders/${ticket.order}`} className="text-brand hover:underline">
                  Order {ticket.order}
                </Link>
              </>
            )}
          </p>
        </div>
        <StatusBadge status={ticket.status} label={ticket.status_display} />
      </div>

      <ol className="space-y-4">
        <li className="mr-6 rounded-2xl border bg-card p-4">
          <p className="text-xs text-muted-foreground">
            {ticket.user.username} · {dateTime(ticket.created_at)}
          </p>
          <p className="mt-1 text-sm whitespace-pre-line">{ticket.message}</p>
        </li>
        {ticket.messages.map((m) =>
          m.body ? (
            <li key={m.id} className={cn("rounded-2xl p-4", m.is_staff_reply ? "ml-6 bg-brand-soft/60 dark:bg-brand-soft/30" : "mr-6 border bg-card")}>
              <p className="text-xs text-muted-foreground">
                {m.author} · {dateTime(m.created_at)}
              </p>
              <p className="mt-1 text-sm whitespace-pre-line">{m.body}</p>
              {m.status_change_display && <p className="mt-2 text-xs text-muted-foreground">Status → {m.status_change_display}</p>}
            </li>
          ) : (
            <li key={m.id} className="text-center text-xs text-muted-foreground">
              {m.author} set status to {m.status_change_display} · {dateTime(m.created_at)}
            </li>
          ),
        )}
      </ol>

      <form onSubmit={submit} className="space-y-3 rounded-2xl border p-4">
        <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Reply to the customer (emailed to them)…" rows={4} aria-label="Reply" />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="ticket-status" className="text-sm font-normal text-muted-foreground">
              Status
            </Label>
            <Select value={status} onValueChange={(v) => setStatus(v as TicketStatus | "keep")}>
              <SelectTrigger id="ticket-status" className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="keep">Keep current</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="in_progress">In progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={respond.isPending || (!body.trim() && status === "keep")}>
            {respond.isPending && <Spinner />} Send
          </Button>
        </div>
      </form>
    </div>
  )
}

import { MessageCircleQuestionIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Link } from "react-router"

import { ApiError, type Schemas } from "@/api/client"
import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useAnswerQuestion, useVendorQuestions } from "@/features/vendor/api"
import { date } from "@/lib/format"

function QuestionCard({ q }: { q: Schemas["Question"] }) {
  const answer = useAnswerQuestion()
  const [text, setText] = useState(q.answer)
  const [editing, setEditing] = useState(!q.is_answered)
  const err = answer.error instanceof ApiError ? answer.error.fields.answer : undefined

  function submit(e: FormEvent) {
    e.preventDefault()
    answer.mutate({ id: q.id, answer: text }, { onSuccess: () => setEditing(false) })
  }

  return (
    <li className="space-y-3 rounded-2xl border p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link to={`/products/${q.product}`} className="text-xs text-muted-foreground hover:underline">
          {q.product}
        </Link>
        <StatusBadge tone={q.is_answered ? "success" : "warning"} label={q.is_answered ? "Answered" : "Needs answer"} />
      </div>
      <p className="font-medium">{q.question}</p>
      <p className="text-xs text-muted-foreground">
        {q.author} · {date(q.created_at)}
      </p>
      {editing ? (
        <form onSubmit={submit} className="space-y-2">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a public answer…" rows={3} aria-label="Answer" aria-invalid={Boolean(err)} />
          {err && <p className="text-xs text-destructive">{err}</p>}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={answer.isPending || !text.trim()}>
              {answer.isPending && <Spinner />} Publish answer
            </Button>
            {q.is_answered && (
              <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      ) : (
        <div className="flex items-start justify-between gap-3 rounded-xl bg-muted/50 p-3 text-sm">
          <p>{q.answer}</p>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
      )}
    </li>
  )
}

export default function VendorQuestionsPage() {
  const [page, setPage] = useState(1)
  const { data, isPending, isError, error, refetch } = useVendorQuestions(page)
  const questions = [...(data?.results ?? [])].sort((a, b) => Number(a.is_answered) - Number(b.is_answered))

  return (
    <div className="space-y-6">
      <Title>Questions</Title>
      <PageHeader title="Questions" description="Answers are public on the product page. Unanswered questions are listed first." />
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !questions.length ? (
        <EmptyState icon={MessageCircleQuestionIcon} title="No questions yet" />
      ) : (
        <>
          <ul className="space-y-4">
            {questions.map((q) => (
              <QuestionCard key={q.id} q={q} />
            ))}
          </ul>
          <Pager page={page} count={data!.count} onPage={setPage} />
        </>
      )}
    </div>
  )
}

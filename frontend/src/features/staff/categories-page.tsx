import { FolderTreeIcon, PencilIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { useState, type FormEvent } from "react"

import { ApiError } from "@/api/client"
import { Field, formValues, TextField } from "@/components/common/field"
import { Pager } from "@/components/common/pager"
import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDeleteCategory, useSaveCategory, useStaffCategories, type StaffCategory } from "@/features/staff/api"
import { ConfirmAction, TableShell } from "@/features/staff/shared"

function CategoryDialog({ category, onClose }: { category?: StaffCategory; onClose: () => void }) {
  const save = useSaveCategory()
  const [active, setActive] = useState(category?.is_active ?? true)
  const fields = save.error instanceof ApiError ? save.error.fields : {}

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const v = formValues(e.currentTarget)
    save.mutate({ id: category?.id, name: v.name, description: v.description, is_active: active }, { onSuccess: onClose })
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{category ? `Edit ${category.name}` : "New category"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Name" name="name" required maxLength={100} defaultValue={category?.name} error={fields.name} />
          <TextField label="Description" name="description" rows={3} defaultValue={category?.description} error={fields.description} />
          <div className="flex items-center justify-between rounded-lg border px-3 py-2">
            <Label htmlFor="cat-active" className="font-normal">
              Visible in the shop (hides all its products when off)
            </Label>
            <Switch id="cat-active" checked={active} onCheckedChange={setActive} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending && <Spinner />} Save
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function StaffCategoriesPage() {
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<StaffCategory | "new" | null>(null)
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useStaffCategories(page)
  const remove = useDeleteCategory()

  return (
    <div className="space-y-6">
      <Title>Categories</Title>
      <PageHeader
        title="Categories"
        description="The shop’s top-level navigation."
        actions={
          <Button onClick={() => setEditing("new")}>
            <PlusIcon /> New category
          </Button>
        }
      />
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.results.length ? (
        <EmptyState icon={FolderTreeIcon} title="No categories" />
      ) : (
        <>
          <TableShell dimmed={isPlaceholderData}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead className="text-right">Products</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <p className="font-medium">{c.name}</p>
                      {c.description && <p className="max-w-72 truncate text-xs text-muted-foreground">{c.description}</p>}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{c.slug}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.product_count}</TableCell>
                    <TableCell>
                      <StatusBadge tone={c.is_active === false ? "neutral" : "success"} label={c.is_active === false ? "Hidden" : "Visible"} />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" onClick={() => setEditing(c)} aria-label={`Edit ${c.name}`}>
                          <PencilIcon />
                        </Button>
                        <ConfirmAction
                          trigger={
                            <Button size="icon" variant="ghost" aria-label={`Delete ${c.name}`}>
                              <Trash2Icon />
                            </Button>
                          }
                          title={`Delete ${c.name}?`}
                          description={
                            c.product_count
                              ? `It still has ${c.product_count} products, so the server will refuse. Hide it instead, or move the products first.`
                              : "This can’t be undone."
                          }
                          confirmLabel="Delete"
                          destructive
                          onConfirm={() => remove.mutateAsync(c.id)}
                        />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableShell>
          <Pager page={page} count={data.count} onPage={setPage} />
        </>
      )}
      {editing && <CategoryDialog category={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

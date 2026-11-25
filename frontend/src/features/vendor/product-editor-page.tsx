import { ArrowLeftIcon, ExternalLinkIcon, ImagePlusIcon, PlusIcon, SaveIcon, Trash2Icon } from "lucide-react"
import { useRef, useState, type FormEvent } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { toast } from "sonner"

import { ApiError } from "@/api/client"
import { Field, FieldShell, formValues, TextField } from "@/components/common/field"
import { ErrorState, PageLoader, Spinner } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useCategories } from "@/features/catalog/api"
import {
  useDeleteImage,
  useDeleteProduct,
  useDeleteVariant,
  useSaveProduct,
  useSaveVariant,
  useUpdateImage,
  useUploadCover,
  useUploadImage,
  useVendorProduct,
  type Variant,
  type VendorProduct,
} from "@/features/vendor/api"

const ACCEPT = "image/jpeg,image/png,image/webp,image/gif"

function DetailsForm({ product }: { product?: VendorProduct }) {
  const navigate = useNavigate()
  const { data: categories } = useCategories()
  const save = useSaveProduct(product?.id ?? null)
  const [category, setCategory] = useState(product ? String(product.category) : "")
  const [active, setActive] = useState(product?.is_active ?? true)
  const fields = save.error instanceof ApiError ? save.error.fields : {}

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const v = formValues(e.currentTarget)
    save.mutate(
      {
        name: v.name,
        description: v.description,
        price: v.price,
        stock: Number(v.stock || 0),
        category: Number(category),
        is_active: active,
      },
      {
        onSuccess: (saved) => {
          toast.success(product ? "Product saved" : "Product created. Add photos and options below.")
          if (!product) navigate(`/vendor/products/${saved.id}`, { replace: true })
        },
      },
    )
  }

  return (
    <Card className="shadow-none">
      <CardHeader>
        <CardTitle>Details</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field className="sm:col-span-2" label="Name" name="name" required maxLength={200} defaultValue={product?.name} error={fields.name} />
          <FieldShell label="Category" error={fields.category}>
            {(id) => (
              <Select value={category} onValueChange={setCategory} required>
                <SelectTrigger id={id} className="w-full" aria-invalid={Boolean(fields.category)}>
                  <SelectValue placeholder="Choose a category" />
                </SelectTrigger>
                <SelectContent>
                  {categories?.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FieldShell>
          <Field label="Price" name="price" type="number" inputMode="decimal" min="0" step="0.01" required defaultValue={product?.price} error={fields.price} />
          <TextField className="sm:col-span-2" label="Description" name="description" rows={6} defaultValue={product?.description} error={fields.description} />
          <Field
            label="Stock"
            name="stock"
            type="number"
            min="0"
            defaultValue={product?.stock ?? 0}
            error={fields.stock}
            hint={product?.variants.length ? "Ignored: each option has its own stock." : "Units available to sell."}
          />
          <div className="flex items-center justify-between gap-3 self-end rounded-lg border px-3 py-2">
            <Label htmlFor="is_active" className="font-normal">
              Visible in the shop
            </Label>
            <Switch id="is_active" checked={active} onCheckedChange={setActive} />
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" disabled={save.isPending || !category}>
              {save.isPending ? <Spinner /> : <SaveIcon />} {product ? "Save changes" : "Create product"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function CoverImage({ product }: { product: VendorProduct }) {
  const upload = useUploadCover(product.id)
  const input = useRef<HTMLInputElement>(null)
  return (
    <Card className="shadow-none">
      <CardHeader>
        <CardTitle>Cover photo</CardTitle>
        <CardDescription>Shown in listings. JPG, PNG, WebP or GIF.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="aspect-[4/5] overflow-hidden rounded-xl bg-muted">
          <ProductImage src={product.cover_image} name={product.name} />
        </div>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) upload.mutate(file, { onSuccess: () => toast.success("Cover updated") })
            e.target.value = ""
          }}
        />
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="flex-1" onClick={() => input.current?.click()} disabled={upload.isPending}>
            {upload.isPending ? <Spinner /> : <ImagePlusIcon />} {product.cover_image ? "Replace" : "Upload"}
          </Button>
          {product.cover_image && (
            <Button variant="ghost" size="sm" onClick={() => upload.mutate(null)} disabled={upload.isPending} aria-label="Remove cover">
              <Trash2Icon />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function VariantRow({ productId, variant, onDone }: { productId: number; variant?: Variant; onDone?: () => void }) {
  const save = useSaveVariant(productId)
  const remove = useDeleteVariant(productId)
  const [active, setActive] = useState(variant?.is_active ?? true)
  const fields = save.error instanceof ApiError ? save.error.fields : {}

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const v = formValues(form)
    save.mutate(
      {
        id: variant?.id,
        attribute_name: v.attribute_name,
        attribute_value: v.attribute_value,
        price_override: v.price_override || null,
        stock: Number(v.stock || 0),
        is_active: active,
      },
      {
        onSuccess: () => {
          toast.success(variant ? "Option saved" : "Option added")
          if (!variant) {
            form.reset()
            onDone?.()
          }
        },
      },
    )
  }

  const error = fields.non_field_errors || fields.attribute_value || fields.attribute_name || fields.price_override || fields.stock
  return (
    <form onSubmit={submit} className="grid grid-cols-2 items-end gap-2 border-b py-3 last:border-0 sm:grid-cols-[1fr_1fr_7rem_5rem_auto_auto]">
      <Input name="attribute_name" defaultValue={variant?.attribute_name ?? "Size"} placeholder="Option (e.g. Size)" aria-label="Option name" required />
      <Input name="attribute_value" defaultValue={variant?.attribute_value} placeholder="Value (e.g. M)" aria-label="Option value" required />
      <Input name="price_override" type="number" step="0.01" min="0" defaultValue={variant?.price_override ?? ""} placeholder="Price" aria-label="Price override" />
      <Input name="stock" type="number" min="0" defaultValue={variant?.stock ?? 0} aria-label="Stock" />
      <Switch checked={active} onCheckedChange={setActive} aria-label="Option active" className="mb-2" />
      <div className="flex gap-1">
        <Button type="submit" size="sm" variant={variant ? "outline" : "default"} disabled={save.isPending}>
          {save.isPending ? <Spinner /> : variant ? "Save" : <><PlusIcon /> Add</>}
        </Button>
        {variant && (
          <Button type="button" size="sm" variant="ghost" onClick={() => remove.mutate(variant.id)} disabled={remove.isPending} aria-label="Delete option">
            <Trash2Icon />
          </Button>
        )}
      </div>
      {error && <p className="col-span-full text-xs text-destructive">{error}</p>}
    </form>
  )
}

function Variants({ product }: { product: VendorProduct }) {
  const [adding, setAdding] = useState(product.variants.length === 0)
  return (
    <Card className="shadow-none">
      <CardHeader>
        <CardTitle>Options</CardTitle>
        <CardDescription>Sizes, colours or materials, each with its own stock. Leave price empty to use the product price.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="hidden grid-cols-[1fr_1fr_7rem_5rem_auto_auto] gap-2 pb-1 text-xs text-muted-foreground sm:grid">
          <span>Option</span>
          <span>Value</span>
          <span>Price</span>
          <span>Stock</span>
          <span>On</span>
          <span />
        </div>
        {product.variants.map((v) => (
          <VariantRow key={`${v.id}-${v.stock}-${v.is_active}`} productId={product.id} variant={v} />
        ))}
        {adding ? (
          <VariantRow productId={product.id} onDone={() => setAdding(true)} />
        ) : (
          <Button variant="outline" size="sm" className="mt-3" onClick={() => setAdding(true)}>
            <PlusIcon /> Add option
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function Gallery({ product }: { product: VendorProduct }) {
  const upload = useUploadImage(product.id)
  const update = useUpdateImage(product.id)
  const remove = useDeleteImage(product.id)
  const input = useRef<HTMLInputElement>(null)
  return (
    <Card className="shadow-none">
      <CardHeader>
        <CardTitle>Gallery</CardTitle>
        <CardDescription>Extra photos on the product page. Describe each one for screen readers.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {product.images.map((img) => (
            <div key={img.id} className="space-y-2">
              <div className="group relative aspect-square overflow-hidden rounded-xl bg-muted">
                <ProductImage src={img.image} name={product.name} alt={img.alt_text} size="sm" />
                <button
                  type="button"
                  onClick={() => remove.mutate(img.id)}
                  className="absolute top-2 right-2 flex size-8 items-center justify-center rounded-full bg-background/90 opacity-0 shadow transition group-hover:opacity-100 focus:opacity-100"
                  aria-label="Delete image"
                >
                  <Trash2Icon className="size-4" />
                </button>
              </div>
              <Input
                defaultValue={img.alt_text}
                placeholder="Alt text"
                aria-label="Alt text"
                className="h-8 text-xs"
                onBlur={(e) => e.target.value !== img.alt_text && update.mutate({ id: img.id, alt_text: e.target.value })}
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={upload.isPending}
            className="flex aspect-square flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed text-sm text-muted-foreground transition hover:border-foreground/40 hover:text-foreground"
          >
            {upload.isPending ? <Spinner /> : <ImagePlusIcon className="size-5" />}
            Add photos
          </button>
        </div>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={async (e) => {
            const files = Array.from(e.target.files ?? [])
            e.target.value = ""
            for (const [i, file] of files.entries()) {
              await upload
                .mutateAsync({ file, alt_text: product.name, position: product.images.length + i })
                .catch(() => undefined)
            }
          }}
        />
      </CardContent>
    </Card>
  )
}

function DeleteProduct({ product }: { product: VendorProduct }) {
  const remove = useDeleteProduct()
  const navigate = useNavigate()
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="ghost" className="text-destructive hover:text-destructive">
          <Trash2Icon /> Delete
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete “{product.name}”?</AlertDialogTitle>
          <AlertDialogDescription>
            Products that have been ordered can’t be deleted; they’ll be hidden from the shop instead.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-white hover:bg-destructive/90"
            onClick={() => remove.mutate(product.id, { onSuccess: () => navigate("/vendor/products") })}
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default function ProductEditorPage() {
  const { id } = useParams()
  const productId = id ? Number(id) : null
  const { data: product, isPending, isError, error, refetch } = useVendorProduct(productId)

  if (productId && isPending) return <PageLoader />
  if (productId && isError) return <ErrorState error={error} onRetry={() => refetch()} />

  return (
    <div className="space-y-6">
      <Title>{product ? product.name : "New product"}</Title>
      <Link to="/vendor/products" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" /> Products
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="font-heading text-4xl">{product ? product.name : "New product"}</h1>
          {product && <StatusBadge tone={product.is_active ? "success" : "neutral"} label={product.is_active ? "Live" : "Hidden"} />}
        </div>
        {product && (
          <div className="flex gap-2">
            <Button variant="outline" asChild>
              <Link to={`/products/${product.slug}`} target="_blank">
                <ExternalLinkIcon /> View in shop
              </Link>
            </Button>
            <DeleteProduct product={product} />
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-6">
          <DetailsForm key={product?.updated_at ?? "new"} product={product} />
          {product && <Variants product={product} />}
          {product && <Gallery product={product} />}
        </div>
        {product && (
          <div>
            <CoverImage product={product} />
          </div>
        )}
      </div>
    </div>
  )
}

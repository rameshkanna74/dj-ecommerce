import { ArrowRightIcon, PackageCheckIcon, ShieldCheckIcon, StoreIcon, TruckIcon } from "lucide-react"
import { Link } from "react-router"

import { Title } from "@/components/layout/layouts"
import { ProductCard, ProductCardSkeleton, ProductGrid } from "@/components/product/product-card"
import { ProductImage } from "@/components/product/product-image"
import { Button } from "@/components/ui/button"
import { useCategories, useProducts, useStores } from "@/features/catalog/api"
import { SHOP_NAME } from "@/lib/site"

function Section({ title, link, children }: { title: string; link?: { to: string; label: string }; children: React.ReactNode }) {
  return (
    <section className="container-page mt-20 space-y-8">
      <div className="flex items-end justify-between gap-4">
        <h2 className="font-heading text-3xl md:text-4xl">{title}</h2>
        {link && (
          <Link to={link.to} className="group inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            {link.label}
            <ArrowRightIcon className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        )}
      </div>
      {children}
    </section>
  )
}

function ProductRow({ sort }: { sort: "newest" | "popular" | "rating" }) {
  const { data, isPending } = useProducts({ sort, page_size: 4 })
  return (
    <ProductGrid>
      {isPending
        ? Array.from({ length: 4 }, (_, i) => <ProductCardSkeleton key={i} />)
        : data?.results.map((p, i) => <ProductCard key={p.id} product={p} priority={i < 2} />)}
    </ProductGrid>
  )
}

function Hero() {
  const { data } = useProducts({ sort: "popular", page_size: 3 })
  const picks = data?.results ?? []
  return (
    <section className="container-page pt-8 md:pt-14">
      <div className="grid items-center gap-10 overflow-hidden rounded-3xl bg-brand-soft/60 px-6 py-12 md:grid-cols-2 md:px-12 md:py-16 dark:bg-brand-soft/30">
        <div className="space-y-6">
          <p className="text-xs font-medium tracking-[0.2em] text-brand uppercase">Independent makers · one cart</p>
          <h1 className="font-heading text-5xl leading-[0.95] md:text-7xl">
            Things made <em className="text-brand">well</em>, by people who care.
          </h1>
          <p className="max-w-md text-muted-foreground">
            Discover small-batch goods from studios and workshops on {SHOP_NAME}. Pay on delivery or by bank transfer.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button size="lg" asChild>
              <Link to="/products">
                Shop the collection <ArrowRightIcon />
              </Link>
            </Button>
            <Button size="lg" variant="outline" className="bg-background/60" asChild>
              <Link to="/stores">Meet the makers</Link>
            </Button>
          </div>
        </div>
        <div className="relative hidden h-[22rem] md:block" aria-hidden>
          {picks.slice(0, 3).map((p, i) => (
            <Link
              key={p.id}
              to={`/products/${p.slug}`}
              tabIndex={-1}
              className="absolute overflow-hidden rounded-2xl shadow-xl ring-1 ring-black/5 transition-transform duration-500 hover:-translate-y-1"
              style={
                [
                  { left: "8%", top: "6%", width: "46%", height: "72%", rotate: "-4deg" },
                  { right: "6%", top: "0%", width: "40%", height: "56%", rotate: "5deg" },
                  { right: "16%", bottom: "0%", width: "38%", height: "44%", rotate: "-2deg" },
                ][i]
              }
            >
              <ProductImage src={p.cover_image} name={p.name} />
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}

const PROMISES = [
  { icon: StoreIcon, title: "Real makers", text: "Every store is reviewed before it can sell." },
  { icon: TruckIcon, title: "Tracked shipping", text: "Each item ships with a tracking number." },
  { icon: PackageCheckIcon, title: "Pay on delivery", text: "Cash on delivery or bank transfer." },
  { icon: ShieldCheckIcon, title: "Easy cancellations", text: "Change your mind before it ships." },
]

export default function HomePage() {
  const { data: categories } = useCategories()
  const { data: stores } = useStores()

  return (
    <>
      <Title />
      <Hero />

      <section className="container-page mt-10 grid grid-cols-2 gap-6 border-y py-8 md:grid-cols-4">
        {PROMISES.map(({ icon: Icon, title, text }) => (
          <div key={title} className="flex gap-3">
            <Icon className="mt-0.5 size-5 shrink-0 text-brand" />
            <div>
              <p className="text-sm font-medium">{title}</p>
              <p className="text-xs text-muted-foreground">{text}</p>
            </div>
          </div>
        ))}
      </section>

      {categories && categories.length > 0 && (
        <Section title="Shop by category">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            {categories.map((c) => (
              <Link
                key={c.id}
                to={`/products?category=${c.slug}`}
                className="group relative aspect-[3/2] overflow-hidden rounded-2xl"
              >
                <ProductImage name={c.name} className="transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-black/0" />
                <div className="absolute inset-x-4 bottom-3 text-white">
                  <p className="font-heading text-2xl">{c.name}</p>
                  <p className="text-xs opacity-80">{c.product_count} products</p>
                </div>
              </Link>
            ))}
          </div>
        </Section>
      )}

      <Section title="Most loved" link={{ to: "/products?sort=popular", label: "See all" }}>
        <ProductRow sort="popular" />
      </Section>

      <Section title="Just arrived" link={{ to: "/products?sort=newest", label: "See all" }}>
        <ProductRow sort="newest" />
      </Section>

      {stores && stores.results.length > 0 && (
        <Section title="Meet the makers" link={{ to: "/stores", label: "All stores" }}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {stores.results.slice(0, 3).map((s) => (
              <Link
                key={s.id}
                to={`/stores/${s.store_slug}`}
                className="group flex items-center gap-4 rounded-2xl border p-4 transition-colors hover:bg-muted/50"
              >
                <div className="size-16 shrink-0 overflow-hidden rounded-xl">
                  <ProductImage src={s.business_logo} name={s.business_name} size="sm" />
                </div>
                <div className="min-w-0">
                  <p className="truncate font-medium">{s.business_name}</p>
                  <p className="line-clamp-2 text-xs text-muted-foreground">
                    {s.business_description || [s.business_city, s.business_country].filter(Boolean).join(", ")}
                  </p>
                </div>
                <ArrowRightIcon className="ml-auto size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </Link>
            ))}
          </div>
        </Section>
      )}
    </>
  )
}

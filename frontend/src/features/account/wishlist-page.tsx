import { HeartIcon, ShoppingBagIcon } from "lucide-react"
import { Link } from "react-router"

import { PageHeader } from "@/components/common/page-header"
import { EmptyState, ErrorState, PageLoader, errorMessage } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { ProductCard, ProductGrid } from "@/components/product/product-card"
import { Button } from "@/components/ui/button"
import { useMoveWishlistToCart, useWishlist } from "@/features/account/wishlist-api"
import { pluralize } from "@/lib/format"
import { toast } from "sonner"

export default function WishlistPage() {
  const { data, isPending, isError, error, refetch } = useWishlist()
  const move = useMoveWishlistToCart()

  return (
    <div className="space-y-6">
      <Title>Wishlist</Title>
      <PageHeader title="Wishlist" description={data?.length ? pluralize(data.length, "saved item") : undefined} />
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data.length ? (
        <EmptyState
          icon={HeartIcon}
          title="Nothing saved yet"
          description="Tap the heart on any product to keep it here for later."
          action={
            <Button asChild>
              <Link to="/products">Browse products</Link>
            </Button>
          }
        />
      ) : (
        <ProductGrid className="lg:grid-cols-3">
          {data.map((product) => (
            <div key={product.id} className="space-y-3">
              <ProductCard product={product} />
              {product.is_in_stock && !product.has_variants ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  disabled={move.isPending}
                  onClick={() => move.mutate(product.id, { onError: (e) => toast.error(errorMessage(e)) })}
                >
                  <ShoppingBagIcon /> Move to cart
                </Button>
              ) : product.has_variants ? (
                <Button variant="outline" size="sm" className="w-full" asChild>
                  <Link to={`/products/${product.slug}`}>Choose options</Link>
                </Button>
              ) : null}
            </div>
          ))}
        </ProductGrid>
      )}
    </div>
  )
}

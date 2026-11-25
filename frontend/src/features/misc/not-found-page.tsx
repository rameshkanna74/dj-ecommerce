import { Link } from "react-router"

import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"

export default function NotFoundPage() {
  return (
    <div className="container-page flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <Title>Page not found</Title>
      <p className="font-heading text-8xl text-brand">404</p>
      <h1 className="text-xl font-medium">We couldn’t find that page</h1>
      <p className="max-w-sm text-sm text-muted-foreground">The link may be broken or the page may have moved.</p>
      <Button asChild>
        <Link to="/products">Browse the shop</Link>
      </Button>
    </div>
  )
}

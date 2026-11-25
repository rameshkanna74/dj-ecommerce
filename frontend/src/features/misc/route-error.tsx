import { isRouteErrorResponse, Link, useRouteError } from "react-router"

import { Button } from "@/components/ui/button"

/** Last-resort boundary (e.g. a lazy chunk failed to load after a deploy). */
export function RouteError() {
  const error = useRouteError()
  const status = isRouteErrorResponse(error) ? error.status : null
  const chunkFailed = error instanceof TypeError && /dynamically imported module|Failed to fetch/i.test(error.message)

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="font-heading text-6xl text-brand">{status ?? "Oops"}</p>
      <h1 className="text-xl font-medium">
        {status === 404 ? "This page does not exist" : chunkFailed ? "A new version is available" : "Something broke"}
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        {chunkFailed
          ? "The shop was updated while you were browsing. Reload to get the latest version."
          : "Sorry about that. Try reloading the page, or head back to the shop."}
      </p>
      <div className="flex gap-2">
        <Button onClick={() => window.location.reload()}>Reload</Button>
        <Button variant="outline" asChild>
          <Link to="/">Back to shop</Link>
        </Button>
      </div>
    </div>
  )
}

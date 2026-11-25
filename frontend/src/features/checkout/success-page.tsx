import { CircleCheckIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { ErrorState, PageLoader } from "@/components/common/states"
import { Title } from "@/components/layout/layouts"
import { Button } from "@/components/ui/button"
import { useOrder } from "@/features/account/orders-api"
import { money } from "@/lib/format"

export default function CheckoutSuccessPage() {
  const { orderNumber = "" } = useParams()
  const { data: order, isPending, isError, error } = useOrder(orderNumber)

  if (isPending) return <PageLoader />
  if (isError)
    return (
      <div className="container-page py-16">
        <ErrorState error={error} />
      </div>
    )

  return (
    <div className="container-page max-w-2xl py-16 text-center">
      <Title>Order placed</Title>
      <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-full bg-success-soft">
        <CircleCheckIcon className="size-8 text-success" />
      </div>
      <p className="text-sm text-muted-foreground">Order {order.order_number}</p>
      <h1 className="font-heading mt-2 text-5xl">Thank you!</h1>
      <p className="mt-4 text-muted-foreground">
        Your order of <span className="font-medium text-foreground">{money(order.total_amount)}</span> is confirmed.
        We’ve emailed you a receipt, and each maker will ship their items with tracking.
      </p>
      {order.payment_instructions && (
        <div className="mx-auto mt-8 max-w-md rounded-2xl border bg-muted/40 p-5 text-left text-sm">
          <p className="mb-1 font-medium">{order.payment_method_display}</p>
          <p className="text-muted-foreground">{order.payment_instructions}</p>
        </div>
      )}
      <div className="mt-10 flex flex-wrap justify-center gap-3">
        <Button asChild>
          <Link to={`/account/orders/${order.order_number}`}>View order</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/products">Continue shopping</Link>
        </Button>
      </div>
    </div>
  )
}

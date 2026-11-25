import { ClockIcon, LayoutDashboardIcon, MessageCircleQuestionIcon, PackageIcon, ShieldAlertIcon, ShoppingCartIcon, StarIcon } from "lucide-react"
import { Link } from "react-router"

import { PageLoader } from "@/components/common/states"
import { StatusBadge } from "@/components/common/status-badge"
import { PortalLayout, Title, type NavItem } from "@/components/layout/layouts"
import { Logo } from "@/components/layout/site-header"
import { Button } from "@/components/ui/button"
import { useApplication } from "@/features/vendor/api"
import { date } from "@/lib/format"
import { useAuth } from "@/providers/auth"

const NAV: NavItem[] = [
  { to: "/vendor", label: "Dashboard", icon: LayoutDashboardIcon, end: true },
  { to: "/vendor/products", label: "Products", icon: PackageIcon },
  { to: "/vendor/orders", label: "Orders", icon: ShoppingCartIcon },
  { to: "/vendor/reviews", label: "Reviews", icon: StarIcon },
  { to: "/vendor/questions", label: "Questions", icon: MessageCircleQuestionIcon },
]

/** Pending, rejected or suspended vendors see their application status instead of the portal. */
function ApplicationStatus() {
  const { logout } = useAuth()
  const { data: app, isPending } = useApplication()
  if (isPending || !app) return <PageLoader />
  const pending = app.approval_status === "pending"
  const Icon = pending ? ClockIcon : ShieldAlertIcon
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-8 p-6">
      <Title>Vendor application</Title>
      <Logo />
      <div className="w-full max-w-lg space-y-5 rounded-3xl border bg-card p-8 text-center">
        <div className={`mx-auto flex size-14 items-center justify-center rounded-full ${pending ? "bg-warning-soft text-warning" : "bg-destructive/10 text-destructive"}`}>
          <Icon className="size-6" />
        </div>
        <div className="space-y-2">
          <h1 className="font-heading text-3xl">
            {pending ? "Your application is under review" : app.approval_status === "rejected" ? "Application not approved" : "Your store is suspended"}
          </h1>
          <StatusBadge status={app.approval_status} label={app.approval_status_display} />
        </div>
        <p className="text-sm text-muted-foreground">
          {pending
            ? `Thanks for applying with ${app.business_name} on ${date(app.created_at)}. We review applications within two working days and will email you as soon as you can start selling.`
            : "Your store can’t sell right now. Contact support if you’d like to discuss this decision."}
        </p>
        {app.rejection_reason && (
          <p className="rounded-xl bg-muted p-4 text-left text-sm">
            <span className="font-medium">Reason: </span>
            {app.rejection_reason}
          </p>
        )}
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="outline" asChild>
            <Link to="/account/support">Contact support</Link>
          </Button>
          <Button variant="ghost" onClick={() => logout()}>
            Sign out
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function VendorLayout() {
  const { user } = useAuth()
  if (user?.vendor?.approval_status !== "approved") return <ApplicationStatus />
  return (
    <PortalLayout
      title="Vendor"
      items={NAV}
      footer={
        <div className="space-y-1 rounded-xl border bg-background p-3 text-xs">
          <p className="truncate font-medium">{user.vendor.business_name}</p>
          <p className="text-muted-foreground">Commission {Number(user.vendor.commission_rate)}%</p>
          <Link to={`/stores/${user.vendor.store_slug}`} className="text-brand hover:underline">
            View storefront →
          </Link>
        </div>
      }
    />
  )
}

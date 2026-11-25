import { HeartIcon, KeyRoundIcon, LifeBuoyIcon, PackageIcon, UserIcon } from "lucide-react"

import { PortalLayout, type NavItem } from "@/components/layout/layouts"
import { useAuth } from "@/providers/auth"

export default function AccountLayout() {
  const { user } = useAuth()
  const items: NavItem[] = [
    { to: "/account", label: "Profile", icon: UserIcon, end: true },
    ...(user?.role === "customer"
      ? [
          { to: "/account/orders", label: "Orders", icon: PackageIcon },
          { to: "/account/wishlist", label: "Wishlist", icon: HeartIcon },
        ]
      : []),
    { to: "/account/support", label: "Support", icon: LifeBuoyIcon },
    { to: "/account/security", label: "Password", icon: KeyRoundIcon },
  ]
  return <PortalLayout title="My account" items={items} withSiteHeader />
}

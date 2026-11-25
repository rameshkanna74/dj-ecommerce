import { MenuIcon, type LucideIcon } from "lucide-react"
import { useState, type ReactNode } from "react"
import { Link, NavLink, Outlet, ScrollRestoration } from "react-router"

import { Logo, SiteHeader, ThemeToggle } from "@/components/layout/site-header"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { pageTitle, SHOP_NAME } from "@/lib/site"
import { cn } from "@/lib/utils"

/** React 19 hoists <title> into <head>; this keeps titles consistent. */
export function Title({ children }: { children?: string }) {
  return <title>{pageTitle(children)}</title>
}

const YEAR = new Date().getFullYear()

function SiteFooter() {
  return (
    <footer className="mt-24 border-t bg-muted/40">
      <div className="container-page grid gap-10 py-12 md:grid-cols-4">
        <div className="space-y-3 md:col-span-2">
          <Logo />
          <p className="max-w-sm text-sm text-muted-foreground">
            A marketplace for independent makers. Every order supports a small business directly.
          </p>
        </div>
        <div className="space-y-2 text-sm">
          <p className="font-medium">Shop</p>
          <ul className="space-y-1.5 text-muted-foreground">
            <li><Link to="/products" className="hover:text-foreground">All products</Link></li>
            <li><Link to="/stores" className="hover:text-foreground">Stores</Link></li>
            <li><Link to="/products?sort=popular" className="hover:text-foreground">Best sellers</Link></li>
          </ul>
        </div>
        <div className="space-y-2 text-sm">
          <p className="font-medium">Help</p>
          <ul className="space-y-1.5 text-muted-foreground">
            <li><Link to="/account/orders" className="hover:text-foreground">Track an order</Link></li>
            <li><Link to="/account/support" className="hover:text-foreground">Contact support</Link></li>
            <li><Link to="/register?type=vendor" className="hover:text-foreground">Sell on {SHOP_NAME}</Link></li>
          </ul>
        </div>
      </div>
      <div className="container-page border-t py-6 text-xs text-muted-foreground">
        © {YEAR} {SHOP_NAME}. All prices include applicable taxes.
      </div>
    </footer>
  )
}

export function StoreLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50">
        Skip to content
      </a>
      <SiteHeader />
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <SiteFooter />
      <ScrollRestoration />
    </div>
  )
}

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

function SideNav({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5" onClick={onNavigate}>
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              isActive
                ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

/**
 * Sidebar layout for the account area and the vendor/staff portals.
 * ``withSiteHeader`` keeps the shop header (customer account); portals get a compact top bar.
 */
export function PortalLayout({
  title,
  items,
  withSiteHeader = false,
  footer,
}: {
  title: string
  items: NavItem[]
  withSiteHeader?: boolean
  footer?: ReactNode
}) {
  const [open, setOpen] = useState(false)

  const sidebar = (
    <div className="flex h-full flex-col gap-6">
      <p className="px-3 text-xs font-medium tracking-wider text-muted-foreground uppercase">{title}</p>
      <SideNav items={items} onNavigate={() => setOpen(false)} />
      {footer && <div className="mt-auto">{footer}</div>}
    </div>
  )

  return (
    <div className="flex min-h-svh flex-col">
      {withSiteHeader ? (
        <SiteHeader />
      ) : (
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-lg">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                <MenuIcon />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 bg-sidebar p-4">
              <SheetHeader className="p-0 pb-4">
                <SheetTitle asChild>
                  <div>
                    <Logo />
                  </div>
                </SheetTitle>
              </SheetHeader>
              {sidebar}
            </SheetContent>
          </Sheet>
          <Logo />
          <span className="hidden text-sm text-muted-foreground sm:inline">/ {title}</span>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/">View shop</Link>
            </Button>
            <ThemeToggle />
          </div>
        </header>
      )}
      <div className={cn("flex flex-1", withSiteHeader && "container-page gap-10 py-8")}>
        <aside className={cn("hidden w-60 shrink-0 lg:block", !withSiteHeader && "border-r bg-sidebar")}>
          <div className={cn("sticky", withSiteHeader ? "top-24" : "top-14 h-[calc(100svh-3.5rem)] p-4")}>{sidebar}</div>
        </aside>
        <main id="main" className={cn("min-w-0 flex-1", !withSiteHeader && "p-4 sm:p-6 lg:p-8")}>
          {withSiteHeader && (
            <div className="mb-6 lg:hidden">
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant="outline" size="sm">
                    <MenuIcon /> {title}
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="w-72 p-4">
                  <SheetHeader className="p-0 pb-4">
                    <SheetTitle>{title}</SheetTitle>
                  </SheetHeader>
                  {sidebar}
                </SheetContent>
              </Sheet>
            </div>
          )}
          <Outlet />
        </main>
      </div>
      <ScrollRestoration />
    </div>
  )
}

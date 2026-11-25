import {
  HeartIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MenuIcon,
  MoonIcon,
  PackageIcon,
  SearchIcon,
  ShieldCheckIcon,
  ShoppingBagIcon,
  StoreIcon,
  SunIcon,
  UserIcon,
} from "lucide-react"
import { useTheme } from "@/providers/theme"
import { useState, type FormEvent } from "react"
import { Link, NavLink, useNavigate, useSearchParams } from "react-router"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { useCart } from "@/features/cart/api"
import { useCategories } from "@/features/catalog/api"
import { initials } from "@/lib/format"
import { SHOP_NAME } from "@/lib/site"
import { cn } from "@/lib/utils"
import { useAuth } from "@/providers/auth"

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn("flex items-center gap-2", className)} aria-label={`${SHOP_NAME} home`}>
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <span className="font-heading text-xl leading-none">c</span>
      </span>
      <span className="font-heading text-2xl leading-none">{SHOP_NAME}</span>
    </Link>
  )
}

function SearchBox({ className, onDone }: { className?: string; onDone?: () => void }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [q, setQ] = useState(params.get("q") ?? "")

  function submit(e: FormEvent) {
    e.preventDefault()
    navigate(q.trim() ? `/products?q=${encodeURIComponent(q.trim())}` : "/products")
    onDone?.()
  }

  return (
    <form onSubmit={submit} role="search" className={cn("relative", className)}>
      <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search products"
        aria-label="Search products"
        className="h-10 rounded-full bg-muted/60 pl-9 shadow-none focus-visible:bg-background"
      />
    </form>
  )
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === "dark"
  return (
    <Button variant="ghost" size="icon" aria-label="Toggle dark mode" onClick={() => setTheme(dark ? "light" : "dark")}>
      {dark ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}

function CartButton() {
  const { data } = useCart()
  const count = data?.total_quantity ?? 0
  return (
    <Button variant="ghost" size="icon" className="relative" asChild>
      <Link to="/cart" aria-label={`Cart, ${count} items`}>
        <ShoppingBagIcon />
        {count > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex min-w-4.5 items-center justify-center rounded-full bg-brand px-1 text-[10px] leading-4.5 font-semibold text-brand-foreground tabular-nums">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </Link>
    </Button>
  )
}

function AccountMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  if (!user) {
    return (
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
          <Link to="/login">Sign in</Link>
        </Button>
        <Button size="sm" asChild>
          <Link to="/register">Join</Link>
        </Button>
      </div>
    )
  }
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="rounded-full focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          aria-label="Account menu"
        >
          <Avatar className="size-8">
            {user.avatar && <AvatarImage src={user.avatar} alt="" />}
            <AvatarFallback className="bg-brand-soft text-xs text-brand">{initials(name)}</AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <p className="truncate text-sm font-medium">{name}</p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {user.role === "customer" && (
          <>
            <DropdownMenuItem asChild>
              <Link to="/account/orders">
                <PackageIcon /> Orders
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link to="/account/wishlist">
                <HeartIcon /> Wishlist
              </Link>
            </DropdownMenuItem>
          </>
        )}
        {user.role === "vendor" && (
          <DropdownMenuItem asChild>
            <Link to="/vendor">
              <StoreIcon /> Vendor dashboard
            </Link>
          </DropdownMenuItem>
        )}
        {user.is_platform_admin && (
          <DropdownMenuItem asChild>
            <Link to="/staff">
              <ShieldCheckIcon /> Admin console
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem asChild>
          <Link to="/account">
            <UserIcon /> Account settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            await logout()
            navigate("/")
          }}
        >
          <LogOutIcon /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn("text-sm transition-colors hover:text-foreground", isActive ? "text-foreground font-medium" : "text-muted-foreground")

export function SiteHeader() {
  const { user } = useAuth()
  const { data: categories } = useCategories()
  const [open, setOpen] = useState(false)

  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur-lg supports-[backdrop-filter]:bg-background/70">
      <div className="container-page flex h-16 items-center gap-4">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
              <MenuIcon />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80">
            <SheetHeader>
              <SheetTitle asChild>
                <div>
                  <Logo />
                </div>
              </SheetTitle>
            </SheetHeader>
            <div className="flex flex-col gap-6 px-4">
              <SearchBox onDone={() => setOpen(false)} />
              <nav className="flex flex-col gap-3" onClick={() => setOpen(false)}>
                <NavLink to="/products" className={navClass} end>
                  Shop all
                </NavLink>
                {categories?.map((c) => (
                  <Link key={c.id} to={`/products?category=${c.slug}`} className="text-sm text-muted-foreground">
                    {c.name}
                  </Link>
                ))}
                <NavLink to="/stores" className={navClass}>
                  Stores
                </NavLink>
                {user?.role === "vendor" && (
                  <NavLink to="/vendor" className={navClass}>
                    Vendor dashboard
                  </NavLink>
                )}
                {user?.is_platform_admin && (
                  <NavLink to="/staff" className={navClass}>
                    Admin console
                  </NavLink>
                )}
              </nav>
            </div>
          </SheetContent>
        </Sheet>

        <Logo />

        <nav className="ml-6 hidden items-center gap-6 md:flex">
          <NavLink to="/products" className={navClass} end>
            Shop
          </NavLink>
          <NavLink to="/stores" className={navClass}>
            Stores
          </NavLink>
          {user?.role === "vendor" && (
            <NavLink to="/vendor" className={navClass}>
              <span className="inline-flex items-center gap-1.5">
                <LayoutDashboardIcon className="size-3.5" /> Sell
              </span>
            </NavLink>
          )}
          {user?.is_platform_admin && (
            <NavLink to="/staff" className={navClass}>
              Admin
            </NavLink>
          )}
        </nav>

        <SearchBox className="ml-auto hidden w-full max-w-xs lg:block" />

        <div className="ml-auto flex items-center gap-1 lg:ml-2">
          <ThemeToggle />
          {(!user || user.role === "customer") && <CartButton />}
          <AccountMenu />
        </div>
      </div>
    </header>
  )
}

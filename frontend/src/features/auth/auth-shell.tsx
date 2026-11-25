import type { ReactNode } from "react"

import { Title } from "@/components/layout/layouts"
import { ProductImage } from "@/components/product/product-image"

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
  wide = false,
}: {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  return (
    <div className="container-page py-10 md:py-16">
      <Title>{title}</Title>
      <div className="mx-auto grid max-w-5xl overflow-hidden rounded-3xl border bg-card md:grid-cols-[1fr_1.1fr]">
        <div className="relative hidden md:block">
          <ProductImage name="Made by hand" alt="" size="lg" />
          <div className="absolute inset-x-8 bottom-8 space-y-2 text-white drop-shadow">
            <p className="font-heading text-3xl leading-tight">“Every order is a note of thanks to a small studio.”</p>
            <p className="text-sm opacity-80">— The makers</p>
          </div>
          <div className="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent" />
        </div>
        <div className={wide ? "p-6 sm:p-10" : "p-6 sm:p-12"}>
          <div className="mb-8 space-y-2">
            <h1 className="font-heading text-4xl">{title}</h1>
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          {children}
          {footer && <div className="mt-8 text-center text-sm text-muted-foreground">{footer}</div>}
        </div>
      </div>
    </div>
  )
}

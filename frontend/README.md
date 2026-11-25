# CoreCart frontend

React SPA for the CoreCart marketplace API (`/api/v1/`). Storefront, checkout, customer account,
vendor portal and admin console in one lightweight app.

**Stack:** React 19 · Vite 8 · TypeScript 7 · Tailwind CSS v4 · shadcn/ui (radix-nova) · React Router 8 ·
TanStack Query 5 · openapi-fetch (types generated from the Django OpenAPI schema) · Bun.

## Run it

```bash
# terminal 1 — API (repo root)
uv run python manage.py runserver          # http://127.0.0.1:8000

# terminal 2 — frontend
cd frontend
bun install
bun run dev                                # http://localhost:5173
```

The Vite dev server proxies `/api` and `/media` to Django, so the browser sees a single origin: the
httpOnly refresh cookie and CSRF work with no CORS setup. Point it elsewhere with
`VITE_BACKEND_URL=http://host:port bun run dev`.

Set `CORECART_FRONTEND_URL=http://localhost:5173` in the backend `.env` so password-reset emails link to
`/reset-password` here. Demo data: `uv run python manage.py seed_demo` (coupon `WELCOME10`).

| Script | What it does |
|---|---|
| `bun run dev` | Dev server with HMR |
| `bun run build` | Type-check (`tsc -b`) + production build to `dist/` |
| `bun run preview` | Serve the production build |
| `bun run typecheck` / `bun run lint` | `tsc -b` / oxlint |
| `bun run gen:api` | Regenerate `src/api/schema.d.ts` from Django (`manage.py spectacular`). Run after any API change |

`gen:api` uses an isolated toolchain in `tools/openapi/` because openapi-typescript needs the TypeScript 5
JS API (the app itself compiles with TypeScript 7).

Optional env (`.env.local`): `VITE_CURRENCY` (ISO code, default `USD`), `VITE_SHOP_NAME` (default `CoreCart`).

## Structure

```
src/
  api/            client.ts (typed openapi-fetch client, auth/refresh, ApiError) · schema.d.ts (generated)
  providers/      auth.tsx (session, login/logout, useAuth) · theme.tsx (light/dark/system)
  components/
    ui/           shadcn/ui primitives (add more with `bunx --bun shadcn@latest add <name>`)
    common/       field, states (loading/empty/error), page-header, pager, status-badge, charts, guards
    layout/       site header, StoreLayout (shop), PortalLayout (account/vendor/admin sidebar)
    product/      product card, image (with monogram placeholder), ratings
  features/       one folder per area; each has api.ts (TanStack Query hooks) + *-page.tsx
    catalog/      home, product list/filters, product detail, stores
    cart/ checkout/
    auth/         login, register (customer/vendor), forgot/reset password
    account/      profile, password, orders, wishlist, support tickets
    vendor/       dashboard, products + editor (options, gallery), fulfilment, reviews, questions
    staff/        dashboard, orders, vendors, products, reviews, users, coupons, categories, support
  lib/            format (money/dates), lazy-page, site
  routes.tsx      route tree; every page is a lazy chunk
```

## How it works

- **Auth.** The access token lives only in memory. Login and registration send `use_cookie: true`, so the
  refresh token is an httpOnly cookie that JS can't read. On load the app silently refreshes when a
  `cc-session` hint is present. Any 401 triggers one shared refresh, then the request is retried once.
  Changing the password returns a fresh token pair, and the server revokes every older token.
- **Types end to end.** Paths, params and payloads are checked against the generated schema, so a backend
  change that breaks the frontend fails `bun run build`.
- **Errors.** DRF field errors (`{field: [msg]}`) render inline under inputs, and domain errors
  (`{detail, code}`) show as toasts. 409 checkout conflicts refresh the cart and rotate the idempotency key.
- **Checkout** sends a per-attempt `Idempotency-Key`, so double clicks and retries return the same order.
- **Roles.** Route guards mirror the API: `/cart` and `/checkout` are customer-only, `/vendor` is
  vendor-only (pending, rejected or suspended vendors see their application status), and `/staff` is for
  platform admins. The API enforces every rule anyway.
- **Light.** Pages load on demand (2–13 KB each). Charts are dependency-free SVG. Initial JS is about
  180 KB gzipped, mostly React itself.

## Production

`bun run build` writes static files to `dist/`. Serve them from any static host or CDN with an SPA
fallback to `index.html`. Either reverse-proxy `/api` and `/media` to Django on the same domain
(recommended: cookies stay first-party), or host the API separately, set `CORS_ALLOWED_ORIGINS` and
`JWT_REFRESH_COOKIE_DOMAIN`, and see the root README's "Connecting a browser frontend".

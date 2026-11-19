# CoreCart 1.0

CoreCart is a server-rendered, multi-vendor e-commerce marketplace built with Django.
Customers browse and buy, approved vendors sell and fulfil, and administrators run the platform.

## Features

**Customers**: registration, login with username or email, password reset and change, profile with default
delivery address, product search, filtering, sorting and pagination, product variants, wishlist, a database-backed
cart with save-for-later, coupons, checkout with cash on delivery or bank transfer, order tracking with a timeline,
cancellation of unprocessed orders, printable invoices, reviews (one per product, verified-purchase badge),
product questions, back-in-stock email alerts, recently viewed products and support tickets.

**Vendors**: application with an approval workflow (pending → approved / rejected, plus suspension), a dashboard with
KPIs and sales charts, product management with variants and image galleries, inventory, per-item fulfilment
(processing → shipped with tracking → delivered), reviews and questions inbox, store settings, a public storefront
and CSV sales export.

**Administrators**: a marketplace dashboard (customers, vendors, pending approvals, products, orders, recognised
revenue, top sellers, sales trend, category performance, low stock), a support queue, CSV exports, and the Django
admin for users, vendor approval, products, categories, orders (record payment, refund, cancel), coupons, review and
question moderation and stock alerts.

## REST API (v1)

Every feature above is also available as a JSON API at **`/api/v1/`**, built with Django REST Framework on the
same service layer as the web pages, so business rules are never duplicated.

- **Docs**: interactive Swagger UI at `/api/v1/docs/`, ReDoc at `/api/v1/redoc/`, OpenAPI 3 schema at
  `/api/v1/schema/` (use it to generate a typed frontend client).
- **Auth**: JWT. `POST /api/v1/auth/token/` with `{"username": "<username or email>", "password": "..."}` returns
  `access`, `refresh` and the user. Send `Authorization: Bearer <access>`. Refresh at `/auth/token/refresh/`
  (refresh tokens rotate, and old ones are blacklisted). Log out with `POST /auth/logout/ {"refresh": "..."}`.
  Session cookies also work (CSRF enforced).
- **Errors**: validation errors are field-keyed, e.g. `{"email": ["..."]}`. Business-rule errors are
  `{"detail": "...", "code": "..."}` with 400 (`cart_error`, `coupon_error`, `ticket_error`) or 409
  (`checkout_conflict`, `invalid_transition`, `payment_error`, `protected`).
- **Money** is always a decimal string (`"25.00"`). Lists are paginated with `?page=` and `?page_size=` (max 100).
- **Throttling**: anonymous 120/min, authenticated 1200/min, auth endpoints 20/min (configurable).
- **Checkout** requires an `Idempotency-Key` header. Retrying with the same key returns the original order
  (200) instead of creating a duplicate.

| Area | Endpoints |
|---|---|
| Auth & account | `auth/register/customer/`, `auth/register/vendor/`, `auth/token/`, `auth/token/refresh/`, `auth/token/verify/`, `auth/logout/`, `auth/password/change/`, `auth/password/reset/`, `auth/password/reset/confirm/`, `me/` |
| Catalogue (public) | `categories/`, `products/` (`q`, `category`, `min_price`, `max_price`, `in_stock`, `sort`), `products/{slug}/`, `products/{slug}/reviews/`, `products/{slug}/questions/`, `products/{slug}/stock-alert/`, `reviews/{id}/`, `stores/`, `stores/{slug}/products/` |
| Customer | `wishlist/`, `cart/`, `cart/items/`, `cart/items/{id}/`, `checkout/payment-methods/`, `checkout/preview/`, `checkout/`, `orders/`, `orders/{number}/`, `orders/{number}/cancel/`, `support/tickets/` (+ `reply/`, `close/`) |
| Vendor | `vendor/application/`, `vendor/dashboard/`, `vendor/products/` (+ `variants/`, `images/`), `vendor/order-items/`, `vendor/order-items/{id}/status/`, `vendor/orders/{number}/`, `vendor/reviews/`, `vendor/questions/` (+ `answer/`) |
| Staff | `staff/dashboard/`, `staff/vendors/` (+ `approve/`, `reject/`, `suspend/`), `staff/orders/` (+ `mark-paid/`, `refund/`, `cancel/`), `staff/order-items/{id}/status/`, `staff/coupons/`, `staff/categories/`, `staff/users/`, `staff/products/`, `staff/reviews/`, `staff/tickets/` (+ `respond/`) |
| Ops | `health/` |

Quick example:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token/ -H "Content-Type: application/json" \
  -d '{"username":"demo_customer","password":"<password>"}' | python -c "import sys,json;print(json.load(sys.stdin)['access'])")
curl -s localhost:8000/api/v1/products/?sort=price_asc
curl -s -X POST localhost:8000/api/v1/cart/items/ -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"product": 1, "quantity": 2}'
curl -s -X POST localhost:8000/api/v1/checkout/ -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Dana Demo","phone":"5550100","address":"1 Main St","city":"Portland","postal_code":"97201","country":"USA","payment_method":"cod"}'
```

### Connecting a browser frontend (React SPA)

1. Add the frontend's origin to `CORS_ALLOWED_ORIGINS` (Vite's `http://localhost:5173` and `http://localhost:3000`
   are allowed by default in DEBUG). Credentials are allowed, and the `Idempotency-Key` header is permitted.
2. Log in with `"use_cookie": true`. The response body contains only the short-lived `access` token: keep it in
   memory, never in localStorage. The refresh token is set as an **httpOnly, Secure, SameSite** cookie scoped to
   `/api/v1/auth/`, so JavaScript cannot read it.
3. When the access token expires (HTTP 401), call `POST /api/v1/auth/token/refresh/` with an empty body,
   `credentials: "include"` and the header `X-Requested-With: XMLHttpRequest`. The cookie is rotated
   automatically. The header is required for cookie-based refresh and logout as CSRF protection.
4. Log out with `POST /api/v1/auth/logout/` (same header). This blacklists the token and clears the cookie.
5. Set `CORECART_FRONTEND_URL` so password-reset emails link to `<frontend>/reset-password?uid=..&token=..`. The
   page then posts to `/api/v1/auth/password/reset/confirm/`.

Mobile and server clients can ignore the cookie and send `refresh` in the request body.

```js
// Minimal fetch wrapper
let access = null;
async function api(path, options = {}) {
  const send = () => fetch(`${API}/api/v1${path}`, {
    ...options, credentials: "include",
    headers: { "Content-Type": "application/json", ...(access && { Authorization: `Bearer ${access}` }),
               ...options.headers },
  });
  let res = await send();
  if (res.status === 401) {
    const r = await fetch(`${API}/api/v1/auth/token/refresh/`, { method: "POST", credentials: "include",
      headers: { "X-Requested-With": "XMLHttpRequest" } });
    if (r.ok) { access = (await r.json()).access; res = await send(); }
  }
  return res;
}
```

Generate a typed client from the schema: `npx openapi-typescript http://localhost:8000/api/v1/schema/ -o src/api/schema.d.ts`.

**Caching:** anonymous `GET` responses for categories, products and stores are sent with
`Cache-Control: public, max-age=60`, so a CDN can cache them. Every response carries an `ETag`, so clients can
revalidate with `If-None-Match` and get a cheap `304`. Unknown `/api/...` URLs return JSON errors, not HTML.

## Technology

- Python 3.14, Django 6.1, Django ORM, forms, templates, auth, admin, messages, sessions and cache
- SQLite for development; PostgreSQL through environment variables
- Plain HTML5, CSS3 (custom design system in `static/css/main.css`) and vanilla JavaScript (`static/js/app.js`).
  No CSS or JavaScript frameworks.
- Pillow for image validation
- Django REST Framework, djangorestframework-simplejwt (JWT with blacklist), drf-spectacular (OpenAPI) and
  django-cors-headers
- Production extra (`uv sync --extra production`): Gunicorn, psycopg (PostgreSQL), redis, django-storages[s3]
- pytest + pytest-django for testing

## Project layout

| App | Responsibility |
|---|---|
| `config` | Settings (environment driven), root URLs, `test_settings.py` for pytest |
| `core` | Home page, shared helpers (money, slugs, safe redirects), image validators, email helper, form renderer, context processor, `seed_demo` command |
| `accounts` | Custom user with roles, customer and vendor profiles, approval workflow, wishlist, role-based permission decorators and mixins |
| `products` | Categories, products, variants, gallery images, reviews, questions, stock alerts; public catalogue and vendor management views |
| `cart` | Database cart and cart rules (`cart/services.py`) |
| `orders` | Coupons, orders, items, timeline; checkout and workflow (`orders/services.py`), payment boundary (`orders/payments.py`), notifications |
| `analytics` | Dashboard aggregation (`analytics/services.py`), SVG chart tags, CSV exports |
| `support` | Tickets with message history and staff workflow |

Business logic lives in the `services.py` modules. Views stay thin and templates contain no business rules.

## Getting started

### Prerequisites

- Python 3.14
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install

```bash
uv sync                       # creates .venv and installs runtime + dev dependencies
# or: python -m venv .venv && .venv\Scripts\activate && pip install django pillow pytest pytest-django
```

### Configure

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

Edit `.env` and set `DJANGO_SECRET_KEY`. Generate one with:

```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

`DJANGO_DEBUG` defaults to **False**. The example file turns it on for local development. Real environment
variables always override `.env`.

### Database and admin user

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser     # superusers get the "admin" role automatically
uv run python manage.py seed_demo           # optional demo catalogue, vendor, customer and WELCOME10 coupon
```

### Run

```bash
uv run python manage.py runserver
```

Open http://localhost:8000. The admin dashboard is at `/staff/dashboard/` and the Django admin at `/admin/`.

## Running tests

```bash
uv run pytest            # full suite
uv run pytest -q tests/test_checkout.py
```

The suite uses `config/test_settings.py` (DEBUG off, fast password hashing, in-memory email, temporary media).
It covers accounts and permissions, catalogue and filtering, image validation, cart rules, checkout (totals,
coupons, inventory conflicts, rollback, duplicate submission), order workflow and ownership, vendor isolation,
analytics definitions, CSV exports, support tickets, template integrity, escaping, security headers and N+1 query
guards.

Also run before a release:

```bash
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

## Static and media files

- `static/` holds source CSS, JS and images. `collectstatic` copies them to `STATIC_ROOT` (`staticfiles/` or
  `DJANGO_STATIC_ROOT`).
- Uploads go to `MEDIA_ROOT` (`media/` or `DJANGO_MEDIA_ROOT`). Images are limited to JPG, PNG, WebP and GIF,
  checked by Pillow, and capped by `CORECART_MAX_IMAGE_SIZE` (2 MB by default).
- With DEBUG on, Django serves media. In production, let the web server (e.g. nginx) serve `/static/` and `/media/`.

## PostgreSQL in production

```bash
uv sync --extra postgres      # installs psycopg
```

```ini
DB_ENGINE=postgresql
DB_NAME=corecart
DB_USER=corecart
DB_PASSWORD=<secret>
DB_HOST=db.internal
DB_PORT=5432
```

Checkout locks product, variant and coupon rows with `SELECT ... FOR UPDATE` on PostgreSQL. On SQLite the
connection uses `IMMEDIATE` transactions instead. On both backends stock and coupon counters change only through
conditional updates, so overselling is impossible.

## Deployment checklist

1. `uv sync --extra production --no-dev` on the (Linux) server.
2. `DJANGO_DEBUG=False`, a unique `DJANGO_SECRET_KEY`, correct `DJANGO_ALLOWED_HOSTS`, and a non-default
   `DJANGO_ADMIN_URL`.
3. HTTPS in front of the app. Secure cookies, SSL redirect and HSTS are on by default when DEBUG is off.
   Set `DJANGO_BEHIND_PROXY=True` if a proxy terminates TLS.
4. PostgreSQL (`DB_ENGINE=postgresql`, `DB_*`), then `python manage.py migrate`.
5. Redis (`REDIS_URL`), so rate limits are shared by all workers.
6. Media: `MEDIA_STORAGE=s3` with a bucket (optionally behind a CDN via `S3_CUSTOM_DOMAIN`), or local disk served
   by nginx at `/media/`.
7. `python manage.py collectstatic --noinput`. Static files get hashed names; serve `/static/` from nginx or a
   CDN with long cache lifetimes.
8. SMTP configured (`EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, ...).
   `CORECART_BASE_URL` set to the API's public URL, and `CORECART_FRONTEND_URL` to the frontend's.
9. `CORS_ALLOWED_ORIGINS=https://app.example.com` for the browser frontend. If the frontend and API are on different
   sites (not just sub-domains), set `JWT_REFRESH_COOKIE_SAMESITE=None`.
10. `python manage.py check --deploy` reports no issues. CoreCart adds its own checks: `corecart.W001`–`W004`
    and `E001`.
11. Run `gunicorn config.wsgi` (settings in `gunicorn.conf.py`; `GUNICORN_WORKERS`, `GUNICORN_BIND`).
12. Point your load balancer's health check at `GET /api/v1/health/`. It verifies the database and cache and
    returns the version.

## Business rules and design decisions

- **Roles** are set only on the server (registration views or Django admin). Purchasing, wishlists and reviews are
  for customer accounts. Vendors and admins use separate accounts to shop.
- **Platform admin** means a superuser, or a staff user with the `admin` role.
- **Vendor visibility**: products are public only when they are active, in an active category, and sold by an
  approved vendor whose account is active (or by CoreCart itself, `vendor = NULL`).
- **Payments**: cash on delivery and bank transfer only. Orders are created unpaid. An administrator records the
  payment in the Django admin ("Record payment received"). `orders/payments.py` is the boundary where a real gateway
  would plug in.
- **Order workflow**: each item moves Pending → Processing → Shipped (tracking number required) → Delivered. Items
  can be cancelled before they ship, which restocks them and recalculates the order total. The parent order status
  is derived from its items. Customers can cancel an unpaid order while every item is still pending. Paid orders
  must be refunded before cancellation. A fully cancelled order releases its coupon use.
- **Revenue** on the admin dashboard counts only paid, non-cancelled orders. Vendor gross sales count
  non-cancelled items. Vendor net revenue is paid items minus the commission captured on each item at purchase.
  Coupons are platform-funded.
- **Addresses**: each customer has one default delivery address on their profile. Every order stores its own
  address snapshot.
- **Guest checkout** is not offered. The legacy `guest_*` order columns are kept so no data is dropped.
- The legacy denormalised vendor metric columns (`total_sales`, etc.) are no longer used. Dashboards compute live
  values.

## Known limitations

- No online card payments (by design for 1.0). Payment confirmation is manual.
- Emails are plain text and sent synchronously after the transaction commits. A failed send is logged and does not
  break the request.
- Customers have a single saved address.
- Without `REDIS_URL` the cache is per process, so rate limits are per worker and cached navigation data can be
  stale for up to an hour on other workers. Set `REDIS_URL` in production.

## License

MIT

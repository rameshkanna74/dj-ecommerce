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

## Technology

- Python 3.14, Django 6.1, Django ORM, forms, templates, auth, admin, messages, sessions and cache
- SQLite for development; PostgreSQL through environment variables
- Plain HTML5, CSS3 (custom design system in `static/css/main.css`) and vanilla JavaScript (`static/js/app.js`).
  No CSS or JavaScript frameworks.
- Pillow for image validation
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

1. `DJANGO_DEBUG=False`, a unique `DJANGO_SECRET_KEY`, correct `DJANGO_ALLOWED_HOSTS` and
   `DJANGO_CSRF_TRUSTED_ORIGINS`.
2. HTTPS in front of the app. Secure cookies, SSL redirect and HSTS are on by default when DEBUG is off.
   Set `DJANGO_BEHIND_PROXY=True` if a proxy terminates TLS.
3. PostgreSQL configured, then `python manage.py migrate`.
4. `python manage.py collectstatic --noinput`, with static and media served by the web server.
5. SMTP configured (`EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, ...) and
   `CORECART_BASE_URL` set to the public URL (used in email links).
6. `python manage.py check --deploy` passes.
7. Run under a WSGI server, e.g. `gunicorn config.wsgi` (not bundled; choose per platform).

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
- The category navigation cache uses the local-memory cache. With several server processes, configure a shared
  cache backend or accept up to an hour of staleness after category edits.

## License

MIT

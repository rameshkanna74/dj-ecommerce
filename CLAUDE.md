# CoreCart — project guide for Claude

Multi-vendor e-commerce backend. **Django 6.1 + Django REST Framework API at `/api/v1/`** (JWT + session auth).
A React frontend will be built separately later by the user. Server-rendered Django templates also exist and work,
but **do not build or redesign UI unless asked** — backend work goes into the DRF API.

`prompt.md` is the original spec. It is partly outdated: it says to remove DRF, but DRF is now required for
all backend APIs. The README is current and documents business rules, API usage and deployment.

## Commands (Windows, PowerShell, uv)
```
uv sync                                   # deps (+ dev: pytest)
.venv\Scripts\python.exe -m pytest -q     # tests — ALWAYS pytest, never `manage.py test`
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file $env:TEMP\s.yml   # must stay warning-free
.venv\Scripts\python.exe manage.py runserver
.venv\Scripts\python.exe manage.py seed_demo   # demo vendor/customer/products, coupon WELCOME10
```
- Local config is in `.env` (gitignored; template in `.env.example`). `DJANGO_DEBUG` defaults to False.
- Tests use `config/test_settings.py`, which ignores `.env` (`DJANGO_SKIP_DOTENV`).
- Production deps: `uv sync --extra production` (gunicorn, psycopg, redis, django-storages).

## Layout (where things live)
| Path | Contents |
|---|---|
| `config/settings.py` | All env-driven settings: DB (sqlite/postgresql), REDIS_URL, MEDIA_STORAGE=s3, CORS, SIMPLE_JWT, REST_FRAMEWORK, MAILERS |
| `config/api_urls.py` | **Every API route** (router + manual nested routes), health, schema/docs |
| `core/api/` | `permissions.py` (IsCustomer, IsVendor, IsApprovedVendor, IsPlatformAdmin, VendorScopedMixin, is_schema_generation), `exceptions.py` (domain error → HTTP mapping), `pagination.py`, `caching.py`, `staff.py` (all `/staff/` admin endpoints) |
| `core/` | utils (`money`, `unique_slugify`, `safe_redirect_target`), validators (images), `emails.py`, `checks.py` (deploy checks), home view |
| `<app>/services.py` | **Business logic.** `cart/services.py`, `orders/services.py` (checkout, status workflow, cancel), `orders/payments.py` (payment boundary), `products/services.py` (filtering, stock alerts), `support/services.py`, `analytics/services.py` (dashboard aggregation) |
| `<app>/api.py` or `<app>/api/` | DRF serializers + views (accounts, products, cart, orders, analytics, support) |
| `<app>/views.py`, `templates/` | Server-rendered site (legacy UI, keep working) |
| `tests/` | pytest suite; fixtures in `tests/conftest.py` (`customer`, `vendor`, `pending_vendor`, `admin_user`, `product`, `variant_product`, `make_product`, `make_coupon`, `fill_cart`, `shipping`, `api(user)`) |

## Rules to follow
- **Views stay thin; rules live in `services.py`**, shared by the API and the HTML views. Services raise domain
  exceptions (`CartError`, `CheckoutError`, `OrderWorkflowError`, `CouponError`, `PaymentError`, `TicketError`).
  `core/api/exceptions.py` maps them to `{"detail","code"}` with a 400 or 409 status. Add new exceptions there.
- Roles are `CustomUser.role` (customer/vendor/admin) and are never accepted from request data.
  - Platform admin = superuser, or a staff user with role `admin` (`user.is_platform_admin`).
  - A vendor can sell only when `vendor_profile.can_sell` (approved and active).
  - Every queryset is scoped to the owner, so other users' objects return 404.
- Public products: always `Product.objects.visible()`.
- Money: `DecimalField` everywhere. The API returns decimal strings. Quantize with `core.utils.money`.
- Checkout and stock: run in `transaction.atomic`, use `select_for_update(of=("self",))`, and change stock and
  coupon counters with conditional `F()` updates. Checkout is idempotent via the `Idempotency-Key` header
  (stored as `Order.checkout_token`).
- Order item workflow: pending → processing → shipped (tracking number required) → delivered. Items can be
  cancelled before they ship. The parent order status is derived. Orders are created unpaid; an admin marks
  them paid.
- Revenue counts only paid, non-cancelled orders. Vendor net revenue = paid line totals minus the line's stored
  `commission_rate`.
- Migrations are additive only; never destructive. Never delete or recreate `db.sqlite3`.
- Avoid N+1 queries: `tests/test_performance.py` asserts flat query counts. Don't call `variant.current_price`
  in loops (it re-fetches the product); use `price_override` or the product's price.
- New DRF views:
  - Give them an explicit `permission_classes`.
  - Use `@extend_schema` where the schema can't be inferred.
  - Guard user-dependent `get_queryset` with `is_schema_generation(self)` so the schema stays warning-free.
  - Add a test for every new endpoint.
- Browser auth: login with `use_cookie: true` puts the refresh token in an httpOnly cookie
  (`accounts/api/cookies.py`). Cookie refresh and logout require the `X-Requested-With` header.

## Gotchas
- Django 6.1: email is configured through `MAILERS` (the `EMAIL_*` settings are deprecated). `createsuperuser`
  sets role=admin via `CustomUserManager`.
- In PowerShell 5.1, `Get-Content -Raw` reads UTF-8 as ANSI and corrupts characters like `·` and `—`. Use the
  Edit tool, or `[IO.File]::ReadAllText/WriteAllText`.
- All app URL modules are mounted at the root with distinct prefixes (`products/`, `vendor/`, `staff/`, ...).
  The API lives only under `/api/v1/` (namespace `api:`).

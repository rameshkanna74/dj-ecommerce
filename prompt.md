# MASTER ENGINEERING PROMPT — CORECART 1.0
## Complete Existing Django E-Commerce Application Audit, Upgrade and Initial Release

Act as a Senior Django Architect, Full-Stack Developer, Database Engineer, UI/UX Designer, Security Engineer and QA Engineer.

Your task is to transform the EXISTING CoreCart Premium project into a complete, stable, polished and release-ready multi-vendor e-commerce application: **CoreCart 1.0**.

This is an existing project. Do not blindly rebuild it or discard working functionality.

First understand the entire existing codebase, then systematically improve its architecture, business logic, frontend, backend, database design, security, performance and user experience.

The final result must be a fully functional Django application, not a static UI prototype or collection of unfinished features.

---

# 1. NON-NEGOTIABLE TECHNOLOGY REQUIREMENTS

Use the following technology stack.

Backend:
- Python
- Django
- Django ORM
- Django Forms and ModelForms
- Django Templates
- Django Authentication
- Django Admin
- Django Middleware
- Django Signals only when genuinely appropriate
- Django Messages Framework
- Django Sessions
- Django Cache Framework where useful
- Django's built-in security features

Frontend:
- Semantic HTML5
- CSS3
- Vanilla JavaScript
- Django Template Language

Database:
- SQLite for local development.
- Structure database configuration so PostgreSQL can be enabled for production through environment variables.
- Never hardcode production database credentials.

Styling restrictions:
- Use normal CSS3 exclusively.
- Do not use Bootstrap.
- Do not use Tailwind CSS.
- Do not use Bulma.
- Do not use Material UI.
- Do not use any CSS framework.
- Do not introduce a frontend framework.
- Do not use jQuery unless an existing essential dependency genuinely requires it.

Package restrictions:
- Avoid unnecessary packages and dependencies.
- Prefer native Django capabilities over third-party packages.
- Inspect existing dependencies before changing them.
- Remove unused Django REST Framework and Daphne dependencies if confirmed unnecessary.
- Keep Pillow only if required by image functionality.
- Do not introduce Celery, Redis, Docker, GraphQL, React, Vue or other infrastructure without a demonstrated requirement.
- Do not introduce a package merely to solve something Django already handles.

Use compatible, maintained versions of Python and Django. Keep dependency versions consistent with the project configuration.

The default application architecture must remain a traditional server-rendered Django application.

---

# 2. PHASE ONE — COMPLETE CODEBASE AUDIT

Before changing code, inspect the entire repository.

Read:
- All Django applications.
- Models.
- Views.
- Forms.
- URL configurations.
- Middleware.
- Signals.
- Managers and QuerySets.
- Services and utility functions.
- Template files.
- CSS and JavaScript.
- Settings.
- Migrations.
- Admin configurations.
- Tests.
- Dependency configuration.
- Existing database schema.

Existing applications include:

- accounts
- products
- cart
- orders
- analytics
- support
- core
- config

Understand how they interact.

Create an internal implementation plan identifying:

1. Existing working features.
2. Incomplete functionality.
3. Incorrect business logic.
4. Security vulnerabilities.
5. Authorization weaknesses.
6. Database design problems.
7. Duplicate or unnecessary code.
8. N+1 database queries.
9. Missing validation.
10. Broken URLs and template references.
11. Missing error handling.
12. Missing test coverage.
13. UI inconsistencies.
14. Missing release-critical functionality.

Do not assume that README documentation accurately reflects the implementation.

Do not overwrite functioning features without understanding their dependencies.

Preserve existing user data and migrations.

Do not delete or recreate the SQLite database.

Do not perform destructive migrations.

---

# 3. PHASE TWO — ARCHITECTURE AND CODE QUALITY

Improve the project using Django's native architecture.

Requirements:

- Use appropriately separated Django applications.
- Keep business logic out of templates.
- Keep views reasonably small.
- Use ModelForms for model-backed forms.
- Use reusable QuerySets and managers.
- Use service functions for complex business operations.
- Use class-based views where they improve clarity.
- Use function-based views where they are simpler.
- Use Django permission checks and reusable access-control mixins.
- Use transaction.atomic() for operations involving multiple database writes.
- Use select_related() and prefetch_related() to optimize queries.
- Add database indexes for frequently queried fields.
- Use database constraints for important invariants.
- Use DecimalField for all monetary values.
- Use timezone-aware datetime handling.
- Use named URL patterns and reverse() or reverse_lazy().
- Avoid unnecessary abstraction and overengineering.

Follow a consistent naming convention and project structure.

Avoid creating unnecessary applications or files.

Do not create generic service layers for simple CRUD operations.

---

# 4. PHASE THREE — USER ACCOUNTS AND ROLE MANAGEMENT

Implement a secure multi-role account system.

Roles:

1. Customer
2. Vendor
3. Administrator

Use the existing custom user model where possible.

Authentication:
- Customer registration.
- Vendor registration.
- Login.
- Logout using POST.
- Password reset.
- Password reset confirmation.
- Secure session handling.
- Profile management.
- Password change.
- Account status management.

Customer profile:
- Full name.
- Email.
- Phone.
- Profile image.
- Address information.
- Account preferences.

Vendor profile:
- Business name.
- Business description.
- Business logo.
- Business banner.
- Contact details.
- Business address.
- Registration information.
- Approval status.
- Store slug.
- Commission configuration.

Vendor approval workflow:

Pending → Approved or Rejected.

Only approved and active vendors can publish products and process orders.

Prevent customers from accessing vendor dashboards.

Prevent vendors from accessing other vendors' products, sales, analytics and orders.

Prevent unauthorized users from accessing administrator functions.

Apply object-level ownership checks to every sensitive operation.

Never trust role information submitted through a browser form.

---

# 5. PHASE FOUR — PRODUCT CATALOG

Create a complete product management system.

Categories:
- Create.
- Update.
- Delete with appropriate protection.
- Category descriptions.
- Category slugs.
- Active/inactive management.

Products:
- Product name.
- Unique slug.
- Description.
- Price.
- Stock.
- Category.
- Vendor.
- Main image.
- Additional images if supported by the existing architecture.
- Active/inactive status.
- Creation and update timestamps.
- Product ratings.
- Review count.

Product functionality:

- Product listing.
- Product details.
- Related products.
- Featured products.
- New arrivals.
- Search.
- Category filtering.
- Minimum and maximum price filtering.
- Sorting by price.
- Sorting by newest.
- Sorting by popularity where reliable data exists.
- Pagination.
- Empty search results.
- Stock availability.
- Out-of-stock indicators.
- Product variants when applicable.

Vendor restrictions:
- Vendors can only manage their own products.
- Unapproved vendors cannot publish products.
- Validate all product fields server-side.
- Prevent negative prices and invalid stock.
- Generate collision-safe slugs.
- Validate uploaded images and file sizes.

Use optimized ORM queries.

Never expose unpublished or inactive products through public listings.

---

# 6. PHASE FIVE — SHOPPING CART

Implement a reliable database-backed shopping cart.

Features:
- Add products.
- Remove products.
- Update quantities.
- Save for later.
- Move saved products back into the cart.
- Display item subtotals.
- Display cart subtotal.
- Display total quantity.
- Display stock availability.
- Display empty-cart state.

Business rules:

- Do not allow zero or negative quantities.
- Do not allow quantities exceeding available stock.
- Do not allow inactive products to be purchased.
- Do not trust browser-calculated prices.
- Recalculate every amount on the server.
- Ensure saved-for-later products are excluded from checkout.
- Handle duplicate cart additions correctly.
- Ensure all cart operations are restricted to the authenticated owner.

Use POST for state-changing operations.

Provide clear feedback for invalid quantities and insufficient stock.

---

# 7. PHASE SIX — CHECKOUT AND ORDER MANAGEMENT

This is one of the most critical areas.

Implement a complete and reliable order workflow.

Checkout must:

1. Require a valid shopping cart.
2. Exclude saved-for-later items.
3. Validate all products.
4. Validate current inventory.
5. Recalculate prices from the database.
6. Validate coupons.
7. Calculate discounts correctly.
8. Calculate the final payable amount.
9. Collect and validate customer delivery information.
10. Create the order.
11. Create order items with immutable price snapshots.
12. Update inventory safely.
13. Record the initial order timeline.
14. Clear the active cart.
15. Prevent duplicate order submissions.

Use transaction.atomic().

Use select_for_update() where supported and appropriate, and design locking behavior carefully for SQLite development and PostgreSQL production.

Handle inventory conflicts gracefully.

Coupon functionality:

- Percentage discounts.
- Fixed discounts.
- Start and expiry dates.
- Usage limits.
- Minimum order value if implemented.
- Active/inactive status.
- Correct discount calculation.
- Prevent discounts exceeding the eligible order amount.
- Protect usage counters against concurrent requests.

Order management:

- Order number.
- Customer.
- Delivery address snapshot.
- Order items.
- Item quantity.
- Purchase-time price.
- Subtotal.
- Discount.
- Final total.
- Payment status.
- Payment method.
- Order status.
- Tracking number.
- Created and updated timestamps.

Order status workflow:

Pending → Processing → Shipped → Delivered.

Support cancellation according to clearly defined business rules.

For multi-vendor orders, maintain separate vendor-specific order item statuses while keeping the parent order status consistent.

Maintain an order status timeline.

Customers can only view their own orders.

Vendors can only manage their own order items.

Administrators can manage all orders.

Generate printable invoices using Django templates.

Payment integration:

Do not fabricate successful online payments.

For the initial release, implement an explicitly configured payment method such as cash on delivery or manual payment confirmation, depending on the available business requirements.

Keep payment processing separate from order creation so a real payment gateway can be integrated later.

Never mark an order as paid simply because an order record was created.

---

# 8. PHASE SEVEN — WISHLIST, REVIEWS AND CUSTOMER FEATURES

Wishlist:
- Add product.
- Remove product.
- Display wishlist.
- Move wishlist product into cart.
- Prevent duplicate entries.

Reviews:
- One review per customer per product.
- Rating between 1 and 5.
- Review text validation.
- Review editing and deletion according to ownership.
- Correct average-rating calculation.
- Correct review-count calculation.
- Prevent unauthorized review modifications.

If implementing verified-purchase reviews, verify that the customer actually purchased the product.

Product questions:
- Submit questions.
- Display questions.
- Vendor responses.
- Administrator moderation where appropriate.

Recently viewed products:
- Store recently viewed products in sessions.
- Avoid unnecessary database queries.
- Limit the history.
- Ensure the middleware is correctly registered if middleware is retained.

Stock alerts:
- Prevent duplicate subscriptions.
- Notify subscribers when stock is replenished.
- Avoid sending duplicate notifications.

---

# 9. PHASE EIGHT — VENDOR DASHBOARD

Build a complete vendor management interface.

Dashboard KPIs:
- Total products.
- Active products.
- Total orders.
- Pending orders.
- Units sold.
- Gross sales.
- Revenue.
- Product ratings.

Vendor functionality:

- Manage products.
- Upload product images.
- Update stock.
- View incoming orders.
- View order details.
- Update item fulfillment status.
- Add tracking numbers.
- View sales history.
- View best-selling products.
- View revenue trends.
- Manage store information.
- View customer reviews.

All analytics must be based on actual persisted data.

Do not hardcode dashboard numbers.

Ensure vendor queries are filtered by the authenticated vendor profile.

Use Django ORM aggregation rather than loading unnecessary records into Python.

---

# 10. PHASE NINE — ADMINISTRATION

Use Django Admin as the foundation.

Improve the administration experience with:

- Custom user administration.
- Vendor approval and rejection.
- Product management.
- Category management.
- Order management.
- Coupon management.
- Review moderation.
- Support ticket management.
- Stock monitoring.
- Sales reports.

Implement an administrator dashboard with:

- Total registered customers.
- Total vendors.
- Pending vendor approvals.
- Total products.
- Total orders.
- Pending orders.
- Revenue.
- Recent orders.
- Top-selling products.
- Sales trends.
- Category performance.

All calculations must use correct business definitions.

Exclude cancelled and unpaid orders from recognized revenue.

Use accurate aggregation and avoid duplicated sums caused by joins.

Provide CSV export where appropriate.

Protect all administrator functionality with proper authorization.

---

# 11. PHASE TEN — CUSTOMER SUPPORT

Implement a complete support ticket workflow.

Features:
- Create ticket.
- Ticket subject.
- Ticket message.
- Optional order association.
- Ticket status.
- Ticket history.
- Administrator responses.
- Customer ticket listing.
- Ticket detail view.

Statuses:

Open → In Progress → Resolved → Closed.

Customers can only view their own tickets.

Administrators can manage all tickets.

Vendors must not gain access to customer support records without explicit authorization.

Provide meaningful feedback and notifications.

---

# 12. PHASE ELEVEN — COMPLETE FRONTEND REDESIGN

Redesign the frontend into a cohesive, premium e-commerce experience.

Important:

Use only:
- HTML5.
- Django Templates.
- CSS3.
- Vanilla JavaScript.

No CSS frameworks.

No frontend frameworks.

Design direction:

A premium, modern marketplace with a clean visual hierarchy, refined spacing, elegant typography, professional product cards, subtle shadows, carefully selected colors and smooth interactions.

Do not make every element look like a glass card.

Prioritize usability, readability and conversion.

Create a consistent design system using CSS custom properties.

Establish:
- Primary colors.
- Secondary colors.
- Accent colors.
- Background colors.
- Surface colors.
- Typography scale.
- Spacing scale.
- Border radii.
- Shadows.
- Focus states.
- Transition rules.

Build reusable CSS components.

Frontend requirements:

A. Global layout
- Responsive navigation.
- Logo.
- Search bar.
- Category navigation.
- Cart indicator.
- Account menu.
- Footer.
- Messages and notifications.

B. Homepage
- Hero section.
- Featured categories.
- Featured products.
- New arrivals.
- Best sellers where supported by actual data.
- Promotional sections.
- Clear calls to action.

C. Product listing
- Responsive product grid.
- Search.
- Filters.
- Sorting.
- Pagination.
- Product images.
- Price.
- Rating.
- Stock status.
- Add-to-cart action.

D. Product detail
- Image gallery.
- Product description.
- Price.
- Stock availability.
- Variants.
- Quantity selector.
- Add-to-cart.
- Wishlist.
- Reviews.
- Related products.

E. Customer account
- Dashboard.
- Profile.
- Addresses.
- Wishlist.
- Orders.
- Order details.
- Support tickets.

F. Vendor account
- Dashboard.
- Sidebar navigation.
- Product management.
- Order management.
- Inventory.
- Analytics.
- Store settings.

G. Administrator experience
- Useful dashboard.
- Clean navigation.
- Data tables.
- Filters.
- Action buttons.
- Status indicators.

H. Cart and checkout
- Clear order summary.
- Quantity controls.
- Discount display.
- Delivery information.
- Final total.
- Validation messages.

I. Authentication
- Registration.
- Login.
- Password reset.
- Password change.

Responsive requirements:
- Mobile-first implementation.
- Mobile navigation.
- Tablet layout.
- Desktop layout.
- No horizontal overflow.
- Accessible forms.
- Touch-friendly controls.

Accessibility:
- Semantic HTML.
- Correct heading hierarchy.
- Labels for inputs.
- Keyboard navigation.
- Visible focus states.
- Appropriate ARIA attributes.
- Sufficient color contrast.
- Reduced-motion support.

JavaScript should only improve user experience.

All important business logic and validation must remain on the Django backend.

Avoid inline CSS.

Avoid duplicated CSS.

Avoid unnecessary JavaScript.

---

# 13. PHASE TWELVE — DATABASE AND CONFIGURATION

Keep SQLite as the default development database.

Prepare database configuration for PostgreSQL through environment variables.

Use environment-based settings for:

- SECRET_KEY.
- DEBUG.
- ALLOWED_HOSTS.
- Database engine.
- Database credentials.
- Email settings.
- Base URL.

Separate development and production concerns cleanly without creating unnecessary settings complexity.

Security configuration must include:
- CSRF protection.
- Secure authentication.
- Session security.
- Password validation.
- Clickjacking protection.
- Secure cookies in production.
- HTTPS-aware settings.
- Correct host validation.
- Safe uploaded-file handling.

Do not commit secrets.

Do not expose SECRET_KEY in source control.

Keep media files separate from static files.

Configure Django static file handling correctly.

Prepare the project for PostgreSQL without requiring PostgreSQL for local development.

Do not migrate the development database unnecessarily.

---

# 14. PHASE THIRTEEN — TESTING AND QUALITY ASSURANCE

Testing is mandatory.

Use Django's built-in testing framework.

Test every major business operation.

Accounts:
- Registration.
- Authentication.
- Password reset.
- Role permissions.
- Unauthorized access.

Products:
- Product listing.
- Search.
- Filtering.
- Pagination.
- Product ownership.
- Image validation.

Cart:
- Add.
- Update.
- Remove.
- Saved for later.
- Stock validation.
- Unauthorized modification.

Checkout:
- Empty cart.
- Valid order.
- Invalid coupon.
- Expired coupon.
- Inventory conflict.
- Saved products exclusion.
- Duplicate submission.
- Correct totals.
- Correct stock deduction.
- Rollback after failure.

Orders:
- Customer ownership.
- Vendor ownership.
- Status transitions.
- Timeline creation.
- Invoice access.

Vendor:
- Approval workflow.
- Product ownership.
- Order management.
- Analytics isolation.

Admin:
- Permissions.
- Dashboard calculations.
- CSV exports.

Support:
- Ticket creation.
- Customer ownership.
- Administrator management.

Frontend:
- Critical page rendering.
- Form errors.
- Empty states.
- Navigation.
- Responsive behavior where testable.

Run:

python manage.py check

python manage.py makemigrations --check --dry-run

python manage.py migrate

python manage.py test

Do not claim that tests pass without executing them.

Fix all discovered failures.

Do not disable tests or weaken assertions to make the test suite pass.

---

# 15. PHASE FOURTEEN — PERFORMANCE AND SECURITY REVIEW

Inspect every major database query.

Prevent N+1 query patterns.

Use:
- select_related()
- prefetch_related()
- annotate()
- aggregate()
- Exists()
- database constraints
- indexes
- pagination

Do not cache data unnecessarily.

If caching is used, ensure invalidation is correct.

Security review must include:

- IDOR vulnerabilities.
- Broken access control.
- CSRF.
- XSS.
- Unsafe redirects.
- Insecure file uploads.
- Mass assignment.
- Price manipulation.
- Coupon abuse.
- Inventory race conditions.
- Duplicate submissions.
- Unauthorized object modification.
- Information leakage.
- Debug mode exposure.

Never rely on frontend validation for security.

---

# 16. PHASE FIFTEEN — DOCUMENTATION AND RELEASE PREPARATION

Update the README with:

- Project overview.
- Features.
- Technology stack.
- Prerequisites.
- Installation.
- Virtual environment setup.
- Dependency installation.
- Environment configuration.
- Database migration.
- Superuser creation.
- Development server.
- Running tests.
- Static and media file configuration.
- PostgreSQL production configuration.
- Deployment checklist.

Provide a sample environment file without real credentials.

Ensure the project starts from a clean setup.

Check that all templates, static assets, URL names and navigation links are valid.

Remove unused files and dependencies only after verifying that they are not needed.

---

# 17. EXECUTION RULES

Work directly on the existing repository.

Do not merely provide recommendations or sample code.

Actually implement the changes.

Follow this order:

1. Audit the existing application.
2. Identify critical bugs.
3. Fix architecture and configuration.
4. Improve database models and migrations.
5. Complete business logic.
6. Complete customer functionality.
7. Complete vendor functionality.
8. Complete administrator functionality.
9. Redesign frontend.
10. Optimize queries.
11. Add and execute tests.
12. Complete documentation.
13. Perform final release checks.

Do not stop after creating the homepage.

Do not leave placeholder buttons.

Do not create non-functional forms.

Do not use fake analytics data.

Do not leave TODO comments for core release functionality.

Do not implement fake payment processing.

Do not silently remove existing features.

When a requirement is ambiguous, make the smallest sensible decision consistent with the existing application and document it.

When a feature cannot be safely completed because external credentials or a business decision are missing, implement a clear integration boundary rather than pretending it works.

Keep changes focused, maintainable and easy to understand.

---

# 18. DEFINITION OF DONE — CORECART 1.0

The project is ready for its initial release only when:

- The application starts successfully.
- All migrations apply cleanly.
- SQLite works locally.
- PostgreSQL configuration is prepared.
- Customer registration and authentication work.
- Vendor approval works.
- Product management works.
- Search and filtering work.
- Cart operations work.
- Checkout creates correct orders.
- Stock updates are safe.
- Coupons calculate correctly.
- Orders and invoices work.
- Vendor permissions are enforced.
- Admin management works.
- Analytics reflect real data.
- Support tickets work.
- The frontend is responsive.
- No CSS framework is used.
- No unnecessary dependencies remain.
- No critical security issues remain.
- All critical tests pass.
- Documentation is complete.

At the end, provide:

1. Summary of implemented changes.
2. Updated project architecture.
3. New and modified files.
4. Database and migration changes.
5. Dependencies added or removed, with reasons.
6. Features completed.
7. Security improvements.
8. Test results with actual execution details.
9. Known limitations.
10. Exact commands to run the application.

**Final objective: Deliver a genuinely functional, maintainable and professionally designed CoreCart 1.0 application using Django, SQLite for development, PostgreSQL-ready configuration for production, and pure HTML5, CSS3 and Vanilla JavaScript.**
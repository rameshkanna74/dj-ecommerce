/* CoreCart progressive enhancements. Every feature works without JavaScript;
   this file only improves the experience. */
(function () {
  "use strict";

  // Mobile navigation toggle
  const toggle = document.querySelector("[data-nav-toggle]");
  const panel = document.getElementById("mobile-panel");
  if (toggle && panel) {
    toggle.addEventListener("click", function () {
      const open = panel.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  // Close <details> menus when clicking outside or pressing Escape
  document.addEventListener("click", function (event) {
    document.querySelectorAll("details[data-menu][open]").forEach(function (menu) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document.querySelectorAll("details[data-menu][open]").forEach(function (menu) {
      menu.removeAttribute("open");
      const summary = menu.querySelector("summary");
      if (summary) summary.focus();
    });
  });

  // Dismissible messages
  document.querySelectorAll("[data-dismiss]").forEach(function (button) {
    button.addEventListener("click", function () {
      const target = button.closest(".alert");
      if (target) target.remove();
    });
  });

  // Prevent double submission (server-side protection exists as well)
  document.querySelectorAll("form[data-submit-once]").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (form.dataset.submitted === "true") {
        return;
      }
      form.dataset.submitted = "true";
      form.querySelectorAll("button[type=submit]").forEach(function (button) {
        window.setTimeout(function () {
          button.disabled = true;
          if (button.dataset.loadingText) button.textContent = button.dataset.loadingText;
        }, 0);
      });
    });
  });

  // Confirmation prompts for destructive actions
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // Quantity steppers
  document.querySelectorAll("[data-qty]").forEach(function (wrapper) {
    const input = wrapper.querySelector("input");
    if (!input) return;
    wrapper.querySelectorAll("button[data-step]").forEach(function (button) {
      button.addEventListener("click", function () {
        const min = parseInt(input.min || "1", 10);
        const max = parseInt(input.max || "99", 10);
        const next = (parseInt(input.value || "1", 10) || 1) + parseInt(button.dataset.step, 10);
        input.value = String(Math.min(max, Math.max(min, next)));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
  });

  // Auto-submit selects (sorting, filters)
  document.querySelectorAll("select[data-autosubmit]").forEach(function (select) {
    select.addEventListener("change", function () {
      if (select.form) select.form.requestSubmit ? select.form.requestSubmit() : select.form.submit();
    });
  });

  // Product gallery
  const main = document.querySelector("[data-gallery-main]");
  if (main) {
    document.querySelectorAll("[data-gallery-thumb]").forEach(function (thumb) {
      thumb.addEventListener("click", function () {
        main.src = thumb.dataset.src;
        main.alt = thumb.dataset.alt || main.alt;
        document.querySelectorAll("[data-gallery-thumb]").forEach(function (other) {
          other.setAttribute("aria-pressed", String(other === thumb));
        });
      });
    });
  }

  // Variant selection updates the displayed price and max quantity
  const variantInputs = document.querySelectorAll("input[name=variant][data-price]");
  const priceEl = document.querySelector("[data-product-price]");
  const qtyInput = document.querySelector("[data-qty-input]");
  variantInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      if (priceEl && input.dataset.price) priceEl.textContent = input.dataset.price;
      if (qtyInput && input.dataset.stock) {
        qtyInput.max = input.dataset.stock;
        if (parseInt(qtyInput.value, 10) > parseInt(input.dataset.stock, 10)) qtyInput.value = input.dataset.stock;
      }
    });
  });

  // Collapse the catalogue filter panel on small screens unless a filter is active
  const filters = document.querySelector("details.filters");
  if (filters && window.matchMedia("(max-width: 959px)").matches && !filters.hasAttribute("data-active")) {
    filters.removeAttribute("open");
  }

  // Print buttons
  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () { window.print(); });
  });
})();

// App shell: htmx page swaps plus the Alpine sheet, hold and toast components.
let sheetOpener = null;
let sheetFocusId = null;

const store = () => Alpine.store("shell");

function sheet() {
  return {
    open: false,
    opener: null,
    startY: null,
    dy: 0,
    init() {
      // A load-triggered swap can land before Alpine starts; open it then.
      if (this.$el.innerHTML.trim()) this.show();
    },
    show(detail) {
      this.opener = detail?.opener ?? null;
      this.$el.showModal();
      this.open = true;
    },
    close() {
      if (!this.open) return;
      this.open = false;
      this.$el.close();
      this.$el.style.transform = "";
      this.$el.innerHTML = "";
      // A save can swap the opener out; focus its replacement.
      const opener = this.opener;
      (opener?.isConnected
        ? opener
        : document.getElementById(opener?.id)
      )?.focus();
    },
    trapTab(e) {
      // Fallback wrap for when the focus trap has not handled the key.
      if (e.defaultPrevented) return;
      const items = [
        ...this.$el.querySelectorAll(
          "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select, textarea, [tabindex]:not([tabindex='-1'])",
        ),
      ];
      if (!items.length) return;
      const [first, last] = [items[0], items.at(-1)];
      const active = document.activeElement;
      if (
        !this.$el.contains(active) ||
        (e.shiftKey ? active === first : active === last)
      ) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus();
      }
    },
    dragStart(e) {
      if (e.target.closest("[data-sheet-handle]")) {
        this.startY = e.clientY;
        this.$el.setPointerCapture(e.pointerId);
      }
    },
    dragMove(e) {
      if (this.startY === null) return;
      this.dy = Math.max(0, e.clientY - this.startY);
      this.$el.style.transform = `translateY(${this.dy}px)`;
    },
    dragEnd() {
      if (this.startY === null) return;
      const far = this.dy > 80;
      this.startY = null;
      this.dy = 0;
      this.$el.style.transform = "";
      if (far) this.close();
    },
  };
}

function hold(key) {
  return {
    timer: null,
    start() {
      delete this.$el.dataset.held;
      this.timer = setTimeout(() => this.fire(), 500);
    },
    stop() {
      clearTimeout(this.timer);
      this.$el.classList.remove("nav__item--held");
    },
    fire() {
      this.$el.classList.add("nav__item--held");
      this.$el.dataset.held = "1";
      navigator.vibrate?.(15);
      document.querySelector(`[data-hold-link="${key}"]`).click();
    },
  };
}

function toast() {
  return {
    message: "",
    t: null,
    show(detail) {
      this.message = detail?.message ?? detail?.value?.message ?? "";
      clearTimeout(this.t);
      this.t = setTimeout(() => (this.message = ""), 4000);
    },
  };
}

// Send invoice: open WhatsApp in a new tab so this page stays for Copy text. If
// the tab is blocked, or the page is still in front 3 s later, WhatsApp didn't
// open, so offer the text to copy.
function invoiceSend() {
  return {
    fallback: false,
    t: null,
    send() {
      const opened = window.open(this.$el.dataset.waUrl, "_blank");
      if (!opened) {
        this.fallback = true;
        return;
      }
      opened.opener = null;
      this.wait();
    },
    wait() {
      this.cancel();
      this.t = setTimeout(() => {
        if (document.visibilityState === "visible") this.fallback = true;
      }, 3000);
    },
    cancel() {
      clearTimeout(this.t);
    },
    async copy() {
      const text = JSON.parse(
        document.getElementById("invoice-text").textContent,
      );
      try {
        await navigator.clipboard.writeText(text);
        window.dispatchEvent(
          new CustomEvent("toast", {
            detail: { message: "Invoice text copied" },
          }),
        );
      } catch {
        window.dispatchEvent(
          new CustomEvent("toast", {
            detail: { message: "Couldn't copy. Try again." },
          }),
        );
      }
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.store("shell", { tab: document.body.dataset.tab || "", depth: 0 });
  Alpine.data("sheet", sheet);
  Alpine.data("hold", hold);
  Alpine.data("toast", toast);
  Alpine.data("invoiceSend", invoiceSend);
});

// The hold link already navigated; the release click must not reach htmx, or
// hx-sync would abort the pending hold request.
document.addEventListener(
  "click",
  (evt) => {
    const held = evt.target.closest?.('[data-held="1"]');
    if (!held) return;
    delete held.dataset.held;
    evt.preventDefault();
    evt.stopImmediatePropagation();
  },
  true,
);

document.addEventListener("htmx:before:request", (evt) => {
  const { sourceElement: elt, target } = evt.detail.ctx;
  if (elt?.hasAttribute("data-back") && store().depth > 0) {
    evt.preventDefault();
    history.back();
  } else if (target?.id === "sheet") {
    // A sheet that re-renders itself keeps its first opener.
    if (target.open) sheetFocusId = document.activeElement?.id;
    else sheetOpener = document.activeElement;
  }
});

function pageSwapped(elt) {
  const page = document.querySelector("#page .page");
  const title = page?.dataset.title ?? "";
  window.scrollTo(0, 0);
  store().tab = page?.dataset.tab ?? "";
  document.body.dataset.subpage = page?.dataset.subpage ?? "";
  document.title = `${title} · Tailorly`;
  document.querySelector("#page h1")?.focus({ preventScroll: true });
  // A link to page#id (S12 to an S04 item or an S16 queue) lands on that id.
  const hash = elt?.getAttribute("href")?.split("#")[1];
  if (hash) document.getElementById(hash)?.scrollIntoView();
  const announce = document.getElementById("announce");
  announce.textContent = "";
  requestAnimationFrame(() => (announce.textContent = title));
  if (elt?.hasAttribute("hx-push-url")) store().depth += 1;
}

document.addEventListener("htmx:after:swap", (evt) => {
  const { sourceElement: elt, target } = evt.detail.ctx;
  if (!target) return;
  if (target.id === "page") {
    pageSwapped(elt);
  } else if (evt.detail.ctx.request?.headers?.["HX-History-Restore-Request"]) {
    // Back and Forward restore the whole body, not #page.
    pageSwapped(null);
  } else if (target.id === "sheet" && target.innerHTML.trim()) {
    if (!target.open) {
      window.dispatchEvent(
        new CustomEvent("sheet:open", { detail: { opener: sheetOpener } }),
      );
    } else if (!target.querySelector('[aria-invalid="true"]')) {
      document.getElementById(sheetFocusId)?.focus();
    }
  } else if (
    elt?.id &&
    !elt.isConnected &&
    (!document.activeElement || document.activeElement === document.body)
  ) {
    // A chip or segment replaced itself and focus fell to the body: keep it
    // on the new copy. If focus moved to another control, leave it there.
    document.getElementById(elt.id)?.focus();
  }
  // An outerHTML swap leaves `target` detached; look in its replacement.
  const live = target.isConnected ? target : document.getElementById(target.id);
  live?.querySelector('[aria-invalid="true"], [data-invalid]')?.focus();
});

window.addEventListener("popstate", () => {
  store().depth = Math.max(0, store().depth - 1);
});

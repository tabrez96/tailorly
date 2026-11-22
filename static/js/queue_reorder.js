// S16: reorder one employee's queue by drag (x-sort) or Up/Down; each move is saved and announced.
function csrfHeaders() {
  const h = JSON.parse(
    document.body.getAttribute("hx-headers:inherited") || "{}",
  );
  return { "X-CSRFToken": h["X-CSRFToken"] };
}

const SAVE_FAILED =
  "Couldn't save the new order. Check your connection and try again.";

function ordinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function queueReorder(url) {
  return {
    picked: null,
    busy: false,
    spoken: "",
    error: "",
    confirmed: [], // the order the server last saved
    root: null,
    order: 0, // bumped whenever the DOM order changes, so the bar title re-renders
    init() {
      this.root = this.$root;
      this.confirmed = this.keys();
    },
    list() {
      return this.root.querySelector("[data-queue-body] ol");
    },
    rows() {
      return [...(this.list()?.children ?? [])];
    },
    keys() {
      return this.rows().map((li) => li.dataset.key);
    },
    row(key) {
      return this.rows().find((li) => li.dataset.key === key);
    },
    total() {
      return this.rows().length;
    },
    position() {
      return this.keys().indexOf(this.picked) + 1;
    },
    barTitle() {
      this.order;
      const li = this.row(this.picked);
      return li
        ? `${li.dataset.garment}, ${ordinal(this.position())} of ${this.total()}`
        : "";
    },
    barDue() {
      this.order;
      return this.row(this.picked)?.dataset.due ?? "";
    },
    pick(key) {
      if (this.picked === key) return this.done();
      this.picked = key;
      this.$nextTick(() => this.$refs.down.focus());
    },
    done() {
      const key = this.picked;
      this.picked = null;
      if (key)
        this.$nextTick(() =>
          this.row(key)?.querySelector(".qrow__handle")?.focus(),
        );
    },
    renumber() {
      this.rows().forEach((li, i) => {
        li.querySelector(".qrow__rank").textContent = i + 1;
      });
      this.order++;
    },
    restore() {
      const ol = this.list();
      this.confirmed.forEach((k) => ol.append(this.row(k)));
      this.renumber();
    },
    step(delta) {
      const to = this.position() + delta;
      if (this.busy || to < 1 || to > this.total()) return;
      const li = this.row(this.picked);
      if (delta < 0) li.previousElementSibling.before(li);
      else li.nextElementSibling.after(li);
      this.renumber();
      this.save(this.picked, to);
    },
    dropped(key, position) {
      // SortableJS has already moved the node; $position is 0-based.
      if (this.busy) return this.restore();
      this.renumber();
      this.save(key, position + 1);
    },
    say(text) {
      this.spoken = "";
      requestAnimationFrame(() => (this.spoken = text));
    },
    async save(key, to) {
      this.busy = true;
      this.error = "";
      const garment = this.row(key)?.dataset.garment;
      const body = new FormData();
      body.append("key", key);
      body.append("to", to);
      try {
        const r = await fetch(url, {
          method: "POST",
          body,
          headers: csrfHeaders(),
          credentials: "same-origin",
        });
        if (!r.ok) throw new Error(r.status);
        const t = document.createElement("template");
        t.innerHTML = await r.text();
        document
          .getElementById("plan-hero")
          ?.replaceWith(t.content.getElementById("plan-hero"));
        this.root.querySelector("[data-queue-body]").innerHTML =
          t.content.querySelector("[data-queue-body]").innerHTML;
        // htmx 4 has no MutationObserver: wire up the swapped-in Back to suggested button.
        htmx.process(document.getElementById("plan-hero"));
        htmx.process(this.root.querySelector("[data-queue-body]"));
        this.order++;
        this.confirmed = this.keys();
        if (!this.confirmed.includes(this.picked)) this.picked = null;
        this.say(
          `${garment} moved to position ${this.confirmed.indexOf(key) + 1} of ${this.total()}.`,
        );
      } catch {
        this.restore();
        this.error = SAVE_FAILED;
      } finally {
        this.busy = false;
      }
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("queueReorder", queueReorder);
});

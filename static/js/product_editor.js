// Product sheet: the measurement list and the options editor.
// Everything is posted as two JSON fields (measurements_json, options_json).

const byId = (id) => document.getElementById(id);

// Focus an element once Alpine has rendered; fall back to its mirror (Up <-> Down)
// when the button we pressed is now disabled at an end of the list.
function refocus(vm, id, mirror) {
  vm.$nextTick(() => {
    const el = byId(id);
    (el && !el.disabled ? el : byId(mirror))?.focus();
  });
}

function move(list, i, delta) {
  const j = i + delta;
  if (j < 0 || j >= list.length) return false;
  [list[i], list[j]] = [list[j], list[i]];
  return true;
}

function productEditor() {
  return {
    measurements: [],
    options: [],
    materials: [],
    errors: {},
    editingMeasurements: false,
    uid: 0,
    init() {
      const data = JSON.parse(
        this.$el.querySelector("#product-editor-data").textContent,
      );
      this.measurements = data.measurements;
      this.materials = data.materials;
      this.errors = data.errors;
      this.options = data.options.map((o, i) => ({
        ...o,
        uid: ++this.uid,
        open: false,
        err: data.errors.option[i] || {},
      }));
      const first =
        this.options.find((o) => Object.keys(o.err).length) || this.options[0];
      if (first) first.open = true;
      if (this.errors.measurements) this.editingMeasurements = true;
      this.$nextTick(() =>
        this.$el
          .closest("form")
          .querySelector('[aria-invalid="true"]')
          ?.focus(),
      );
    },
    get wholeOptionsError() {
      return (
        Boolean(this.errors.options) &&
        !this.options.some((o) => Object.keys(o.err).length)
      );
    },
    get measurementsJson() {
      return JSON.stringify(this.measurements);
    },
    get optionsJson() {
      return JSON.stringify(this.options.map(({ uid, open, err, ...o }) => o));
    },
    get measurementNames() {
      return this.measurements
        .map((m) => m.trim())
        .filter(Boolean)
        .join(", ");
    },
    get measurementCount() {
      return this.measurements.filter((m) => m.trim()).length;
    },
    material(o) {
      return this.materials.find((m) => m.id === o.material);
    },
    summary(o) {
      const choices = o.choices.map((c) => c.trim()).filter(Boolean);
      const parts = [
        o.answer === "choice" ? `Choice: ${choices.join(", ")}` : "Yes or no",
      ];
      const material = this.material(o);
      if (material) parts.push(material.name);
      parts.push(o.asked_when === "when_done" ? "When done" : "At order");
      return parts.join(" · ");
    },
    openOnly(o) {
      this.options.forEach((x) => (x.open = x === o));
    },
    addOption() {
      const o = {
        name: "",
        answer: "yes_no",
        choices: [],
        material: null,
        asks_quantity: false,
        asks_notes: false,
        asked_when: "at_order",
        uid: ++this.uid,
        open: true,
        err: {},
      };
      this.options.push(o);
      this.openOnly(this.options.at(-1));
      this.$nextTick(() => byId(`opt-${o.uid}-name`)?.focus());
    },
    removeOption(o) {
      this.options.splice(this.options.indexOf(o), 1);
      this.$nextTick(() => byId("opt-add").focus());
    },
    moveOption(o, delta, id) {
      if (!move(this.options, this.options.indexOf(o), delta)) return;
      refocus(
        this,
        id,
        id.replace(/-(up|down)-/, (_, d) => `-${d === "up" ? "down" : "up"}-`),
      );
    },
    sorted(uid, position) {
      const from = this.options.findIndex((o) => o.uid === uid);
      if (from < 0) return;
      const [o] = this.options.splice(from, 1);
      this.options.splice(position, 0, o);
    },
    setAnswer(o, answer) {
      o.answer = answer;
      if (answer === "choice") {
        while (o.choices.length < 2) o.choices.push("");
      }
      o.err.choices = "";
    },
    setMaterial(o, value) {
      o.material = value ? Number(value) : null;
      if (!o.material) o.asks_quantity = false;
      o.err.material = "";
    },
    addChoice(o) {
      o.choices.push("");
      const id = `opt-${o.uid}-choice-${o.choices.length - 1}`;
      this.$nextTick(() => byId(id)?.focus());
    },
    removeChoice(o, i) {
      o.choices.splice(i, 1);
      this.$nextTick(() => byId(`opt-${o.uid}-choice-add`)?.focus());
    },
    moveChoice(o, i, delta) {
      if (!move(o.choices, i, delta)) return;
      const id = (n, d) => `opt-${o.uid}-choice-${n}-${d}`;
      const d = delta < 0 ? "up" : "down";
      refocus(
        this,
        id(i + delta, d),
        id(i + delta, d === "up" ? "down" : "up"),
      );
    },
    addMeasurement() {
      this.measurements.push("");
      const id = `m-${this.measurements.length - 1}`;
      this.errors.measurements = "";
      this.$nextTick(() => byId(id)?.focus());
    },
    removeMeasurement(i) {
      this.measurements.splice(i, 1);
      this.$nextTick(() => byId("m-add")?.focus());
    },
    moveMeasurement(i, delta) {
      if (!move(this.measurements, i, delta)) return;
      const d = delta < 0 ? "up" : "down";
      refocus(
        this,
        `m-${i + delta}-${d}`,
        `m-${i + delta}-${d === "up" ? "down" : "up"}`,
      );
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("productEditor", productEditor);
});

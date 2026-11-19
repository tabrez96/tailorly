// Edit measurements page: inches/cm conversion and + Add measurement rows.

function measureForm(unit) {
  return {
    unit,
    newRows: [],
    next: 0,
    // Prefilled values are inches, so switching units converts what is on screen
    // before Save; the server reads every value in the unit that is selected.
    convert(to) {
      if (to === this.unit) return;
      const factor = to === "cm" ? 2.54 : 1 / 2.54;
      this.$root.querySelectorAll("[data-measure]").forEach((el) => {
        const v = el.value.trim();
        if (!/^\d+(\.\d+)?$/.test(v)) return;
        el.value = String(Math.round(Number(v) * factor * 100) / 100);
      });
      this.unit = to;
    },
    addRow() {
      const i = this.next++;
      this.newRows.push(i);
      this.$nextTick(() => document.getElementById(`new-name-${i}`)?.focus());
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("measureForm", measureForm);
});

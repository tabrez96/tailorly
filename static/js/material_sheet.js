// Add material sheet: picker filter, and totals from unit prices x quantity.

// Same cent rounding as the server (half up). toPrecision drops float noise
// after the x100 step, so 0.5 x 2.01 gives 1.01.
function materialTotal(n, unit) {
  return String(
    Math.round(Number((n * Number(unit) * 100).toPrecision(12))) / 100,
  );
}

function materialSheet() {
  const s = JSON.parse(
    document.getElementById("material-sheet-data").textContent,
  );
  return {
    ...s,
    q: "",
    all: false,
    changing: s.changing || false,
    // The user emptied Cost: keep it unknown when the quantity changes.
    costCleared: s.cost === "",
    get qtyLabel() {
      return this.unit ? `Quantity (${this.unit})` : "Quantity";
    },
    shown(m, i) {
      const q = this.q.trim().toLowerCase();
      if (q) return m.name.toLowerCase().includes(q);
      return this.all || i < 3 || m.id === this.picked;
    },
    pick(m) {
      this.picked = m.id;
      this.unit = m.unit;
      this.unitCost = m.unitCost;
      this.unitSell = m.unitSell;
      this.onBill = m.billed;
      this.costCleared = false;
      this.fill();
    },
    fill() {
      const n = parseFloat(String(this.qty).replace(/[,\s]/g, ""));
      if (!(n > 0)) return;
      const total = (u) => materialTotal(n, u);
      if (this.unitCost !== null && !this.costCleared)
        this.cost = total(this.unitCost);
      if (this.unitSell !== null) this.sell = total(this.unitSell);
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("materialSheet", materialSheet);
});

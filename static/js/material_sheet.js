// Add material sheet: picker filter, and totals from unit prices x quantity.

function materialSheet() {
  const s = JSON.parse(
    document.getElementById("material-sheet-data").textContent,
  );
  return {
    ...s,
    q: "",
    all: false,
    changing: false,
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
      this.fill();
    },
    fill() {
      const n = parseFloat(String(this.qty).replace(/[,\s]/g, ""));
      if (!(n > 0)) return;
      const total = (u) => String(Math.round(n * Number(u) * 100) / 100);
      if (this.unitCost !== null) this.cost = total(this.unitCost);
      if (this.unitSell !== null) this.sell = total(this.unitSell);
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("materialSheet", materialSheet);
});

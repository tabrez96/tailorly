// S12: a minutes timer that is not announced, and polling of the Right now cards.
function duration(minutes) {
  // Same output as core.formats.format_duration.
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) return `${h}h ${m}m`;
  return h ? `${h}h` : `${m}m`;
}

function minuteTimer() {
  return {
    text: "",
    left: "",
    over: false,
    percent: 0,
    t: null,
    init() {
      const d = this.$el.dataset;
      this.base = Number(d.base);
      this.started = Date.parse(d.started);
      this.estimate = Number(d.estimate);
      this.offset = Date.parse(d.serverNow) - Date.now(); // server clock minus phone clock
      this.tick();
      this.t = setInterval(() => this.tick(), 15000); // a new minute shows within 15 s
    },
    destroy() {
      clearInterval(this.t);
    },
    tick() {
      const elapsed = Math.floor(
        (Date.now() + this.offset - this.started) / 1000,
      );
      const m = Math.floor((this.base + Math.max(0, elapsed)) / 60);
      this.text = duration(m);
      this.over = m > this.estimate;
      this.left = this.over
        ? `${duration(m - this.estimate)} over`
        : `${duration(this.estimate - m)} left`;
      this.percent =
        this.estimate > 0
          ? Math.min(100, Math.floor((m * 100) / this.estimate))
          : 100;
    },
  };
}

function livePoll(url, every) {
  return {
    t: null,
    init() {
      this.t = setInterval(() => {
        if (document.visibilityState !== "visible" || !this.$el.isConnected)
          return;
        htmx.ajax("GET", url, { target: "#right-now", swap: "outerHTML" });
      }, every);
    },
    destroy() {
      clearInterval(this.t);
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("minuteTimer", minuteTimer);
  Alpine.data("livePoll", livePoll);
});

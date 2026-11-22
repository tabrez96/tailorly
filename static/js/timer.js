// S08 timer: counts from the server's started_at, so it is right after sleep or a slow tab.
function timerText(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const pad = (n) => String(n).padStart(2, "0");
  return `${h}:${pad(m)}:${pad(s % 60)}`;
}

function spokenTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  const part = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
  if (h && m) return `${part(h, "hour")} ${part(m, "minute")}`;
  return h ? part(h, "hour") : part(m, "minute");
}

function workTimer() {
  return {
    text: "",
    spoken: "",
    minute: null,
    t: null,
    base: 0,
    started: null,
    offset: 0,
    init() {
      const d = this.$el.dataset;
      this.base = Number(d.base);
      this.started = d.started ? Date.parse(d.started) : null;
      this.offset = Date.parse(d.serverNow) - Date.now(); // server clock minus phone clock
      // Start the minute at its first value so a swap doesn't announce it.
      this.minute = Math.floor(this.seconds() / 60);
      this.tick();
      if (this.started !== null) this.t = setInterval(() => this.tick(), 1000);
      this.onVisible = () => {
        if (document.visibilityState === "visible") this.tick();
      };
      document.addEventListener("visibilitychange", this.onVisible);
    },
    destroy() {
      clearInterval(this.t);
      document.removeEventListener("visibilitychange", this.onVisible);
    },
    seconds() {
      if (this.started === null) return this.base;
      return (
        this.base +
        Math.max(
          0,
          Math.floor((Date.now() + this.offset - this.started) / 1000),
        )
      );
    },
    tick() {
      const s = this.seconds();
      this.text = timerText(s);
      const m = Math.floor(s / 60);
      if (m !== this.minute) {
        this.minute = m;
        this.spoken = `Timer ${spokenTime(m)}`;
      }
    },
  };
}

function offlineBanner() {
  return {
    offline: !navigator.onLine,
    init() {
      this.on = () => (this.offline = false);
      this.off = () => (this.offline = true);
      addEventListener("online", this.on);
      addEventListener("offline", this.off);
    },
    destroy() {
      removeEventListener("online", this.on);
      removeEventListener("offline", this.off);
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("workTimer", workTimer);
  Alpine.data("offlineBanner", offlineBanner);
});

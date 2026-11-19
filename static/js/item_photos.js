// S20 photos: preview, upload each one (staged on the draft), retry on failure.
function csrfHeaders() {
  const h = JSON.parse(
    document.body.getAttribute("hx-headers:inherited") || "{}",
  );
  return { "X-CSRFToken": h["X-CSRFToken"] };
}

const MAX_BYTES = 20 * 1024 * 1024;

function itemPhotos() {
  return {
    tiles: [],
    max: 3,
    url: "",
    name: "",
    status: "",
    error: "",
    uid: 0,
    init() {
      const data = JSON.parse(
        document.getElementById("item-photos-data").textContent,
      );
      Object.assign(this, { max: data.max, url: data.url, name: data.name });
      this.tiles = data.photos.map((p) => ({
        key: ++this.uid,
        id: p.id,
        src: p.thumb,
        saved: p.saved,
        status: "done",
        file: null,
      }));
    },
    alt(i) {
      return `${this.name}, photo ${i + 1} of ${this.tiles.length}`;
    },
    pick(e) {
      const files = [...e.target.files].slice(0, this.max - this.tiles.length);
      e.target.value = "";
      this.error = "";
      for (const file of files) {
        if (file.size > MAX_BYTES) {
          this.error = this.status = "Choose a photo under 20 MB.";
          continue;
        }
        this.tiles.push({
          key: ++this.uid,
          id: null,
          src: URL.createObjectURL(file),
          saved: false,
          status: "uploading",
          file,
        });
        this.upload(this.tiles.at(-1)); // the reactive proxy, not the raw object
      }
    },
    async upload(t) {
      t.status = "uploading";
      this.changed();
      const body = new FormData();
      body.append("photo", t.file);
      try {
        const r = await fetch(this.url, {
          method: "POST",
          body,
          headers: csrfHeaders(),
          credentials: "same-origin",
        });
        if (!r.ok) throw new Error(r.status);
        t.id = (await r.json()).id;
        t.status = "done";
        this.status = `Photo ${this.tiles.indexOf(t) + 1} added.`;
      } catch {
        t.status = "failed";
        this.status = "Upload failed. Tap to retry.";
      }
      this.changed();
    },
    retry(t) {
      if (t.status === "failed") this.upload(t);
    },
    changed() {
      // A late upload from a form that was swapped out must not repaint the new one.
      if (!this.$el.isConnected) return;
      const done = this.tiles.filter((t) => t.status === "done");
      this.$dispatch(
        "item-photos-busy",
        this.tiles.some((t) => t.status === "uploading"),
      );
      window.dispatchEvent(
        new CustomEvent("item-picture", {
          detail: { src: done[0]?.src ?? "", count: done.length },
        }),
      );
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("itemPhotos", itemPhotos);
});

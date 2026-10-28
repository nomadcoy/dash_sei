const CACHE = "gestao-vista-static-v2";
const MAX_TRIES = 8;

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "precache") {
    event.waitUntil(precache().catch(() => {}));
  }
});

async function precache() {
  const cache = await caches.open(CACHE);
  let html = "";
  try {
    const r = await buscarComRetry("/");
    if (r && r.ok) html = await r.text();
  } catch (e) {}
  const urls = new Set();
  const re = /\/static\/[^"'\s)]+/g;
  let m;
  while ((m = re.exec(html)) !== null) urls.add(m[0]);
  await Promise.all(
    [...urls].map(async (u) => {
      try {
        const hit = await cache.match(u, { ignoreSearch: true });
        if (hit) return;
        const r = await buscarComRetry(u);
        if (r && r.ok && r.type === "basic") {
          await cache.put(u, r.clone());
        }
      } catch (e) {}
    })
  );
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  let url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith("/static/")) return;

  event.respondWith(handle(req));
});

async function handle(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req, { ignoreSearch: true });
  if (hit) return hit;

  const resp = await buscarComRetry(req);
  if (resp && resp.ok && resp.type === "basic") {
    try {
      await cache.put(req, resp.clone());
    } catch (e) {}
  }
  return resp;
}

function dormir(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function buscarComRetry(req) {
  let ultimo;
  for (let i = 0; i < MAX_TRIES; i++) {
    try {
      const r = await fetch(req, { cache: "reload" });
      if (r && r.ok) return r;
      ultimo = r;
    } catch (e) {
      ultimo = e;
    }
    await dormir(150 * (i + 1));
  }
  if (ultimo instanceof Response) return ultimo;
  throw ultimo || new Error("falha ao buscar " + req.url);
}

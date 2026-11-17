// Ludoteca privata: serve i giochi da R2 al loro indirizzo <gioco>.ludoteca-digitale.com.
// Davanti c'è Cloudflare Access (email e codice), quindi qui arriva solo chi è ammesso.
// I file stanno nel contenitore R2 come <gioco>/<percorso>; elenco.json dice quali giochi ci sono.
// Un sottodominio che non è in elenco (la ludoteca, Ghouls su Pages) passa oltre, al suo sito.

const TIPI = {
  html: "text/html; charset=utf-8", js: "text/javascript", mjs: "text/javascript", css: "text/css",
  json: "application/json", wasm: "application/wasm", pck: "application/octet-stream", png: "image/png",
  jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", svg: "image/svg+xml", ico: "image/x-icon",
  ogg: "audio/ogg", mp3: "audio/mpeg", wav: "audio/wav", woff2: "font/woff2", ttf: "font/ttf", txt: "text/plain",
};
let elenco = null, letto = 0;

async function giochi(env) {
  if (!elenco || Date.now() - letto > 60000) {
    const o = await env.GIOCHI.get("elenco.json");
    elenco = o ? await o.json() : {};
    letto = Date.now();
  }
  return elenco;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const gioco = url.hostname.split(".")[0];
    const lista = await giochi(env);
    if (!lista[gioco]) return fetch(req); // non è un gioco su R2: va al suo sito
    if (req.method !== "GET" && req.method !== "HEAD") return new Response("Metodo non ammesso", {status: 405});
    let p = decodeURIComponent(url.pathname);
    if (p.endsWith("/")) p += "index.html";
    let o = await env.GIOCHI.get(gioco + p, {onlyIf: req.headers, range: req.headers});
    if (!o && !p.split("/").pop().includes(".")) {
      o = await env.GIOCHI.get(gioco + p + "/index.html");
      if (o) return Response.redirect(url.origin + url.pathname + "/", 301);
    }
    if (!o) return new Response("Non trovato", {status: 404});
    const h = new Headers();
    o.writeHttpMetadata(h);
    h.set("etag", o.httpEtag);
    const est = p.split(".").pop().toLowerCase();
    if (!h.get("content-type")) h.set("content-type", TIPI[est] || "application/octet-stream");
    h.set("cache-control", est === "html" ? "no-cache" : "public, max-age=300");
    if (!("body" in o)) return new Response(null, {status: 304, headers: h});
    if (o.range) {
      const r = o.range, inizio = r.offset ?? 0, lun = r.length ?? (o.size - inizio);
      h.set("content-range", `bytes ${inizio}-${inizio + lun - 1}/${o.size}`);
      return new Response(req.method === "HEAD" ? null : o.body, {status: 206, headers: h});
    }
    return new Response(req.method === "HEAD" ? null : o.body, {headers: h});
  },
};

#!/usr/bin/env python3
"""Pubblica i giochi sulla ludoteca privata usando Cloudflare R2 e un Worker, senza segreti nei loro repository.

Ogni gioco si costruisce da solo e lascia su GitHub il pacchetto del sito (artefatto «github-pages», tenuto un
giorno). Questo script, che gira nella ludoteca ogni due ore:
1. si assicura che esistano il contenitore R2, il Worker (cloudflare/worker.js) e il DNS *.<dominio>;
2. legge elenco.json dal contenitore (gioco -> commit pubblicato e file);
3. per ogni gioco con un pacchetto più nuovo carica i file in <gioco>/..., toglie quelli che non ci sono più
   e aggiorna elenco.json. Il gioco si apre da https://<gioco>.<dominio>/, dietro Cloudflare Access.

Perché R2 e non un progetto Pages per gioco: il piano gratuito di Pages ha al massimo 100 progetti per account
e file di 25 MB al massimo; R2 non ha nessuno dei due limiti.

Un gioco che non è ancora su R2 e non ha un pacchetto recente viene fatto ricostruire (il suo workflow di
pubblicazione, avviato a mano): al giro dopo il pacchetto c'è e viene caricato. Al massimo RICOSTRUZIONI per giro.

Variabili: LUDOTECA_TOKEN (GitHub, tutti i repository: Contents in lettura, Actions in lettura e scrittura), CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID.
MAX_GIOCHI: quanti giochi al massimo per giro (30). Se manca qualcosa non fa nulla.
"""
import io, json, mimetypes, os, subprocess, sys, tarfile, tempfile, shutil, time, zipfile
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, QUI)
os.environ.setdefault("LUDOTECA_DOMINIO", json.load(open(os.path.join(RADICE, "cloudflare.json"))).get("dominio", ""))
import pubblica_cloudflare as pc  # noqa: E402

GH = os.environ.get("LUDOTECA_TOKEN", "")
MAX = int(os.environ.get("MAX_GIOCHI") or 30)
RICOSTRUZIONI = int(os.environ.get("RICOSTRUZIONI") or 20)
BUCKET = "ludoteca-giochi"
WORKER = "ludoteca-giochi"
NON_GIOCHI = {"tannoiser2.github.io", "presenza", "gurps", "smoothieware", "cinebook-ai", "tabelle_materiali", "html_converter"}
TIPI = {".wasm": "application/wasm", ".pck": "application/octet-stream", ".js": "text/javascript",
        ".html": "text/html; charset=utf-8", ".json": "application/json", ".webp": "image/webp"}


def gh(url, raw=False, dati=None):
    req = urllib.request.Request(url if url.startswith("http") else "https://api.github.com" + url,
                                 data=json.dumps(dati).encode() if dati is not None else None,
                                 method="POST" if dati is not None else "GET",
                                 headers={"Authorization": "Bearer " + GH, "Accept": "application/vnd.github+json",
                                          "User-Agent": "ludoteca"})
    with urllib.request.urlopen(req, timeout=300) as r:
        corpo = r.read()
        return corpo if raw else (json.loads(corpo) if corpo else None)


def ricostruisci(repo):
    """Avvia il workflow che pubblica il gioco (quello che carica l'artefatto github-pages). True se avviato."""
    for w in gh(f"/repos/{repo['full_name']}/actions/workflows").get("workflows", []):
        if w.get("state") != "active":
            continue
        testo = gh(f"/repos/{repo['full_name']}/contents/{w['path']}").get("content", "")
        import base64
        y = base64.b64decode(testo).decode("utf-8", "replace")
        if "upload-pages-artifact" in y and "workflow_dispatch" in y:
            gh(f"/repos/{repo['full_name']}/actions/workflows/{w['id']}/dispatches", dati={"ref": repo.get("default_branch", "main")})
            return True
    return False


def wrangler(*args):
    r = subprocess.run(["npx", "--yes", "wrangler@3", *args], cwd=RADICE, capture_output=True, env=dict(os.environ, CI="1"))
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")


def metti(chiave, file, tipo):
    err = ""
    for tentativo in range(3):
        rc, _, err = wrangler("r2", "object", "put", f"{BUCKET}/{chiave}", "--file", file, "--content-type", tipo, "--remote")
        if rc == 0:
            return
        time.sleep(3 * (tentativo + 1))
    raise RuntimeError(f"caricamento di {chiave} fallito: {err[-300:]}")


def togli(chiave):
    wrangler("r2", "object", "delete", f"{BUCKET}/{chiave}", "--remote")


def leggi_elenco():
    rc, out, err = wrangler("r2", "object", "get", f"{BUCKET}/elenco.json", "--pipe", "--remote")
    if rc != 0:
        e = err.lower()
        if "not exist" in e or "not found" in e or "404" in e or "10007" in e:
            return {}
        pc.esci("Non riesco a leggere elenco.json da R2: " + err[-300:])
    try:
        return json.loads(out or b"{}")
    except ValueError:
        return {}


def scrivi_elenco(elenco):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(elenco, f, ensure_ascii=False)
    f.close()
    metti("elenco.json", f.name, "application/json")
    os.unlink(f.name)


def prepara():
    """Contenitore R2, Worker con la rotta *.<dominio>/* e record DNS jolly: crea quello che manca."""
    if not pc.cf("GET", f"/accounts/{pc.CONTO}/r2/buckets/{BUCKET}", ok404=True):
        pc.avviso("R2: creo il contenitore " + BUCKET)
        pc.cf("POST", f"/accounts/{pc.CONTO}/r2/buckets", {"name": BUCKET})
    conf = os.path.join(RADICE, "cloudflare", "wrangler.toml")
    with open(conf, "w") as f:
        f.write(f'''name = "{WORKER}"
main = "worker.js"
compatibility_date = "2024-09-23"
workers_dev = false
routes = [{{ pattern = "*.{pc.DOMINIO}/*", zone_name = "{pc.DOMINIO}" }}]

[[r2_buckets]]
binding = "GIOCHI"
bucket_name = "{BUCKET}"
''')
    rc, _, err = wrangler("deploy", "--config", conf)
    if rc != 0:
        pc.esci("Pubblicazione del Worker fallita: " + err[-500:])
    zid = pc.cf("GET", f"/zones?name={pc.DOMINIO}")["result"][0]["id"]
    if not pc.cf("GET", f"/zones/{zid}/dns_records?name=*.{pc.DOMINIO}")["result"]:
        pc.avviso("DNS: creo *." + pc.DOMINIO)
        pc.cf("POST", f"/zones/{zid}/dns_records", {"type": "CNAME", "name": "*", "content": pc.DOMINIO, "proxied": True, "ttl": 1})


def slug(nome):
    return "".join(c if c.isalnum() else "-" for c in nome.lower()).strip("-")


def pubblica(nome, art, sha, vecchio):
    s = slug(nome)
    lavoro = tempfile.mkdtemp()
    try:
        z = zipfile.ZipFile(io.BytesIO(gh(art["archive_download_url"], raw=True)))
        with z.open("artifact.tar") as t, tarfile.open(fileobj=t) as tar:
            tar.extractall(lavoro, filter="data")
        file = []
        for radice, _, nomi in os.walk(lavoro):
            for n in nomi:
                file.append(os.path.relpath(os.path.join(radice, n), lavoro).replace(os.sep, "/"))

        def uno(rel):
            tipo = TIPI.get(os.path.splitext(rel)[1].lower()) or mimetypes.guess_type(rel)[0] or "application/octet-stream"
            metti(f"{s}/{rel}", os.path.join(lavoro, rel), tipo)
        # index.html per ultimo: chi apre il gioco durante il caricamento trova ancora la versione vecchia intera
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(uno, [f for f in file if f != "index.html"]))
        if "index.html" in file:
            uno("index.html")
        for f in set((vecchio or {}).get("file", [])) - set(file):
            togli(f"{s}/{f}")
        return {"repo": nome, "commit": sha, "file": sorted(file), "quando": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    finally:
        shutil.rmtree(lavoro, ignore_errors=True)


def main():
    if not (GH and pc.TOKEN and pc.CONTO and pc.DOMINIO):
        pc.avviso("Giochi su Cloudflare: mancano LUDOTECA_TOKEN o le chiavi Cloudflare, salto.")
        return
    prepara()
    elenco = leggi_elenco()
    repos, pagina = [], 1
    while True:
        r = gh(f"/user/repos?affiliation=owner&per_page=100&page={pagina}")
        repos += r
        if len(r) < 100:
            break
        pagina += 1
    fatti, errori, saltati, ricostruiti = [], [], 0, []
    for r in sorted(repos, key=lambda x: x.get("pushed_at") or "", reverse=True):
        nome = r["name"]
        if r.get("fork") or r.get("archived") or nome.lower() in NON_GIOCHI:
            continue
        try:
            a = gh(f"/repos/{r['full_name']}/actions/artifacts?name=github-pages&per_page=1")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                pc.esci("Il token LUDOTECA_TOKEN non può leggere le Actions dei giochi: aggiungigli il permesso "
                        "Actions in sola lettura.")
            continue
        art = next((x for x in a.get("artifacts", []) if not x.get("expired")), None)
        if not art:
            if slug(nome) not in elenco and a.get("artifacts") and len(ricostruiti) < RICOSTRUZIONI:
                try:
                    if ricostruisci(r):
                        ricostruiti.append(nome)
                except urllib.error.HTTPError as e:
                    errori.append(f"{nome}: ricostruzione non avviata (HTTP {e.code}: serve Actions in scrittura nel token)")
            continue
        sha = (art.get("workflow_run") or {}).get("head_sha") or str(art["id"])
        s = slug(nome)
        if elenco.get(s, {}).get("commit") == sha:
            saltati += 1
            continue
        if len(fatti) >= MAX:
            continue
        try:
            elenco[s] = pubblica(nome, art, sha, elenco.get(s))
            fatti.append(nome)
            scrivi_elenco(elenco)  # dopo ogni gioco: se il giro si interrompe, quelli fatti restano
        except Exception as e:  # un gioco che non va non ferma gli altri
            errori.append(f"{nome}: {type(e).__name__}: {str(e)[:300]}")
    pc.avviso(f"Giochi su Cloudflare: {len(fatti)} pubblicati ({', '.join(fatti) or 'nessuno'}), "
              f"{saltati} già aggiornati, {len(elenco)} in tutto"
              + (f"; ricostruzione avviata per {', '.join(ricostruiti)} (saranno caricati al prossimo giro)" if ricostruiti else "") + ".")
    for e in errori:
        print("::warning::" + e)


if __name__ == "__main__":
    main()

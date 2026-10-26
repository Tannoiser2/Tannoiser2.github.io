#!/usr/bin/env python3
"""Pubblica una cartella su Cloudflare Pages, dietro il dominio privato della ludoteca.

Uso: python3 pubblica_cloudflare.py CARTELLA PROGETTO SOTTODOMINIO
  CARTELLA     la cartella del sito già costruito (es. build/web)
  PROGETTO     il nome del progetto Cloudflare Pages (minuscole, numeri e trattini)
  SOTTODOMINIO "ghouls" per ghouls.<dominio>, oppure "@" per il dominio principale

Variabili d'ambiente: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, LUDOTECA_DOMINIO.
Se manca una delle tre non fa nulla ed esce senza errore: il gioco resta su GitHub Pages.

Cosa fa, ogni volta (le operazioni già fatte vengono saltate):
1. crea il progetto Pages, se non c'è;
2. aggiunge un piccolo «middleware» che rimanda chi apre l'indirizzo *.pages.dev al dominio
   privato, così nessuno aggira la richiesta di accesso;
3. carica il sito con wrangler;
4. collega il sottodominio al progetto e crea il record DNS.
La protezione con email e codice (Cloudflare Access) copre tutto *.<dominio> e la configura la
ludoteca con strumenti/accesso_cloudflare.py.
"""
import json, os, shutil, subprocess, sys, tempfile, urllib.request, urllib.error

TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CONTO = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
DOMINIO = os.environ.get("LUDOTECA_DOMINIO", "").strip().lower()
API = "https://api.cloudflare.com/client/v4"


def avviso(msg):
    """Stampa il messaggio anche come annotazione di GitHub Actions (visibile nel riepilogo)."""
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"):
        print("::notice::" + msg.replace("\n", " "))


def esci(msg):
    if os.environ.get("GITHUB_ACTIONS"):
        print("::error::" + msg.replace("\n", " "))
    raise SystemExit(msg)


def cf(metodo, percorso, dati=None, ok404=False):
    req = urllib.request.Request(API + percorso, method=metodo,
                                 data=json.dumps(dati).encode() if dati is not None else None,
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")
        if ok404 and e.code == 404:
            return None
        esci(f"Cloudflare {metodo} {percorso}: HTTP {e.code} {corpo[:800]}")


MIDDLEWARE = """// Chi arriva dall'indirizzo *.pages.dev viene rimandato al dominio privato (protetto da Access).
export async function onRequest(ctx) {
  const url = new URL(ctx.request.url);
  if (url.hostname.endsWith(".pages.dev")) {
    url.hostname = "%s";
    url.port = "";
    return Response.redirect(url.toString(), 301);
  }
  return ctx.next();
}
"""


def main(cartella, progetto, sotto):
    if not (TOKEN and CONTO and DOMINIO):
        print("Cloudflare: mancano CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID o LUDOTECA_DOMINIO, salto.")
        return
    host = DOMINIO if sotto == "@" else f"{sotto}.{DOMINIO}"

    # 0. sicurezza: niente pubblicazione se il dominio non è ancora protetto da Access
    protetti = set()
    for a in cf("GET", f"/accounts/{CONTO}/access/apps")["result"]:
        protetti.update(d.lower() for d in (a.get("self_hosted_domains") or []))
        protetti.update((d.get("uri") or "").lower() for d in (a.get("destinations") or []))
        protetti.add((a.get("domain") or "").lower())
    if host not in protetti and ("*." + DOMINIO) not in protetti:
        esci(f"Cloudflare: {host} non è ancora protetto da Access (protetti: {sorted(protetti)}). Fai girare prima la "
                         "ludoteca (Actions → Pubblica la ludoteca → Run workflow), poi riprova.")

    # 1. progetto
    p = cf("GET", f"/accounts/{CONTO}/pages/projects/{progetto}", ok404=True)
    if not p:
        avviso(f"Cloudflare: creo il progetto {progetto}")
        p = cf("POST", f"/accounts/{CONTO}/pages/projects", {"name": progetto, "production_branch": "main"})
    sottodominio_pages = p["result"].get("subdomain") or f"{progetto}.pages.dev"

    # 2-3. middleware e caricamento (wrangler cerca la cartella functions/ nella cartella da cui parte)
    lavoro = tempfile.mkdtemp()
    os.makedirs(os.path.join(lavoro, "functions"))
    with open(os.path.join(lavoro, "functions", "_middleware.js"), "w") as f:
        f.write(MIDDLEWARE % host)
    sito = os.path.abspath(cartella)
    r = subprocess.run(["npx", "--yes", "wrangler@3", "pages", "deploy", sito, "--project-name", progetto,
                    "--branch", "main", "--commit-dirty=true"], cwd=lavoro, check=True,
                   env=dict(os.environ, CI="1"), capture_output=True, text=True)
    print(r.stdout[-4000:], r.stderr[-4000:])
    if r.returncode:
        esci("wrangler: " + (r.stderr or r.stdout)[-800:])
    shutil.rmtree(lavoro, ignore_errors=True)

    # 4. dominio del progetto e DNS
    domini = [d["name"] for d in cf("GET", f"/accounts/{CONTO}/pages/projects/{progetto}/domains")["result"]]
    if host not in domini:
        avviso(f"Cloudflare: collego {host}")
        cf("POST", f"/accounts/{CONTO}/pages/projects/{progetto}/domains", {"name": host})
    zone = cf("GET", f"/zones?name={DOMINIO}")["result"]
    if not zone:
        esci(f"Cloudflare: il dominio {DOMINIO} non è in questo account")
    zid = zone[0]["id"]
    record = cf("GET", f"/zones/{zid}/dns_records?name={host}")["result"]
    if not record:
        avviso(f"Cloudflare: creo il record DNS {host} → {sottodominio_pages}")
        cf("POST", f"/zones/{zid}/dns_records",
           {"type": "CNAME", "name": host, "content": sottodominio_pages, "proxied": True, "ttl": 1})
    avviso(f"Pubblicato su https://{host}/")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])

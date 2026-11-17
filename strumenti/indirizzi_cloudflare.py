#!/usr/bin/env python3
"""Copia del sito per la ludoteca privata: il pulsante Gioca porta alla versione del gioco su Cloudflare
(https://<repository in minuscolo>.<dominio>/) per ogni gioco che vi è già pubblicato; gli altri restano su GitHub.

Uso: python3 strumenti/indirizzi_cloudflare.py SITO COPIA
"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("LUDOTECA_DOMINIO", json.load(open(os.path.join(QUI, "cloudflare.json"))).get("dominio", ""))
import pubblica_cloudflare as pc  # noqa: E402


def main(sito, copia):
    shutil.rmtree(copia, ignore_errors=True)
    shutil.copytree(sito, copia)
    if not (pc.TOKEN and pc.CONTO and pc.DOMINIO):
        return
    progetti, pagina = set(), 1
    while True:
        r = pc.cf("GET", f"/accounts/{pc.CONTO}/pages/projects?per_page=50&page={pagina}")["result"]
        progetti |= {p["name"] for p in r}
        if len(r) < 50:
            break
        pagina += 1
    # più i giochi serviti da R2 (strumenti/giochi_r2.py), che sono in elenco.json
    import subprocess
    r = subprocess.run(["npx", "--yes", "wrangler@3", "r2", "object", "get", "ludoteca-giochi/elenco.json", "--pipe", "--remote"],
                       capture_output=True, env=dict(os.environ, CI="1"))
    if r.returncode == 0:
        try:
            progetti |= set(json.loads(r.stdout or b"{}").keys())
        except ValueError:
            pass
    f = os.path.join(copia, "giochi.json")
    giochi = json.load(open(f, encoding="utf-8"))
    n = 0
    for g in giochi:
        p = "".join(c if c.isalnum() else "-" for c in g["repo"].lower()).strip("-")
        if p in progetti:
            g["gioca"] = f"https://{p}.{pc.DOMINIO}/"
            n += 1
    json.dump(giochi, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    pc.avviso(f"Ludoteca privata: {n} giochi su {len(giochi)} si aprono dalla versione su Cloudflare.")


if __name__ == "__main__":
    main(*sys.argv[1:3])

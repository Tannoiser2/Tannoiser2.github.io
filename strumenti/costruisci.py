#!/usr/bin/env python3
"""Costruisce la ludoteca: cerca fra i repository di Tannoiser2 quelli che hanno la cartella
`ludoteca/` (scheda.json + copertina.webp) e scrive in OUT il sito pronto da pubblicare:
index.html e il resto del repository, giochi.json e le copertine in img/.

Uso: python3 strumenti/costruisci.py OUT
Variabili: GITHUB_TOKEN (facoltativa, alza il limite di richieste), LUDOTECA_UTENTE.
"""
import json, os, shutil, sys, urllib.request, urllib.error

UTENTE = os.environ.get("LUDOTECA_UTENTE", "Tannoiser2")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scarica(url, api=False):
    req = urllib.request.Request(url, headers={"User-Agent": "ludoteca"})
    if api:
        req.add_header("Accept", "application/vnd.github+json")
    if TOKEN and api:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def repository():
    tutti, pagina = [], 1
    while True:
        dati = json.loads(scarica(f"https://api.github.com/users/{UTENTE}/repos?per_page=100&page={pagina}", api=True))
        if not dati:
            return tutti
        tutti += dati
        pagina += 1


def main(out):
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(QUI, out, ignore=shutil.ignore_patterns(".git", ".github", "strumenti", os.path.basename(out)))
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    giochi = []
    for r in repository():
        if r.get("archived") or r.get("fork") or r.get("private"):
            continue
        nome, ramo = r["name"], r.get("default_branch") or "main"
        base = f"https://raw.githubusercontent.com/{UTENTE}/{nome}/{ramo}/ludoteca/"
        grezza = scarica(base + "scheda.json")
        if grezza is None:
            continue
        try:
            s = json.loads(grezza.decode("utf-8-sig"))
        except ValueError as e:
            print(f"!! {nome}: scheda.json non valida ({e}), salto")
            continue
        if s.get("nascosto"):
            continue
        img = ""
        cop = scarica(base + "copertina.webp")
        if cop:
            img = f"img/{nome}.webp"
            with open(os.path.join(out, img), "wb") as f:
                f.write(cop)
        giochi.append({
            "repo": nome,
            "titolo": s.get("titolo") or nome,
            "sottotitolo": s.get("sottotitolo", ""),
            "descrizione": s.get("descrizione", ""),
            "online": bool(s.get("online", False)),
            "sezione": "originale" if s.get("sezione") == "originale" else "conversione",
            "ordine": s.get("ordine", 1000),
            "gioca": s.get("gioca") or f"https://{UTENTE.lower()}.github.io/{nome}/",
            "codice": r["html_url"],
            "img": img,
        })
        print(f"ok {nome}: {giochi[-1]['titolo']}" + ("" if img else " (senza copertina)"))
    if not giochi:
        sys.exit("Nessun gioco trovato: non pubblico una ludoteca vuota.")
    giochi.sort(key=lambda g: (g["ordine"], g["titolo"].lower()))
    with open(os.path.join(out, "giochi.json"), "w", encoding="utf-8") as f:
        json.dump(giochi, f, ensure_ascii=False, indent=1)
    print(f"{len(giochi)} giochi")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")

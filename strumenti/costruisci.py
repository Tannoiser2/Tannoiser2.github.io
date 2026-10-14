#!/usr/bin/env python3
"""Costruisce la ludoteca: cerca fra i repository di Tannoiser2 quelli che hanno la cartella
`ludoteca/` (scheda.json + copertina.webp) e scrive in OUT il sito pronto da pubblicare:
index.html e il resto del repository, giochi.json e le copertine in img/.

Uso: python3 strumenti/costruisci.py OUT
Variabili: GITHUB_TOKEN (facoltativa, alza il limite di richieste), LUDOTECA_UTENTE.
"""
import json, os, shutil, sys, time, traceback, urllib.request, urllib.error

UTENTE = os.environ.get("LUDOTECA_UTENTE", "Tannoiser2")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scarica(url, api=False):
    for tentativo in range(3):
        try:
            return _scarica(url, api)
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
            ultimo = e
        except urllib.error.URLError as e:
            ultimo = e
        time.sleep(3 * (tentativo + 1))
    raise ultimo


def _scarica(url, api=False):
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


def misure_webp(dati):
    """Larghezza e altezza di un'immagine WebP (o None), senza librerie esterne."""
    try:
        if dati[:4] != b"RIFF" or dati[8:12] != b"WEBP":
            return None
        tipo = dati[12:16]
        if tipo == b"VP8X":
            return 1 + int.from_bytes(dati[24:27], "little"), 1 + int.from_bytes(dati[27:30], "little")
        if tipo == b"VP8 ":
            return int.from_bytes(dati[26:28], "little") & 0x3FFF, int.from_bytes(dati[28:30], "little") & 0x3FFF
        if tipo == b"VP8L":
            b = int.from_bytes(dati[21:25], "little")
            return 1 + (b & 0x3FFF), 1 + ((b >> 14) & 0x3FFF)
    except Exception:
        pass
    return None


def repository():
    tutti, pagina = [], 1
    while True:
        dati = json.loads(scarica(f"https://api.github.com/users/{UTENTE}/repos?per_page=100&page={pagina}", api=True))
        if not dati:
            return tutti
        tutti += dati
        pagina += 1


def generi_predefiniti():
    try:
        with open(os.path.join(QUI, "generi.json"), encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


GENERI = {}


def main(out):
    GENERI.update(generi_predefiniti())
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(QUI, out, ignore=shutil.ignore_patterns(".git", ".github", "strumenti", "copertine", "generi.json", os.path.basename(out)))
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    giochi = []
    for r in repository():
        if r.get("archived") or r.get("fork") or r.get("private"):
            continue
        try:
            g = scheda(r, out)
        except Exception:
            print(f"!! {r.get('name')}: errore, salto questo gioco")
            traceback.print_exc()
            continue
        if g:
            giochi.append(g)
            print(f"ok {g['repo']}: {g['titolo']}" + ("" if g["img"] else " (senza copertina)"))
    if not giochi:
        sys.exit("Nessun gioco trovato: non pubblico una ludoteca vuota.")
    giochi.sort(key=lambda g: (g["ordine"], g["titolo"].lower()))
    with open(os.path.join(out, "giochi.json"), "w", encoding="utf-8") as f:
        json.dump(giochi, f, ensure_ascii=False, indent=1)
    print(f"{len(giochi)} giochi")


def numero(v, predefinito=1000):
    try:
        return float(v)
    except (TypeError, ValueError):
        return predefinito


def scheda(r, out):
    if True:  # (blocco mantenuto per leggibilità del diff)
        nome, ramo = r["name"], r.get("default_branch") or "main"
        base = f"https://raw.githubusercontent.com/{UTENTE}/{nome}/{ramo}/ludoteca/"
        grezza = scarica(base + "scheda.json")
        if grezza is None:
            return None
        try:
            s = json.loads(grezza.decode("utf-8-sig"))
        except ValueError as e:
            print(f"!! {nome}: scheda.json non valida ({e}), salto")
            return None
        if s.get("nascosto"):
            return None
        img = ""
        # una copertina in copertine/<repository>.webp di questo repository ha la precedenza
        locale = os.path.join(QUI, "copertine", nome + ".webp")
        cop = open(locale, "rb").read() if os.path.exists(locale) else scarica(base + "copertina.webp")
        misure = misure_webp(cop) if cop else None
        if cop:
            img = f"img/{nome}.webp"
            with open(os.path.join(out, img), "wb") as f:
                f.write(cop)
        generi = s.get("generi") if isinstance(s.get("generi"), list) else GENERI.get(nome, [])
        return {
            "repo": nome,
            "generi": [str(x) for x in generi],
            "titolo": str(s.get("titolo") or nome),
            "sottotitolo": s.get("sottotitolo", ""),
            "descrizione": s.get("descrizione", ""),
            "online": bool(s.get("online", False)),
            "sezione": "originale" if s.get("sezione") == "originale" else "conversione",
            "ordine": numero(s.get("ordine")),
            "gioca": s.get("gioca") or f"https://{UTENTE.lower()}.github.io/{nome}/",
            "codice": r["html_url"],
            "img": img,
            "w": misure[0] if misure else 0,
            "h": misure[1] if misure else 0,
        }


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")

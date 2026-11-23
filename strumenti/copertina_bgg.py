#!/usr/bin/env python3
"""Scarica da BoardGameGeek l'immagine della scatola di un gioco e la salva come copertina della ludoteca.

Uso: python3 strumenti/copertina_bgg.py REPOSITORY [ID_BGG]
  REPOSITORY  il nome del repository del gioco (la copertina diventa copertine/<REPOSITORY>.webp)
  ID_BGG      facoltativo: se manca si legge da ludoteca/scheda.json del gioco
Serve BGG_TOKEN. Lo usa il workflow «Copertina da BGG» (Actions → Run workflow).
"""
import io, json, os, re, sys, urllib.request
from PIL import Image

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("BGG_TOKEN", "")


def scarica(url, bgg=False):
    h = {"User-Agent": "ludoteca"}
    if bgg:
        h["Authorization"] = "Bearer " + TOKEN
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        return r.read()


def main(repo, bgg_id=None):
    if not bgg_id:
        s = json.loads(scarica(f"https://raw.githubusercontent.com/Tannoiser2/{repo}/main/ludoteca/scheda.json"))
        bgg_id = s.get("bgg")
    if not bgg_id:
        sys.exit(f"{repo}: nessun codice BGG nella scheda")
    xml = scarica(f"https://boardgamegeek.com/xmlapi2/thing?id={bgg_id}", bgg=True).decode("utf-8", "replace")
    m = re.search(r"<image>\s*([^<]+?)\s*</image>", xml)
    if not m:
        sys.exit(f"{repo}: BGG non ha un'immagine per il gioco {bgg_id}")
    im = Image.open(io.BytesIO(scarica(m.group(1)))).convert("RGB")
    w, h = im.size
    nw = 600 if w >= h else 480
    im = im.resize((nw, round(h * nw / w)), Image.LANCZOS)
    im.save(os.path.join(QUI, "copertine", f"{repo}.webp"), "WEBP", quality=85, method=6)
    print(f"::notice::{repo}: copertina da BGG ({m.group(1)}) salvata, {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main(*sys.argv[1:3])

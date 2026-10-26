#!/usr/bin/env python3
"""Costruisce la ludoteca: cerca fra i repository di Tannoiser2 quelli che hanno la cartella
`ludoteca/` (scheda.json + copertina.webp) e scrive in OUT il sito pronto da pubblicare:
index.html e il resto del repository, giochi.json e le copertine in img/.

Uso: python3 strumenti/costruisci.py OUT
Variabili: GITHUB_TOKEN (facoltativa, alza il limite di richieste), LUDOTECA_UTENTE.
  LUDOTECA_TOKEN: token GitHub di sola lettura che vede anche i repository privati. Con questo i giochi
  privati entrano nella ludoteca e il pulsante Gioca porta al loro indirizzo privato
  https://<repository in minuscolo>.<dominio>/ (dominio in cloudflare.json).
"""
import json, os, shutil, sys, time, traceback, urllib.request, urllib.error
import xml.etree.ElementTree as ET

UTENTE = os.environ.get("LUDOTECA_UTENTE", "Tannoiser2")
TOKEN = os.environ.get("LUDOTECA_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
PRIVATI = bool(os.environ.get("LUDOTECA_TOKEN"))
BGG_TOKEN = os.environ.get("BGG_TOKEN", "")
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
    if TOKEN and (api or (PRIVATI and "githubusercontent.com" in url)):
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
        if PRIVATI:  # anche i privati: serve il token del proprietario
            url = f"https://api.github.com/user/repos?affiliation=owner&visibility=all&per_page=100&page={pagina}"
        else:
            url = f"https://api.github.com/users/{UTENTE}/repos?per_page=100&page={pagina}"
        dati = json.loads(scarica(url, api=True))
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
BGG_ID = {}
STATO_BGG = {"msg": ""}


def leggi_json(nome):
    try:
        with open(os.path.join(QUI, nome), encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def info_bgg(ids):
    """Scarica da BoardGameGeek (XML API2, serve BGG_TOKEN) giocatori, durata, età, anno, autori, voto, peso
    e posizione in classifica. Restituisce {id: {...}}; in caso di errore un dizionario vuoto (la pagina
    mostra comunque il collegamento alla scheda BGG)."""
    out = {}
    if not BGG_TOKEN or not ids:
        if ids:
            print("BGG: nessun BGG_TOKEN, mostro solo i collegamenti")
            STATO_BGG["msg"] = "manca il segreto BGG_TOKEN"
        return out
    ids = sorted(set(ids))
    for i in range(0, len(ids), 20):
        url = "https://boardgamegeek.com/xmlapi2/thing?stats=1&id=" + ",".join(str(x) for x in ids[i:i + 20])
        dati = None
        for tentativo in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ludoteca", "Authorization": "Bearer " + BGG_TOKEN})
                with urllib.request.urlopen(req, timeout=40) as r:
                    if r.status == 202:      # BGG prepara la risposta: riprovare
                        time.sleep(4 * (tentativo + 1))
                        continue
                    dati = r.read()
                    break
            except urllib.error.HTTPError as e:
                print(f"BGG: tentativo {tentativo + 1} fallito (HTTP {e.code})")
                STATO_BGG["msg"] = f"BGG ha risposto HTTP {e.code}" + (" (token non valido o applicazione non ancora approvata)" if e.code in (401, 403) else "")
                if e.code in (401, 403):
                    return out
                time.sleep(4 * (tentativo + 1))
            except Exception as e:
                print(f"BGG: tentativo {tentativo + 1} fallito ({e})")
                STATO_BGG["msg"] = f"errore di rete verso BGG ({type(e).__name__})"
                time.sleep(4 * (tentativo + 1))
        if not dati:
            continue
        try:
            radice = ET.fromstring(dati)
        except ET.ParseError:
            continue
        for it in radice.findall("item"):
            def val(tag, d=""):
                n = it.find(tag)
                return n.get("value", d) if n is not None else d
            nomi = [n.get("value") for n in it.findall("name") if n.get("type") == "primary"]
            link = lambda t: [l.get("value") for l in it.findall("link") if l.get("type") == t]
            st = it.find("statistics/ratings")
            def sv(tag):
                n = st.find(tag) if st is not None else None
                try:
                    return round(float(n.get("value")), 2) if n is not None else 0
                except (TypeError, ValueError):
                    return 0
            rank = ""
            if st is not None:
                for rk in st.findall("ranks/rank"):
                    if rk.get("name") == "boardgame" and rk.get("value", "").isdigit():
                        rank = int(rk.get("value"))
            num = lambda x: int(x) if str(x).isdigit() else 0
            out[int(it.get("id"))] = {
                "nome": nomi[0] if nomi else "", "anno": num(val("yearpublished")),
                "min": num(val("minplayers")), "max": num(val("maxplayers")),
                "tmin": num(val("minplaytime")), "tmax": num(val("maxplaytime")), "eta": num(val("minage")),
                "autori": link("boardgamedesigner")[:3], "editori": link("boardgamepublisher")[:2],
                "categorie": link("boardgamecategory"), "meccaniche": link("boardgamemechanic")[:6],
                "voto": sv("average"), "peso": sv("averageweight"), "classifica": rank,
            }
        time.sleep(2)
    print(f"BGG: informazioni per {len(out)} giochi")
    if out:
        STATO_BGG["msg"] = ""
    return out


def main(out):
    GENERI.update(generi_predefiniti())
    BGG_ID.update(leggi_json("bgg.json"))
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(QUI, out, ignore=shutil.ignore_patterns(".git", ".github", "strumenti", "copertine", "generi.json", "bgg.json", "cloudflare.json", os.path.basename(out)))
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    giochi = []
    for r in repository():
        if r.get("archived") or r.get("fork") or (r.get("private") and not PRIVATI):
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
    info = info_bgg([g["bgg"]["id"] for g in giochi if g.get("bgg")])
    for g in giochi:
        if g.get("bgg") and g["bgg"]["id"] in info:
            g["bgg"].update(info[g["bgg"]["id"]])
    with open(os.path.join(out, "giochi.json"), "w", encoding="utf-8") as f:
        json.dump(giochi, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "stato.json"), "w", encoding="utf-8") as f:
        json.dump({"costruita": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                   "bgg_giochi": len(info), "bgg_token": bool(BGG_TOKEN), "bgg_problema": STATO_BGG["msg"]},
                  f, ensure_ascii=False, indent=1)
    print(f"{len(giochi)} giochi")


def dominio_privato():
    try:
        with open(os.path.join(QUI, "cloudflare.json"), encoding="utf-8") as f:
            return (json.load(f).get("dominio") or "").strip().lower()
    except (OSError, ValueError):
        return ""


def progetto_cloudflare(nome):
    """Nome del progetto Cloudflare Pages e del sottodominio di un gioco: il repository in minuscolo."""
    return "".join(c if c.isalnum() else "-" for c in nome.lower()).strip("-")


def indirizzo(nome, privato):
    d = dominio_privato()
    if privato and d:
        return f"https://{progetto_cloudflare(nome)}.{d}/"
    return f"https://{UTENTE.lower()}.github.io/{nome}/"


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
        try:
            bid = int(s.get("bgg") or BGG_ID.get(nome) or 0)
        except (TypeError, ValueError):
            bid = 0
        generi = s.get("generi") if isinstance(s.get("generi"), list) else GENERI.get(nome, [])
        return {
            "repo": nome,
            "generi": [str(x) for x in generi],
            "bgg": {"id": bid, "url": f"https://boardgamegeek.com/boardgame/{bid}"} if bid else None,
            "titolo": str(s.get("titolo") or nome),
            "sottotitolo": s.get("sottotitolo", ""),
            "descrizione": s.get("descrizione", ""),
            "online": bool(s.get("online", False)),
            "sezione": "originale" if s.get("sezione") == "originale" else "conversione",
            "ordine": numero(s.get("ordine")),
            "gioca": s.get("gioca") or indirizzo(nome, r.get("private")),
            "codice": r["html_url"],
            "img": img,
            "w": misure[0] if misure else 0,
            "h": misure[1] if misure else 0,
        }


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")

#!/usr/bin/env python3
"""Pulizia notturna del database dei giochi online (Firebase, progetto flammerouge-f8669).

Cancella le stanze online create da più di GIORNI giorni (predefinito 30) in tutti i giochi:
  <gioco>/rooms/<codice>, <gioco>/stanze/<codice> e la radice storica rooms/<codice> (Flamme Rouge, Blood Master).
Non tocca campagne, partite, salvataggi, librerie o altro.
L'età si legge dal campo created (o created_at, o info/created) della stanza; una stanza senza data non si tocca.

Variabili d'ambiente:
  FIREBASE_SERVICE_ACCOUNT  il JSON della chiave di servizio (se manca non fa nulla)
  PULIZIA_GIORNI            dopo quanti giorni una stanza è vecchia (30)
  PULIZIA_PROVA             "1" = elenca soltanto, senza cancellare
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

DB = "https://flammerouge-f8669-default-rtdb.europe-west1.firebasedatabase.app"
GIORNI = float(os.environ.get("PULIZIA_GIORNI") or 30)
PROVA = os.environ.get("PULIZIA_PROVA", "") == "1"
RAMI = ("rooms", "stanze")


def avviso(msg):
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"):
        print("::notice::" + msg)


def token():
    from google.oauth2 import service_account
    import google.auth.transport.requests
    info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
    cred = service_account.Credentials.from_service_account_info(info, scopes=[
        "https://www.googleapis.com/auth/firebase.database", "https://www.googleapis.com/auth/userinfo.email"])
    cred.refresh(google.auth.transport.requests.Request())
    return cred.token


TOK = None


def req(metodo, percorso, query=None):
    q = dict(query or {}); q["access_token"] = TOK
    url = f"{DB}/{percorso}.json?" + urllib.parse.urlencode(q)
    for tentativo in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method=metodo), timeout=60) as r:
                return json.loads(r.read() or b"null")
        except (urllib.error.URLError, TimeoutError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                raise
            time.sleep(2 * (tentativo + 1))
    raise SystemExit(f"Firebase non risponde: {metodo} {percorso}")


def figli(percorso):
    d = req("GET", percorso, {"shallow": "true"})
    return list(d.keys()) if isinstance(d, dict) else []


def eta_ms(stanza_path):
    for campo in ("created", "created_at", "info/created"):
        v = req("GET", f"{stanza_path}/{campo}")
        if isinstance(v, (int, float)):
            return v * 1000 if v < 1e11 else v  # created_at può essere in secondi
    return None


def main():
    global TOK
    if not os.environ.get("FIREBASE_SERVICE_ACCOUNT"):
        avviso("Pulizia: manca il segreto FIREBASE_SERVICE_ACCOUNT, salto.")
        return
    TOK = token()
    limite = time.time() * 1000 - GIORNI * 86400 * 1000
    contenitori = ["rooms"]  # radice storica
    for radice in figli(""):
        if radice == "rooms":
            continue
        for ramo in RAMI:
            if ramo in figli(radice):
                contenitori.append(f"{radice}/{ramo}")
    tot_vecchie, tot_tenute, senza_data, per_gioco = 0, 0, 0, {}
    for cont in contenitori:
        for codice in figli(cont):
            p = f"{cont}/{codice}"
            t = eta_ms(p)
            if t is None:
                senza_data += 1
                continue
            if t < limite:
                tot_vecchie += 1
                per_gioco[cont] = per_gioco.get(cont, 0) + 1
                if not PROVA:
                    req("DELETE", p)
            else:
                tot_tenute += 1
    dettaglio = ", ".join(f"{k.split('/')[0]} {v}" for k, v in sorted(per_gioco.items())) or "nessuna"
    verbo = "da cancellare (prova, nulla cancellato)" if PROVA else "cancellate"
    avviso(f"Pulizia: {tot_vecchie} stanze più vecchie di {GIORNI:g} giorni {verbo}: {dettaglio}. "
           f"Restano {tot_tenute} stanze recenti; {senza_data} senza data, non toccate.")


if __name__ == "__main__":
    main()

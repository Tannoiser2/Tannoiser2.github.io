#!/usr/bin/env python3
"""Configura Cloudflare Access: la ludoteca e tutti i giochi (<dominio> e *.<dominio>) si aprono solo
dopo aver inserito la propria email e il codice che arriva per posta, e solo per le email in
cloudflare.json → "accessi".

Uso: python3 strumenti/accesso_cloudflare.py
Variabili d'ambiente: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID (se mancano non fa nulla).
Ogni volta riallinea l'elenco delle email: per aggiungere o togliere qualcuno basta modificare
cloudflare.json e la ludoteca si ripubblica da sola.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pubblica_cloudflare import cf, TOKEN, CONTO, avviso  # noqa: E402

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOME_APP = "Ludoteca"
NOME_IDP = "Codice via email"


def main():
    with open(os.path.join(QUI, "cloudflare.json"), encoding="utf-8") as f:
        conf = json.load(f)
    dominio = (conf.get("dominio") or "").strip().lower()
    email = sorted({e.strip().lower() for e in conf.get("accessi", []) if "@" in e})
    if not (TOKEN and CONTO and dominio and email):
        avviso("Access: mancano chiavi Cloudflare, dominio o email, salto.")
        return

    # accesso con codice via email (One-time PIN)
    idp = [i for i in cf("GET", f"/accounts/{CONTO}/access/identity_providers")["result"] if i["type"] == "onetimepin"]
    if idp:
        idp_id = idp[0]["id"]
    else:
        avviso("Access: attivo l'accesso con codice via email")
        idp_id = cf("POST", f"/accounts/{CONTO}/access/identity_providers",
                    {"name": NOME_IDP, "type": "onetimepin", "config": {}})["result"]["id"]

    criterio = {"name": "Persone ammesse", "decision": "allow", "precedence": 1,
                "include": [{"email": {"email": e}} for e in email]}
    app = {"name": NOME_APP, "type": "self_hosted", "domain": dominio,
           "self_hosted_domains": [dominio, "*." + dominio],
           "session_duration": "730h", "allowed_idps": [idp_id], "auto_redirect_to_identity": True,
           "app_launcher_visible": False}

    esistenti = [a for a in cf("GET", f"/accounts/{CONTO}/access/apps")["result"] if a.get("name") == NOME_APP]
    if esistenti:
        aid = esistenti[0]["id"]
        cf("PUT", f"/accounts/{CONTO}/access/apps/{aid}", app)
    else:
        avviso("Access: creo l'applicazione Ludoteca")
        aid = cf("POST", f"/accounts/{CONTO}/access/apps", app)["result"]["id"]

    politiche = cf("GET", f"/accounts/{CONTO}/access/apps/{aid}/policies")["result"]
    if politiche:
        cf("PUT", f"/accounts/{CONTO}/access/apps/{aid}/policies/{politiche[0]['id']}", criterio)
        for p in politiche[1:]:
            cf("DELETE", f"/accounts/{CONTO}/access/apps/{aid}/policies/{p['id']}")
    else:
        cf("POST", f"/accounts/{CONTO}/access/apps/{aid}/policies", criterio)
    avviso(f"Access: {dominio} e *.{dominio} aperti a {len(email)} email")


if __name__ == "__main__":
    main()

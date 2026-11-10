# La ludoteca digitale

Pagina con tutti i giochi da tavolo convertiti in digitale, con copertina, link al gioco su GitHub Pages
e indicazione di quelli giocabili online con gli amici: https://tannoiser2.github.io/

## Si aggiorna da sola

L'elenco non sta in questo repository: ogni gioco si presenta da sé con una cartella `ludoteca/`
nel **proprio** repository. Ogni notte (e a ogni modifica qui, o lanciandola a mano da
Actions → *Pubblica la ludoteca* → *Run workflow*) un'azione cerca fra i repository pubblici di
Tannoiser2 quelli che hanno la cartella e ripubblica la pagina.

Per aggiungere un gioco nuovo, nel suo repository:

```
ludoteca/
  scheda.json      ← i dati della scheda
  copertina.webp   ← la copertina della scatola, nelle sue proporzioni (quadrata, verticale
                     o orizzontale: la pagina non la taglia), larga 480–600 pixel
  .gdignore        ← file vuoto: Godot non importa la cartella (solo progetti Godot)
```

`scheda.json`:

```json
{
  "titolo": "Snow Tails",
  "sottotitolo": "corsa di slitte",
  "descrizione": "Mute di husky su piste a tessere, con curve, crepacci e alberelli.",
  "online": true,
  "sezione": "conversione",
  "ordine": 20
}
```

- `online`: `true` se il gioco ha le stanze per giocare online con gli amici.
- `sezione`: `"conversione"` oppure `"originale"`.
- `ordine`: posizione nell'elenco (numeri più bassi prima; i giochi attuali vanno da 10 a 190; fra due posizioni vicine si può usare un numero intermedio, come Primal 175, Kingsburg 178, Churchill 179 e Burning Banners 180).
- `generi` (facoltativo): elenco di generi per i filtri della pagina, es. `["COIN", "Wargame"]`.
  Se manca vale quello scritto in `generi.json` di questo repository (chiave = nome del repository).
- Facoltativi: `"gioca"` per un indirizzo diverso da `https://tannoiser2.github.io/<repository>/`,
  `"nascosto": true` per togliere il gioco dalla pagina senza cancellare la cartella.

Per togliere un gioco basta cancellare la cartella (o renderlo privato / archiviarlo).
Lo script che costruisce il sito è `strumenti/costruisci.py`.

## Filtri per genere

La pagina mostra una riga di filtri «Genere» (COIN, Wargame, Fantasy, Storici, Sport e corse…) che si
combinano con Online/Su un dispositivo. I generi stanno in `generi.json` (uno o più per gioco); un gioco può
anche dichiararli da sé con il campo `generi` della propria `scheda.json`, che ha la precedenza.

## Collegamento a BoardGameGeek

Ogni gioco ha il pulsante **BGG** verso la sua scheda su BoardGameGeek. I codici BGG stanno in `bgg.json`
(chiave = nome del repository); un gioco può indicarlo da sé con il campo `"bgg": <numero>` nella propria
`scheda.json`.

Con il segreto **`BGG_TOKEN`** (Settings → Secrets and variables → Actions → *New repository secret*) la
costruzione notturna scarica anche giocatori, durata, peso, voto medio, autori e anno dalla XML API di BGG e li
mostra sulle schede. Il token si ottiene registrando un'applicazione non commerciale su
https://boardgamegeek.com/applications (dopo l'approvazione: *Tokens* → crea). Senza token la pagina mostra solo
il collegamento.

## Ludoteca privata (Cloudflare)

La ludoteca e i giochi si stanno spostando su un dominio privato: chi apre la pagina inserisce la propria
email, riceve un codice e entra solo se la sua email è nell'elenco `accessi` di `cloudflare.json`.

- `cloudflare.json`: il dominio e le email ammesse. Per aggiungere un amico basta scrivere qui la sua email.
- Segreti di questo repository: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` e `LUDOTECA_TOKEN` (token GitHub di
  sola lettura che vede anche i repository privati).
- `strumenti/accesso_cloudflare.py` configura la protezione (Cloudflare Access) per il dominio e tutti i suoi
  sottodomini; `strumenti/pubblica_cloudflare.py` pubblica un sito su Cloudflare Pages e non lo mette online sul
  dominio se la protezione non c'è ancora.
- Un gioco con il repository privato si apre da `https://<repository in minuscolo>.<dominio>/`.

## Gioco online: regole di Firebase

Le regole del database (progetto `flammerouge-f8669`) stanno in `firebase/database.rules.json`, con un titolo per ogni
gioco: è il file da incollare in Firebase → Realtime Database → Regole.

**Un gioco nuovo non ha bisogno di una sezione propria** se usa una di queste strutture, coperte dalla regola comune
(`$game`, in fondo al file); la radice è il nome del gioco in minuscolo, senza spazi:

| Struttura | Percorsi | Esempi |
|---|---|---|
| Stanze con mosse | `<gioco>/rooms/<CODICE di 4>`: `host`, `created`, `status`, `open`, `cfg`, `game`, `seats/<n>` (`uid`, `name`), `acts/<n>` (`s` + facoltativi `k` fino a 12 caratteri e `v`) | Village, Titans, Paleo |
| Stanze con registro | come sopra, più `members/<uid>: true` e `log/<n>` (`d`) | Arcs, Hegemony, Il Duello |
| Turni simultanei | `turns/<round>/<posto>` e `plans/<round>/<posto>` | HEAT |
| Salvataggi personali | `<gioco>/salvataggi/<uid>`: `stato` (testo) | Arcs, Barbarian Kings |
| Campagne e partite | `<gioco>/campagne/<CODICE di 6>` o `partite/<CODICE di 6>`, con `json` o `dati` (testo) | ISS Vanguard, Omaha Beach |

Solo un gioco con una struttura diversa (altri campi nella stanza, altri rami) ha bisogno di una sezione sua.

Prima di caricare regole cambiate si possono provare con `node firebase/prove.mjs firebase/database.rules.json nuova`
(un gioco nuovo con le tre strutture) e `... controllo` (le sezioni esistenti): un piccolo valutatore delle regole
(`firebase/valuta.mjs`) rifà le scritture vere delle librerie online.

## Pulizia delle stanze online

Ogni notte la costruzione della ludoteca cancella dal database le stanze online create da più di 30 giorni
(`strumenti/pulizia_firebase.py`), in tutti i giochi: `<gioco>/rooms`, `<gioco>/stanze` e la radice storica `rooms`.
Campagne, partite e salvataggi non vengono toccati. Serve il segreto `FIREBASE_SERVICE_ACCOUNT` (la chiave di servizio
di Firebase, in JSON). `PULIZIA_GIORNI` nel workflow cambia il periodo; con `PULIZIA_PROVA: "1"` elenca soltanto.

## La pagina della ludoteca

In alto c'è una barra fissa con la **ricerca** (titolo, autore, genere; il tasto `/` ci porta il cursore), i filtri
per **modo** (online o su un dispositivo), **genere** e **numero di giocatori** (dai dati BGG: i giochi senza
dati restano sempre visibili) e l'**ordinamento** (ordine della ludoteca, aggiunti di recente, titolo, voto BGG,
peso, anno). Sotto, la fila **Aggiunti di recente** con gli ultimi otto giochi, dalla data di creazione del
repository (campo `aggiunto` di `giochi.json`). Filtri, ordinamento e vista restano salvati nel browser.

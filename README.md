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

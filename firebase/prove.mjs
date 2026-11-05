// Prove delle regole: le scritture vere delle librerie online dei giochi, prese dal loro codice.
import { write, read, carica } from './valuta.mjs';
import fs from 'fs';

const [fileRegole, modo] = process.argv.slice(2);
const rules = carica(fileRegole);
let fallite = 0, fatte = 0;
function prova(nome, atteso, rules, statoRef, uid, ops) {
  const r = write(rules, statoRef.s, uid, ops);
  fatte++;
  const ok = r.ok === atteso;
  if (!ok) { fallite++; console.log(`  NO  ${nome}: atteso ${atteso ? 'permesso' : 'negato'}, ottenuto ${r.ok ? 'permesso' : 'negato'} ${r.perche || ''}`); }
  if (r.ok && atteso) statoRef.s = r.stato;
}
const H = 'host-uid', G = 'ospite-uid', X = 'estraneo-uid';

// Variante A: libreria standard (net.gd): seats + acts, mosse con o senza "k"
function standard(root, mossa) {
  const st = { s: null }; const R = `${root}/rooms/ABCD`;
  prova('A crea stanza', true, rules, st, H, [
    { path: `${R}/host`, value: H }, { path: `${R}/created`, value: { '.sv': 'timestamp' } }, { path: `${R}/status`, value: 'lobby' },
    { path: `${R}/open`, value: [0, 1, 2] }, { path: `${R}/seats/0`, value: { uid: H, name: 'Stefano' } }]);
  prova('A ospite entra', true, rules, st, G, [{ path: `${R}/seats/1`, value: { uid: G, name: 'Marco' } }]);
  prova('A ospite ruba il posto 0', false, rules, st, G, [{ path: `${R}/seats/0`, value: { uid: G, name: 'Marco' } }]);
  prova('A host avvia', true, rules, st, H, [{ path: `${R}/game`, value: { seed: 42, n: 3 } }, { path: `${R}/status`, value: 'playing' }]);
  prova('A ospite cambia lo stato', false, rules, st, G, [{ path: `${R}/status`, value: 'x' }]);
  prova('A mossa ospite', true, rules, st, G, [{ path: `${R}/acts/0`, value: { s: 1, ...mossa } }]);
  prova('A mossa ripetuta (stesso numero)', false, rules, st, G, [{ path: `${R}/acts/0`, value: { s: 1, ...mossa } }]);
  prova('A mossa a nome di un altro', false, rules, st, G, [{ path: `${R}/acts/1`, value: { s: 0, ...mossa } }]);
  prova('A mossa host per l\'IA', true, rules, st, H, [{ path: `${R}/acts/1`, value: { s: 2, ...mossa } }]);
  prova('A ospite segnala presenza', true, rules, st, G, [{ path: `${R}/seats/1/seen`, value: { '.sv': 'timestamp' } }, { path: `${R}/seats/1/away`, value: false }]);
  prova('A campo sconosciuto', false, rules, st, H, [{ path: `${R}/pippo`, value: 1 }]);
  prova('A estraneo cancella', false, rules, st, X, [{ path: R, value: null }]);
  prova('A host cancella', true, rules, st, H, [{ path: R, value: null }]);
}
// Variante B: members + log + salvataggi (Arcs, Il Duello, Hegemony, Barbarian Kings, ...)
function membri(root) {
  const st = { s: null }; const R = `${root}/rooms/WXYZ`;
  prova('B crea stanza', true, rules, st, H, [
    { path: `${R}/host`, value: H }, { path: `${R}/created`, value: { '.sv': 'timestamp' } }, { path: `${R}/status`, value: 'lobby' },
    { path: `${R}/cfg`, value: JSON.stringify({ giocatori: 3, ia: [2] }) }, { path: `${R}/seats/0`, value: { uid: H, name: 'Stefano' } }, { path: `${R}/members/${H}`, value: true }]);
  prova('B ospite membro', true, rules, st, G, [{ path: `${R}/members/${G}`, value: true }]);
  prova('B ospite si fa membro per un altro', false, rules, st, G, [{ path: `${R}/members/${X}`, value: true }]);
  prova('B ospite posto', true, rules, st, G, [{ path: `${R}/seats/1`, value: { uid: G, name: 'Marco' } }]);
  prova('B host avvia', true, rules, st, H, [{ path: `${R}/game`, value: JSON.stringify({ seed: 7 }) }, { path: `${R}/status`, value: 'playing' }]);
  prova('B registro ospite', true, rules, st, G, [{ path: `${R}/log/0`, value: { d: JSON.stringify({ a: 'mossa' }) } }]);
  prova('B registro estraneo', false, rules, st, X, [{ path: `${R}/log/1`, value: { d: 'x' } }]);
  prova('B registro riscritto', false, rules, st, H, [{ path: `${R}/log/0`, value: { d: 'altro' } }]);
  prova('B presenza', true, rules, st, G, [{ path: `${R}/seats/1/seen`, value: { '.sv': 'timestamp' } }]);
  prova('B salvataggio proprio', true, rules, st, G, [{ path: `${root}/salvataggi/${G}`, value: { stato: '{"x":1}', quando: { '.sv': 'timestamp' } } }]);
  prova('B salvataggio altrui', false, rules, st, X, [{ path: `${root}/salvataggi/${G}`, value: { stato: '{}' } }]);
  if (!read(rules, st.s, G, `${root}/salvataggi/${G}`) || read(rules, st.s, X, `${root}/salvataggi/${G}`)) { fallite++; console.log('  NO  B lettura salvataggi'); } fatte++;
  prova('B host cancella', true, rules, st, H, [{ path: R, value: null }]);
}
// Variante C: campagne e partite salvate con codice di 6 caratteri
function campagne(root, ramo, corpo) {
  const st = { s: null };
  prova(`C ${ramo} salva`, true, rules, st, G, [{ path: `${root}/${ramo}/K7P2QM`, value: corpo }]);
  prova(`C ${ramo} codice corto`, false, rules, st, G, [{ path: `${root}/${ramo}/K7P`, value: corpo }]);
  prova(`C ${ramo} senza accesso`, false, rules, st, null, [{ path: `${root}/${ramo}/K7P2QM`, value: corpo }]);
}

if (modo === 'nuova') {
  // un gioco nuovo, senza sezione propria: deve bastare la regola comune
  for (const [nome, m] of [['con k', { k: 'd', v: '{"x":1}' }], ['senza k', { v: 3 }], ['con k "c"', { k: 'c', v: 5 }]]) { console.log(`variante A (${nome})`); standard('giocononuovo', m); }
  console.log('variante B'); membri('giocononuovo');
  console.log('variante C');
  campagne('giocononuovo', 'campagne', { json: '{}', aggiornata: 1, nome: 'Prova', camp: 1, uid: G });
  campagne('giocononuovo', 'campagne', { nome: 'Prova', turno: 3, aggiornato: 1, uid: G, dati: '{}' });
  campagne('giocononuovo', 'partite', { json: '{}', aggiornata: 1, nome: 'Prova', turno: 2, uid: G });
} else {
  // controllo del valutatore: le sezioni già pubblicate devono dare gli stessi esiti
  console.log('village (regola generica attuale, con k)'); standard('village', { k: 'd', v: '{}' });
  console.log('paleo (sezione propria, senza k)'); standard('paleo', { v: 3 });
  console.log('arcs (sezione propria)'); membri('arcs');
  console.log('issvanguard'); campagne('issvanguard', 'campagne', { json: '{}', aggiornata: 1, nome: 'P', camp: 1, uid: G });
}
console.log(`${fatte - fallite}/${fatte} prove riuscite`);
process.exit(fallite ? 1 : 0);

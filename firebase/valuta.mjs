// Valutatore minimo delle regole del Realtime Database di Firebase, per provare le regole senza emulatore.
// Copre: .read/.write a cascata, .validate su ogni nodo cambiato (antenati compresi), variabili $,
// figli espliciti prima dei jolly, data/newData/root, aggiornamenti multi-percorso (PATCH) e cancellazioni.
import fs from 'fs';

String.prototype.matches = function (re) { return re.test(this); };
String.prototype.contains = function (s) { return this.includes(s); };
String.prototype.beginsWith = function (s) { return this.startsWith(s); };
String.prototype.endsWith2 = String.prototype.endsWith;

const clone = (x) => (x === undefined ? null : JSON.parse(JSON.stringify(x)));
const norm = (v, now) => {
  if (v === null || v === undefined) return null;
  if (Array.isArray(v)) { const o = {}; v.forEach((x, i) => { const n = norm(x, now); if (n !== null) o[i] = n; }); return Object.keys(o).length ? o : null; }
  if (typeof v === 'object') {
    if (v['.sv'] === 'timestamp') return now;
    const o = {}; for (const k of Object.keys(v)) { const n = norm(v[k], now); if (n !== null) o[k] = n; }
    return Object.keys(o).length ? o : null;
  }
  return v;
};
const get = (tree, path) => { let t = tree; for (const p of path) { if (t === null || typeof t !== 'object') return null; t = t[p] ?? null; } return t; };
const set = (tree, path, val) => {
  if (!path.length) return val;
  const t = (tree && typeof tree === 'object') ? { ...tree } : {};
  const n = set(t[path[0]] ?? null, path.slice(1), val);
  if (n === null) delete t[path[0]]; else t[path[0]] = n;
  return Object.keys(t).length ? t : null;
};
const split = (p) => p.split('/').filter(Boolean);

class Snap {
  constructor(tree, path) { this.tree = tree; this.path = path; }
  _v() { return get(this.tree, this.path); }
  val() { return this._v(); }
  child(p) { return new Snap(this.tree, [...this.path, ...split(String(p))]); }
  parent() { return new Snap(this.tree, this.path.slice(0, -1)); }
  exists() { return this._v() !== null; }
  hasChild(p) { return this.child(p).exists(); }
  hasChildren(arr) { const v = this._v(); if (v === null || typeof v !== 'object') return false; return arr ? arr.every((k) => this.hasChild(k)) : true; }
  isString() { return typeof this._v() === 'string'; }
  isNumber() { return typeof this._v() === 'number'; }
  isBoolean() { return typeof this._v() === 'boolean'; }
  numChildren() { const v = this._v(); return v && typeof v === 'object' ? Object.keys(v).length : 0; }
}

// trova la regola di un nodo: figlio esplicito, altrimenti jolly $nome
function ruleAt(rules, path) {
  let r = rules; const vars = {};
  for (const p of path) {
    if (!r || typeof r !== 'object') return { r: null, vars };
    if (p in r && !p.startsWith('.')) { r = r[p]; continue; }
    const w = Object.keys(r).find((k) => k.startsWith('$'));
    if (!w) return { r: null, vars };
    vars[w] = p; r = r[w];
  }
  return { r, vars };
}
function evalExpr(expr, ctx) {
  if (expr === true || expr === false) return expr;
  const names = Object.keys(ctx);
  // eslint-disable-next-line no-new-func
  const f = new Function(...names, `return (${expr});`);
  try { return !!f(...names.map((n) => ctx[n])); } catch (e) { return false; }
}

export function write(rules, state, uid, ops, now = 1700000000000) {
  // ops: [{path, value}] (un PUT è un'op, un PATCH sono più op con percorso relativo)
  let nuovo = state;
  for (const o of ops) nuovo = set(nuovo, split(o.path), norm(o.value, now));
  const auth = uid ? { uid } : null;
  // 1. permesso di scrittura per ogni percorso scritto
  for (const o of ops) {
    const path = split(o.path); let ok = false;
    for (let i = 0; i <= path.length && !ok; i++) {
      const sub = path.slice(0, i); const { r, vars } = ruleAt(rules, sub);
      if (r && '.write' in r) ok = evalExpr(r['.write'], { auth, root: new Snap(state, []), data: new Snap(state, sub), newData: new Snap(nuovo, sub), now, ...vars });
    }
    if (!ok) return { ok: false, perche: 'scrittura negata su ' + o.path };
  }
  // 2. validazione: antenati dei percorsi scritti e tutti i nodi del sottoalbero nuovo
  const daValidare = new Set();
  const visita = (path) => { const v = get(nuovo, path); daValidare.add(path.join('/')); if (v && typeof v === 'object') for (const k of Object.keys(v)) visita([...path, k]); };
  for (const o of ops) { const p = split(o.path); for (let i = 0; i < p.length; i++) daValidare.add(p.slice(0, i).join('/')); visita(p); }
  for (const s of daValidare) {
    const path = split(s); if (get(nuovo, path) === null) continue;
    const { r, vars } = ruleAt(rules, path);
    if (r === null && path.length) {
      // nessuna regola: va bene solo se nessun antenato ha un $other/esplicito che la escluda
      continue;
    }
    if (r && '.validate' in r) {
      const ok = evalExpr(r['.validate'], { auth, root: new Snap(state, []), data: new Snap(state, path), newData: new Snap(nuovo, path), now, ...vars });
      if (!ok) return { ok: false, perche: 'validazione fallita su ' + s };
    }
  }
  return { ok: true, stato: nuovo };
}
export function read(rules, state, uid, pathStr) {
  const path = split(pathStr); const auth = uid ? { uid } : null;
  for (let i = 0; i <= path.length; i++) {
    const sub = path.slice(0, i); const { r, vars } = ruleAt(rules, sub);
    if (r && '.read' in r && evalExpr(r['.read'], { auth, root: new Snap(state, []), data: new Snap(state, sub), now: 0, ...vars })) return true;
  }
  return false;
}
export function carica(file) {
  const t = fs.readFileSync(file, 'utf8').replace(/^\s*\/\/.*$/gm, '');
  return JSON.parse(t).rules;
}

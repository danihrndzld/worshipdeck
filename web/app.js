'use strict';
/* worshipdeck SPA: hash routes, one `S` state (sessionStorage) and `T` for
   transient UI state. Every screen is a function that returns HTML. */

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const TODO_TEXT = '[pegar texto';
const READINGS = [
  { id: 'bienvenida', name: 'Lectura de bienvenida', where: 'Antes del 1.er bloque de alabanza', block: 1, short: 'Bienvenida' },
  { id: 'tema', name: 'Lectura del tema', where: 'Antes del 2.º bloque de alabanza', block: 2, short: 'Tema' },
  { id: 'segundo', name: 'Segundo tiempo bíblico', where: 'Antes del 3.er bloque de alabanza', block: 3, short: 'Segundo tiempo' },
  { id: 'ofrenda', name: 'Ofrenda y bendición', where: 'Al final, después de la prédica', block: 0, short: 'Ofrenda y bendición' },
];

// ------------------------------------------------------------------ state

function blank() {
  const d = new Date();
  d.setDate(d.getDate() + ((7 - d.getDay()) % 7));
  return {
    mode: 'img', text: '', image: null, parsed: false,
    lines: null, pend: [], serverPend: [], flyerItems: [], items: [], orderSig: null, uid: 1,
    intro: { op: 'clone_range', start: 1, end: 3 },
    dateLabel: `Domingo ${d.getDate()} de ${MONTHS[d.getMonth()]}`,
    output: `${MONTHS[d.getMonth()].toUpperCase()} ${d.getDate()}`, outputTouched: false,
    sermon: { lead: 'El tema de hoy', title: '', passage: '', items: [] },
    readings: Object.fromEntries(READINGS.map((r) => [r.id, { ref: '', text: '', items: [] }])),
  };
}
let S = blank();
try { Object.assign(S, JSON.parse(sessionStorage.getItem('worshipdeck')) || {}); } catch { /* private mode */ }
function save() {
  try { sessionStorage.setItem('worshipdeck', JSON.stringify(S)); } catch { /* full or blocked: the week lives in memory */ }
}
const T = { lyrics: {}, match: {}, songs: {} };

// ------------------------------------------------------------------ helpers

async function api(path, body, opts = {}) {
  const init = { method: opts.method || (body === undefined ? 'GET' : 'POST') };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) { init.body = JSON.stringify(body); init.headers = { 'Content-Type': 'application/json' }; }
  const res = await fetch(path, init);
  if (!res.ok) {
    let msg = '';
    try { msg = (await res.json()).error; } catch { /* not JSON */ }
    const e = new Error(msg || `El servidor respondió ${res.status}`);
    e.status = res.status;
    throw e;
  }
  return opts.blob ? res.blob() : res.json();
}

function saveBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 60000);
}

const timers = {};
function debounce(key, ms, fn) { clearTimeout(timers[key]); timers[key] = setTimeout(fn, ms); }
function patch(id, html) { const el = document.getElementById(id); if (el) el.innerHTML = html; }
const strip = (it) => {
  const out = Object.fromEntries(Object.entries(it).filter(([k]) => k[0] !== '_'));
  if (it._text && it._text.trim()) out.chunks = it._text.trim().split(/\n\s*\n/).map((c) => c.split('\n'));
  return out;
};
const todayISO = () => new Date().toLocaleDateString('sv');
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const P = {
  back: '<path d="M15 18l-6-6 6-6"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5h.01"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  lines: '<path d="M4 6h16M4 12h16M4 18h10"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  file: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/>',
  chev: '<path d="M6 9l6 6 6-6"/>', eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>', down: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  warn: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>', spin: '<path d="M21 12a9 9 0 1 1-9-9"/>',
};
const ic = (n, s = 18, sw = 1.8, attrs = '') =>
  `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${attrs}>${P[n]}</svg>`;
const spinner = ic('spin', 18, 2.2, 'class="spin"');
const errBox = (msg) => (msg ? `<p class="err" role="alert">${esc(msg)}</p>` : '');

const STEPS = ['Flyer', 'Corregir', 'Orden', 'Prédica', 'Lecturas', 'Descarga'];
function steps(n, cls, suffix = '') {
  return `<div class="${cls}" style="padding: 18px 20px 0; display: flex; flex-direction: column; gap: 10px">
    <div style="display: flex; justify-content: space-between; font: 500 13px/1 var(--g); color: #52525B"><span>Paso ${n} de 6${suffix}</span><span>${esc(S.dateLabel)}</span></div>
    <ol style="list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 4px" aria-hidden="true">
      ${STEPS.map((l, i) => `<li style="display: flex; flex-direction: column; gap: 6px"><div style="height: 4px; border-radius: 2px; background: ${i < n ? '#18181B' : '#DADAD5'}"></div><span class="steplabel" style="font: ${i === n - 1 ? 600 : 500} 12px/1 var(--g); color: ${i === n - 1 ? '#18181B' : '#5F5F66'}">${l}</span></li>`).join('')}
    </ol>
  </div>`;
}
const back = (href, label) => `<a class="back" href="${href}">${ic('back', 16, 2)}${esc(label)}</a>`;

// What one spec item looks like in the lists (badge + heading).
function look(it) {
  const v = it._v || {};
  if (it.op === 'hymn') return { type: 'Himno', cls: 'b-himno', heading: `${it.himno} · ${v.title || ''}`, short: `Himno ${it.himno}` };
  if (it.op === 'song') return { type: 'Canción', cls: 'b-cancion', heading: v.title || it.title_white || '', short: v.title || it.title_white || '' };
  if (it.op === 'scripture') {
    const ref = `${it.book} ${it.range}`;
    const r = READINGS.find((x) => x.id === it._role);
    return r ? { type: 'Lectura', cls: 'b-pasaje', heading: `${r.short} · ${ref}`, short: ref } : { type: 'Pasaje', cls: 'b-pasaje', heading: ref, short: ref };
  }
  if (it.op === 'sermon') return { type: 'Prédica', cls: 'b-muted', heading: it.title, short: 'Prédica' };
  return { type: 'Intro', cls: 'b-muted', heading: 'Logo y declaración de propósito', short: 'Intro' };
}
const matchLabel = (v) => (v.kind === 'himno' ? `${v.label} · ${v.title}` : v.kind === 'cancion' ? `Canción · ${v.title}` : `Pasaje · ${v.title}`);

function sectionLabels(sections) {
  const n = {};
  const total = {};
  sections.forEach((s) => { total[s.kind] = (total[s.kind] || 0) + 1; });
  const name = { verse: 'Estrofa', chorus: 'Coro', bridge: 'Puente' };
  return sections.map((s) => {
    n[s.kind] = (n[s.kind] || 0) + 1;
    return (name[s.kind] || 'Estrofa') + (total[s.kind] > 1 && s.kind !== 'chorus' ? ` ${n[s.kind]}` : ''); // the chorus repeats, it is not a new one
  });
}
function lyricsBox(sections, label) {
  const labels = sectionLabels(sections);
  return `<div class="appear" style="max-height: 260px; overflow-y: auto; padding: 14px 16px; border-radius: 12px; background: #F6F6F3; display: flex; flex-direction: column; gap: 14px" tabindex="0" aria-label="${esc(label)}">
    ${sections.map((s, i) => `<div style="display: flex; flex-direction: column; gap: 6px"><span style="font: 600 11px/1 var(--g); letter-spacing: .08em; text-transform: uppercase; color: #5F5F66">${labels[i]}</span><p style="margin: 0; font: 400 15px/1.55 var(--g); white-space: pre-line">${esc(s.lines.join('\n'))}</p></div>`).join('')}
  </div>`;
}
async function fetchLyrics(it) {
  if (it.op === 'hymn') return (await api(`/api/hymn/${it.himno}`)).sections;
  if (it.key) return (await api(`/api/song/${encodeURIComponent(it.key)}`)).sections;
  return (it.sections || []).map((s) => ({ kind: s.type, lines: s.lines }));
}

// A passage string -> scripture ops, parsed by the server (Spanish 400 when unreadable).
async function passageItems(passage, role) {
  if (!passage.trim()) return [];
  const r = await api('/api/parse', { text: '', passage });
  return r.spec.items.map((it, i) => [it, r.views[i]]).filter(([it]) => it.op === 'scripture').map(([it, v]) => {
    if (!v.todo) delete it.chunks; // the server adds the RVR1960 text at preview/build time
    return { ...it, _role: role, _todo: !!v.todo };
  });
}

// ------------------------------------------------------------------ the deck spec

const blockOf = (b) => S.items.filter((i) => !i._new && i._block === b);
function fullItems() {
  const R = S.readings;
  const items = [S.intro];
  const lastBlock = Math.max(3, ...S.items.map((i) => i._block));
  for (let b = 1; b <= lastBlock; b++) {
    const r = READINGS.find((x) => x.block === b);
    if (r) items.push(...R[r.id].items.map((it, k) => (k ? it : { ...it, _text: R[r.id].text })));
    items.push(...blockOf(b));
  }
  const sm = S.sermon;
  if (sm.title.trim()) items.push({ op: 'sermon', lead: sm.lead, title: sm.title.trim(), reference: sm.passage.trim(), _role: 'sermon' });
  items.push(...sm.items.map((it) => ({ ...it, _role: 'sermon' })));
  items.push(...R.ofrenda.items.map((it, k) => (k ? it : { ...it, _text: R.ofrenda.text })));
  return items;
}
const deckSpec = () => ({ output: `${S.output.trim() || 'culto'}.pptx`, items: fullItems().map(strip) });
const placeholders = () => S.items.filter((i) => i._new);

// ------------------------------------------------------------------ OCR in the browser

function loadScript(src) {
  return new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = ok;
    s.onerror = () => bad(new Error(`no cargó ${src}`));
    document.head.append(s);
  });
}
let worker = null;
async function tesseractLines(image, onProgress) {
  if (!window.Tesseract) await loadScript('https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js');
  const w = await window.Tesseract.createWorker('spa', 1, {
    logger: (m) => {
      if (m.status === 'recognizing text') onProgress(10 + m.progress * 60, 'Leyendo el texto');
      else if (typeof m.progress === 'number') onProgress(m.progress * 10, 'Preparando el lector de texto');
    },
  });
  worker = w;
  try {
    const { data } = await w.recognize(image);
    return data.lines
      .map((l) => ({ text: l.text.trim(), conf: Math.round(l.confidence), box: [l.bbox.x0, l.bbox.y0, l.bbox.x1, l.bbox.y1].map(Math.round) }))
      .filter((l) => l.text);
  } finally {
    w.terminate();
    if (worker === w) worker = null;
  }
}

function downscale(file) {
  return new Promise((ok, bad) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const k = Math.min(1, 1600 / Math.max(img.naturalWidth, img.naturalHeight));
      const c = document.createElement('canvas');
      c.width = Math.round(img.naturalWidth * k);
      c.height = Math.round(img.naturalHeight * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      ok(c.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); bad(new Error('imagen ilegible')); };
    img.src = url;
  });
}

function newWeek(keep) {
  S = Object.assign(blank(), keep);
  T.lyrics = {};
  T.match = {};
  T.downloaded = false;
}

let job = 0;
async function runOcr() {
  const my = ++job;
  T.ocr = { pct: 0, phase: 'Preparando el lector de texto', done: false, error: null };
  if (location.hash !== '#/ocr') location.hash = '#/ocr'; else render();
  const prog = (pct, phase) => {
    if (my !== job) return;
    T.ocr.pct = Math.max(T.ocr.pct, Math.round(pct));
    T.ocr.phase = phase;
    patch('ocr-prog', ocrProgress());
  };
  let body;
  try {
    const lines = await tesseractLines(S.image, prog);
    console.info(`worshipdeck: OCR en el navegador (tesseract.js), ${lines.length} líneas`);
    body = { image: S.image, lines, fresh: true };
  } catch (e) {
    if (my !== job) return;
    console.info('worshipdeck: tesseract.js no disponible, OCR en el servidor', e);
    body = { image: S.image };
  }
  if (my !== job) return;
  prog(75, 'Buscando coincidencias');
  try {
    const r = await api('/api/parse', body);
    if (my !== job) return;
    applyParse(r, true);
    T.ocr = { pct: 100, phase: 'Listo', done: true };
    if (!S.pend.length) location.hash = '#/listo';
    else render();
  } catch (e) {
    if (my !== job) return;
    T.ocr.error = e.message;
    render();
  }
}

function applyParse(r, fresh) {
  S.dateLabel = r.date_label;
  S.parsed = true;
  if (!S.outputTouched) S.output = r.spec.output.replace(/\.pptx$/, '');
  const [intro, ...rest] = r.spec.items;
  S.intro = intro;
  S.flyerItems = rest.map((it, i) => ({ ...it, _v: r.views[i + 1] }));
  S.serverPend = r.pendientes.map((p) => p.id);
  if (fresh) {
    S.lines = r.lines;
    S.pend = r.pendientes.map((p) => ({ id: p.id, ocr: p.text, text: p.text, conf: p.conf, matched: p.matched, crop: p.crop || null, status: 'pending', final: '' }));
  }
  save();
}

// The flyer lines with the person's corrections applied.
function correctedLines() {
  return (S.lines || []).flatMap((l) => {
    const p = S.pend.find((x) => x.id === l.id);
    if (p && p.status === 'discarded') return [];
    return p && p.status === 'confirmed' ? [{ ...l, text: p.text, conf: 100 }] : [l];
  });
}
async function reparse() {
  T.busy = true;
  T.err = null;
  render();
  try {
    applyParse(await api('/api/parse', { image: S.image || undefined, lines: correctedLines(), fresh: false }), false);
  } catch (e) {
    T.err = e.message;
  }
  T.busy = false;
  render();
}

async function refreshMatch(p) {
  const text = p.text.trim();
  if (!text) { T.match[p.id] = { empty: true }; patchPend(p); return; }
  T.match[p.id] = { loading: true };
  patchPend(p);
  try {
    const r = await api('/api/parse', { text });
    if (p.text.trim() !== text) return;
    const views = r.views.slice(1);
    T.match[p.id] = views.length ? { text, ok: true, label: views.map(matchLabel).join(' + ') } : { text, ok: false, label: 'No coincide con ningún himno, canción de la biblioteca ni pasaje.' };
  } catch (e) {
    T.match[p.id] = { ok: false, label: e.message };
  }
  patchPend(p);
}
function patchPend(p) {
  patch(`m-${p.id}`, matchHtml(p));
  const btn = document.getElementById(`c-${p.id}`);
  if (btn) btn.disabled = !p.text.trim() || T.busy;
}

// Go from the corrected flyer to the order of service. Order edits survive
// unless the flyer result itself changed.
function toOrder() {
  const ph = S.pend.filter((p) => p.status === 'confirmed' && S.serverPend.includes(p.id))
    .map((p) => ({ op: 'song', _new: true, _v: { kind: 'cancion', label: 'Canción', title: p.text.trim() } }));
  const src = [...S.flyerItems, ...ph];
  const sig = JSON.stringify(src);
  if (sig !== S.orderSig) {
    S.orderSig = sig;
    const n = Math.max(src.length, 1);
    // ponytail: the flyer has no worship sets, so the order starts as thirds; ↑/↓ move items across blocks
    S.items = src.map((it, i) => ({ ...it, _new: it._new || (it._v && it._v.missing) || undefined, _id: S.uid++, _block: 1 + Math.floor((i * 3) / n) }));
  }
  save();
  location.hash = '#/orden';
}

// ------------------------------------------------------------------ screens

function flyer() {
  const img = S.mode === 'img';
  return `${steps(1, 'wrap')}
  <main class="wrap" style="padding: 28px 20px 24px; display: flex; flex-direction: column; gap: 22px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      <h1 class="h1" tabindex="-1" style="font-size: 28px; line-height: 1.12">Sube el flyer de esta semana</h1>
      <p class="lead">Leemos la lista del culto y la buscamos en el himnario y en la biblioteca de canciones.</p>
    </div>
    <div class="seg" role="group" aria-label="Cómo quieres subir la lista">
      <button type="button" aria-pressed="${img}" data-act="mode" data-v="img">${ic('image', 16)}Imagen</button>
      <button type="button" aria-pressed="${!img}" data-act="mode" data-v="txt">${ic('lines', 16)}Texto</button>
    </div>
    ${errBox(T.err)}
    ${img ? `
    <div class="drop" style="display: flex; flex-direction: column; align-items: center; gap: 18px; padding: 36px 20px 28px; border: 1.5px dashed #C9C9C3; border-radius: 20px; background: #FFFFFF; text-align: center">
      <div style="width: 64px; height: 64px; border-radius: 18px; background: #F1F1EE; display: flex; align-items: center; justify-content: center; color: #18181B">${ic('upload', 28, 1.6)}</div>
      <div style="display: flex; flex-direction: column; gap: 6px">
        <div style="font: 600 17px/1.3 var(--g)">Foto o captura del flyer</div>
        <div class="hint">JPG o PNG</div>
      </div>
      <div class="upl" style="display: flex; flex-direction: column; gap: 10px; width: 100%; max-width: 480px">
        <input id="cam" class="file-in" type="file" accept="image/*" capture="environment" data-ch="photo">
        <label class="btn btn-primary" for="cam">${ic('camera')}Tomar foto</label>
        <input id="gal" class="file-in" type="file" accept="image/*" data-ch="photo">
        <label class="btn btn-secondary" for="gal">${ic('image')}Elegir de la galería</label>
      </div>
    </div>
    <p class="hint" style="margin: 0; text-align: center">Si el pastor mandó la lista por mensaje, usa <strong style="color: #18181B; font-weight: 600">Texto</strong> y pégala.</p>` : `
    <div style="display: flex; flex-direction: column; gap: 8px">
      <label class="label" for="lista">Lista del culto</label>
      <textarea id="lista" class="input" rows="9" data-in="text" placeholder="Una línea por elemento, por ejemplo:
Himno 83
Grande y fuerte
Salmos 23:1-6">${esc(S.text)}</textarea>
      <span class="hint">Un himno, canción o pasaje por línea, en el orden del culto.</span>
    </div>
    <button type="button" class="btn btn-primary" data-act="readText" ${T.busy ? 'disabled' : ''}>${T.busy ? `${spinner}Leyendo…` : 'Leer lista'}</button>`}
    <div style="margin-top: auto; display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 16px; background: #EDEDE9">
      ${ic('file', 20, 1.8, 'style="flex: none; color: #3F3F46"')}
      <div style="flex: 1; min-width: 0; font: 400 14px/1.4 var(--g); color: #3F3F46">¿Ya revisaste la presentación en PowerPoint?</div>
      <a href="#/letras" style="font: 600 14px/1 var(--g); white-space: nowrap; padding: 14px 0">PDF de letras</a>
    </div>
  </main>`;
}

function ocrProgress() {
  const o = T.ocr;
  const st = (doneAt, startAt) => {
    const done = o.pct >= doneAt;
    const active = !done && o.pct >= startAt;
    return { done, active, color: done || active ? '#18181B' : '#71717A' };
  };
  const list = [['Imagen subida', st(0, 0)], ['Leyendo el texto (OCR)', st(75, 0)], ['Buscando en el himnario, la biblioteca y la Biblia', st(100, 75)]];
  return `<div style="display: flex; flex-direction: column; gap: 10px">
      <div style="display: flex; justify-content: space-between; font: 500 14px/1 var(--g)"><span>${esc(o.phase)}</span><span style="font-variant-numeric: tabular-nums; color: #52525B">${o.pct} %</span></div>
      <div style="height: 8px; border-radius: 4px; background: #E2E2DD; overflow: hidden" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${o.pct}" aria-label="Progreso de lectura">
        <div class="bar" style="height: 100%; width: ${o.pct}%; background: #18181B; border-radius: 4px"></div>
      </div>
    </div>
    <ol style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px">
      ${list.map(([label, s]) => `<li style="display: flex; align-items: center; gap: 12px; min-height: 40px; font: 400 15px/1.35 var(--g); color: ${s.color}">
        ${s.done ? `<span style="width: 24px; height: 24px; border-radius: 999px; background: #18181B; color: #FFFFFF; display: inline-flex; align-items: center; justify-content: center; flex: none">${ic('check', 14, 2.6)}</span>`
    : s.active ? '<span class="pulse" style="width: 24px; height: 24px; border-radius: 999px; border: 2px solid #18181B; display: inline-flex; align-items: center; justify-content: center; flex: none"><span style="width: 8px; height: 8px; border-radius: 999px; background: #18181B"></span></span>'
      : '<span style="width: 24px; height: 24px; border-radius: 999px; border: 2px solid #CFCFC9; flex: none"></span>'}
        <span>${label}</span></li>`).join('')}
    </ol>`;
}

function ocr() {
  if (!T.ocr) {
    if (!S.parsed || !S.image) { setTimeout(() => location.replace('#/flyer')); return ''; }
    T.ocr = { pct: 100, phase: 'Listo', done: true };
  }
  const o = T.ocr;
  const n = S.flyerItems.length;
  const k = S.pend.length;
  return `${steps(1, 'wrap')}
  <main class="wrap" style="padding: 24px 20px 24px; display: flex; flex-direction: column; gap: 20px; flex: 1">
    <h1 class="h1" tabindex="-1">${o.done ? 'Flyer leído' : 'Leyendo el flyer…'}</h1>
    <div class="photo" style="height: 330px" role="img" aria-label="Foto del flyer subida">
      <img src="${S.image}" alt="">
      ${o.done || o.error ? '' : '<div class="scan" aria-hidden="true"></div>'}
    </div>
    <div id="ocr-prog" aria-live="polite" style="display: flex; flex-direction: column; gap: 20px">${ocrProgress()}</div>
    ${o.error ? `${errBox(o.error)}<button type="button" class="btn btn-primary" data-act="retryOcr">Intentar de nuevo</button>` : ''}
    ${o.done ? `<div class="appear" style="display: flex; flex-direction: column; gap: 14px; padding: 18px; border-radius: 18px; background: #FFFFFF; border: 1px solid #E3E3DF">
        <p style="margin: 0; font: 400 15px/1.5 var(--g); color: #3F3F46"><strong style="color: #18181B; font-weight: 600">${plural(n, 'elemento', 'elementos')}</strong> se ${n === 1 ? 'leyó' : 'leyeron'} bien. <strong style="color: #18181B; font-weight: 600">${plural(k, 'línea', 'líneas')}</strong> ${k === 1 ? 'necesita' : 'necesitan'} que las revises.</p>
        <a class="btn btn-primary" href="${k ? '#/corregir' : '#/listo'}">${k ? `Revisar ${plural(k, 'línea', 'líneas')}` : 'Continuar'}</a>
      </div>` : ''}
    <div style="margin-top: auto; display: flex; justify-content: center">
      <button type="button" class="btn btn-ghost" data-act="cancelOcr">Cancelar y subir otra imagen</button>
    </div>
  </main>`;
}

function matchHtml(p) {
  const m = T.match[p.id];
  if (!m || m.loading) return '<div class="hint" style="min-height: 20px">Buscando coincidencias…</div>';
  if (m.empty) return `<div style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 12px; background: #FDF6E7; color: #7C3A0A; font: 400 14px/1.4 var(--g)">${ic('info', 18, 2, 'style="flex: none; margin-top: 1px"')}<span>Escribe el texto de esta línea.</span></div>`;
  if (m.ok) return `<div style="display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 12px; background: #EEF2FF; color: #1E3A8A; font: 500 14px/1.35 var(--g)">${ic('check', 18, 2.2, 'style="flex: none"')}<span><span style="font-weight: 400">Coincide con</span> ${esc(m.label)}</span></div>`;
  return `<div style="display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-radius: 12px; background: #FDF6E7; color: #7C3A0A; font: 400 14px/1.4 var(--g)">${ic('info', 18, 2, 'style="flex: none; margin-top: 1px"')}<span>${esc(m.label)}</span></div>`;
}

function corregir() {
  if (!S.parsed) { setTimeout(() => location.replace('#/flyer')); return ''; }
  const total = S.pend.length;
  const remaining = S.pend.filter((p) => p.status === 'pending').length;
  const good = Math.max(0, (S.lines || []).length - total);
  const cards = S.pend.map((p, i) => {
    const n = i + 1;
    if (p.status === 'confirmed' || p.status === 'discarded') {
      const ok = p.status === 'confirmed';
      return `<article class="card appear" style="padding: 10px 8px 10px 14px; display: flex; align-items: center; gap: 12px; background: #FBFBF9" aria-label="Línea ${n} ${ok ? 'confirmada' : 'descartada'}">
        <span style="width: 28px; height: 28px; border-radius: 999px; background: ${ok ? '#18181B' : '#E6E6E1'}; color: ${ok ? '#FFFFFF' : '#52525B'}; display: inline-flex; align-items: center; justify-content: center; flex: none">${ok ? ic('check', 15, 2.6) : ic('x', 14, 2.4)}</span>
        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px">
          <span style="font: 400 12px/1.2 var(--g); color: #5F5F66">Línea ${n} · ${ok ? 'confirmada' : 'no es parte del culto'}</span>
          ${ok ? `<span style="font: 600 15px/1.3 var(--g)">${esc(p.final)}</span>` : `<span style="font: 500 15px/1.3 var(--g); color: #52525B; text-decoration: line-through">${esc(p.text || p.ocr || 'Texto sin leer')}</span>`}
        </div>
        <button type="button" class="btn btn-ghost btn-sm" data-act="reopen" data-id="${esc(p.id)}" ${T.busy ? 'disabled' : ''}>${ok ? 'Editar' : 'Deshacer'}</button>
      </article>`;
    }
    const reason = !p.ocr ? 'No se pudo leer' : p.matched ? 'Lectura dudosa' : 'Sin coincidencia';
    return `<article class="card appear" style="padding: 16px; display: flex; flex-direction: column; gap: 14px" aria-label="Línea ${n}">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
        <span style="font: 600 14px/1 var(--g)">Línea ${n}</span>
        <span class="badge b-warn">${reason}</span>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr)); gap: 14px; align-items: end">
        ${p.crop ? `<div style="display: flex; flex-direction: column; gap: 6px">
          <span class="hint" style="font-size: 12px">Recorte del flyer</span>
          <div class="crop"><img src="${p.crop}" alt="Recorte del flyer${p.ocr ? `: ${esc(p.ocr)}` : ' con texto que no pude leer'}"></div>
        </div>` : ''}
        <div style="display: flex; flex-direction: column; gap: 6px">
          ${p.ocr ? '' : '<span style="font: 600 14px/1.35 var(--g); color: #7C3A0A">Aquí hay texto que no pude leer</span>'}
          <label class="label" for="linea-${n}">Texto (corrígelo o escríbelo completo)</label>
          <input id="linea-${n}" class="input" type="text" value="${esc(p.text)}" data-in="pend" data-id="${esc(p.id)}" autocomplete="off">
        </div>
      </div>
      <div id="m-${esc(p.id)}">${matchHtml(p)}</div>
      <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px">
        <button type="button" id="c-${esc(p.id)}" class="btn btn-primary btn-sm" data-act="confirm" data-id="${esc(p.id)}" ${!p.text.trim() || T.busy ? 'disabled' : ''}>Confirmar</button>
        <button type="button" class="btn btn-secondary btn-sm" data-act="discard" data-id="${esc(p.id)}" style="padding: 0 10px" ${T.busy ? 'disabled' : ''}>No es del culto</button>
      </div>
    </article>`;
  }).join('');
  return `${steps(2, 'wrap w760')}
  <main class="wrap w760" style="padding: 22px 20px 20px; display: flex; flex-direction: column; gap: 18px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back(S.image ? '#/ocr' : '#/flyer', 'Flyer')}
      <h1 class="h1" tabindex="-1">Revisa lo que no pudimos leer</h1>
      <p class="lead">Corrige cada línea o márcala como que no es parte del culto.${good ? ` ${good === 1 ? 'La otra se leyó bien.' : `Las otras ${good} se leyeron bien.`}` : ''}</p>
    </div>
    <div style="display: flex; align-items: center; gap: 10px">
      ${remaining ? `<span class="badge b-warn">Quedan ${remaining} de ${total}</span>` : `<span class="badge b-ok">${ic('check', 13, 2.6)}Todo resuelto</span>`}
      <div style="flex: 1; height: 6px; border-radius: 3px; background: #E2E2DD; overflow: hidden" aria-hidden="true"><div style="height: 100%; width: ${total ? Math.round(((total - remaining) / total) * 100) : 100}%; background: #18181B; border-radius: 3px; transition: width .4s cubic-bezier(.34,1.3,.64,1)"></div></div>
    </div>
    ${errBox(T.err)}
    ${cards}
    <div class="actions" style="margin-top: auto; padding-top: 8px">
      ${remaining ? '<p class="hint" style="margin: 0; text-align: center">Resuelve o descarta todas las líneas para seguir.</p>' : ''}
      <button type="button" class="btn btn-primary" data-act="toOrder" ${remaining || T.busy ? 'disabled' : ''}>${T.busy ? `${spinner}Revisando…` : 'Continuar al orden del culto'}</button>
    </div>
  </main>`;
}

function listo() {
  if (!S.parsed) { setTimeout(() => location.replace('#/flyer')); return ''; }
  const items = S.flyerItems;
  return `${steps(1, 'wrap w880', ' · listo')}
  <main class="wrap w880" style="padding: 24px 20px 24px; display: flex; flex-direction: column; gap: 20px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 10px">
      <span class="badge b-ok" style="align-self: flex-start">${ic('check', 13, 2.6)}Sin líneas dudosas</span>
      <h1 class="h1" tabindex="-1">Leímos ${items.length === 1 ? 'el único elemento' : `los ${items.length} elementos`} del flyer</h1>
      <p class="lead">Todo coincidió con el himnario, la biblioteca o un pasaje, así que no hay nada que corregir.</p>
    </div>
    <div style="display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start">
      ${S.image ? `<div class="photo" style="flex: 1 1 260px; height: 300px" role="img" aria-label="Foto del flyer subida"><img src="${S.image}" alt=""></div>` : ''}
      <ol class="card" style="flex: 1 1 300px; list-style: none; margin: 0; padding: 6px 16px">
        ${items.map((it) => { const l = look(it); return `<li style="display: flex; align-items: center; gap: 10px; min-height: 48px; border-bottom: 1px solid #F0F0EC"><span class="badge ${l.cls}" style="min-width: 66px; justify-content: center">${l.type}</span><span style="font: 500 15px/1.3 var(--g)">${esc(l.heading)}</span></li>`; }).join('')}
      </ol>
    </div>
    <div style="margin-top: auto; display: flex; justify-content: flex-end">
      <button type="button" class="btn btn-primary" data-act="toOrder" style="flex: 1 1 auto; max-width: 420px">Revisar orden del culto</button>
    </div>
  </main>`;
}

const LINE_OPTS = [['auto', 'Automático'], [2, '2'], [4, '4'], ['whole', 'Estrofa']];
function chunkOf(it) { return it.op === 'hymn' ? (it.verse_chunk_size ?? 'auto') : (it.chunk_size ?? 'auto'); }

function orden() {
  if (!S.parsed) { setTimeout(() => location.replace('#/flyer')); return ''; }
  const items = S.items;
  let last = null;
  const rows = items.map((it, i) => {
    let head = '';
    if (it._block !== last) {
      last = it._block;
      head = `<h2 style="margin: 10px 0 0; display: flex; align-items: center; gap: 10px; font: 600 12px/1 var(--g); letter-spacing: .08em; text-transform: uppercase; color: #52525B">Bloque ${it._block} de alabanza<span style="flex: 1; height: 1px; background: #DEDED9"></span></h2>`;
    }
    const l = look(it);
    const open = T.open === it._id;
    const isNew = !!it._new;
    const hasLines = !isNew && (it.op === 'hymn' || (it.op === 'song' && !it.key));
    const canLyrics = !isNew && it.op !== 'scripture';
    const ly = T.lyrics[it._id];
    const ch = chunkOf(it);
    const linesLabel = ch === 'whole' ? 'Estrofa completa por slide' : `${ch} líneas por slide`;
    return `${head}<article class="card" style="overflow: hidden">
      <div style="display: flex; align-items: center; gap: 4px; padding: 8px 6px">
        <span aria-hidden="true" style="width: 28px; display: flex; justify-content: center; color: #A1A19B"><svg width="16" height="20" viewBox="0 0 16 24" fill="currentColor"><circle cx="5" cy="6" r="1.6"/><circle cx="11" cy="6" r="1.6"/><circle cx="5" cy="12" r="1.6"/><circle cx="11" cy="12" r="1.6"/><circle cx="5" cy="18" r="1.6"/><circle cx="11" cy="18" r="1.6"/></svg></span>
        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; padding: 4px 0">
          <div style="display: flex; flex-wrap: wrap; gap: 6px">
            <span class="badge ${l.cls}">${l.type}</span>
            ${isNew ? '<span class="badge b-warn">No está en la biblioteca</span>' : ''}
            ${it._v && it._v.review ? '<span class="badge b-warn">Revisar formato</span>' : ''}
            ${it._v && it._v.todo ? '<span class="badge b-warn">Falta el texto</span>' : ''}
            ${hasLines && ch !== 'auto' && !open ? `<span class="badge b-muted">${linesLabel}</span>` : ''}
          </div>
          <div style="font: 600 16px/1.3 var(--g); text-wrap: pretty">${esc(l.heading)}</div>
        </div>
        <button type="button" class="icon-btn" aria-expanded="${open}" aria-label="Opciones de ${esc(l.heading)}" data-act="toggleItem" data-id="${it._id}">${ic('chev', 20, 2, `class="chev" style="transform: rotate(${open ? 180 : 0}deg)"`)}</button>
      </div>
      ${open ? `<div class="appear" style="display: flex; flex-direction: column; gap: 14px; padding: 4px 14px 14px; border-top: 1px solid #EFEFEB">
        ${hasLines ? `<div style="display: flex; flex-direction: column; gap: 8px; padding-top: 10px">
          <span class="label" id="lps-${it._id}">Líneas por slide</span>
          <div class="seg" role="group" aria-labelledby="lps-${it._id}">
            ${LINE_OPTS.map(([v, lab]) => `<button type="button" aria-pressed="${String(ch) === String(v)}" data-act="chunk" data-id="${it._id}" data-v="${v}">${lab}</button>`).join('')}
          </div>
        </div>` : ''}
        ${it._v && it._v.review ? '<p style="margin: 0; padding: 10px 12px; border-radius: 12px; background: #FDF6E7; color: #7C3A0A; font: 400 14px/1.45 var(--g)">El himnario trae este himno con un formato irregular. Revisa cómo quedan sus slides en la vista previa.</p>' : ''}
        ${it._v && it._v.todo ? '<p style="margin: 0; padding: 10px 12px; border-radius: 12px; background: #FDF6E7; color: #7C3A0A; font: 400 14px/1.45 var(--g)">No encontré este pasaje en la Reina-Valera 1960. Revisa la cita en el flyer; en la presentación sale como pendiente.</p>' : ''}
        ${ly && ly !== 'loading' && !ly.error ? lyricsBox(ly, `Letra de ${l.heading}`) : ''}
        ${ly && ly.error ? errBox(ly.error) : ''}
        <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap">
          ${canLyrics ? `<button type="button" class="btn btn-secondary btn-sm" data-act="itemLyrics" data-id="${it._id}" aria-expanded="${!!ly && !ly.error}">${ly === 'loading' ? spinner : ic('eye', 16)}${ly && ly !== 'loading' && !ly.error ? 'Ocultar letra' : 'Ver letra'}</button>` : ''}
          <span style="flex: 1"></span>
          <button type="button" class="icon-btn" aria-label="Subir" data-act="move" data-id="${it._id}" data-v="-1" ${i === 0 ? 'disabled' : ''}>${ic('up', 18, 2)}</button>
          <button type="button" class="icon-btn" aria-label="Bajar" data-act="move" data-id="${it._id}" data-v="1" ${i === items.length - 1 ? 'disabled' : ''}>${ic('down', 18, 2)}</button>
          <button type="button" class="icon-btn" aria-label="Eliminar del culto" data-act="removeItem" data-id="${it._id}" style="color: #9A3412">${ic('trash')}</button>
        </div>
      </div>` : ''}
      ${isNew ? `<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 10px 10px 10px 14px; background: #FDF6E7; border-top: 1px solid #F5E3BE">
        <span style="flex: 1 1 160px; font: 400 14px/1.4 var(--g); color: #7C3A0A">Sin letra: guárdala una vez y queda para las próximas semanas.</span>
        <a class="btn btn-secondary btn-sm" href="#/cancion-nueva?item=${it._id}">Agregar a la biblioteca</a>
      </div>` : ''}
    </article>`;
  }).join('');
  return `${steps(3, 'wrap w760')}
  <main class="wrap w760" style="padding: 22px 20px 24px; display: flex; flex-direction: column; gap: 14px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 6px">
      ${back(S.pend.length ? '#/corregir' : S.image ? '#/listo' : '#/flyer', S.pend.length ? 'Corregir' : 'Flyer')}
      <h1 class="h1" tabindex="-1">Orden del culto</h1>
      <p class="lead">${plural(items.length, 'elemento', 'elementos')}, en el orden del flyer. Toca uno para ver su letra, moverlo o elegir cuántas líneas van por slide.</p>
    </div>
    ${T.flash ? `<p role="status" style="margin: 0; padding: 12px 14px; border-radius: 12px; background: #EEF2FF; color: #1E3A8A; font: 500 14px/1.45 var(--g)">${esc(T.flash)}</p>` : ''}
    ${rows || '<p class="hint" style="margin: 0">El culto no tiene himnos ni canciones todavía.</p>'}
    <div style="display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 18px; border: 1.5px dashed #D2D2CC; color: #52525B; margin-top: 4px">
      ${ic('book', 20)}
      <span style="font: 500 15px/1.3 var(--g)">Prédica <span style="font-weight: 400">· ${S.sermon.title.trim() ? esc(S.sermon.title) : 'la completas en el siguiente paso'}</span></span>
    </div>
    <a class="btn btn-secondary" href="#/agregar" style="margin-top: 4px">${ic('plus', 18, 2)}Agregar himno o canción</a>
    <div class="actions between" style="margin-top: auto; padding-top: 16px">
      <span class="hint">Los cambios se guardan solos.</span>
      <a class="btn btn-primary" href="#/predica">Continuar a la prédica</a>
    </div>
  </main>`;
}

function searchResults() {
  if (!T.q || !T.q.trim()) return '<span class="hint">Escribe un número de himno o parte del título.</span>';
  if (T.searching && !T.results) return `<span class="hint" style="display: inline-flex; align-items: center; gap: 8px">${spinner}Buscando…</span>`;
  if (T.searchErr) return errBox(T.searchErr);
  const tab = T.tab || 'todo';
  const res = (T.results || []).filter((r) => tab === 'todo' || (tab === 'himnos' ? r.kind === 'himno' : r.kind === 'cancion'));
  const added = (r) => S.items.some((i) => (r.op === 'hymn' ? i.op === 'hymn' && i.himno === r.himno : i.key === r.key));
  const id = (r) => (r.op === 'hymn' ? `h${r.himno}` : `s-${r.key}`);
  return `<span style="font: 500 13px/1 var(--g); color: #52525B">${plural(res.length, 'resultado', 'resultados')}</span>
    ${res.map((r) => {
    const rid = id(r);
    const ly = T.lyrics[rid];
    const open = ly && ly !== 'loading' && !ly.error;
    const heading = r.op === 'hymn' ? `${r.label} · ${r.title}` : r.title;
    const isAdded = added(r);
    return `<article class="card" style="overflow: hidden">
        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 12px 12px 16px; flex-wrap: wrap">
          <div style="flex: 1 1 180px; min-width: 0; display: flex; flex-direction: column; gap: 6px">
            <span class="badge ${r.kind === 'himno' ? 'b-himno' : 'b-cancion'}" style="align-self: flex-start">${r.kind === 'himno' ? 'Himno' : 'Canción'}</span>
            <span style="font: 600 16px/1.3 var(--g)">${esc(heading)}</span>
          </div>
          <div style="display: flex; gap: 8px">
            <button type="button" class="btn btn-secondary btn-sm" aria-expanded="${!!open}" data-act="resultLyrics" data-rid="${esc(rid)}">${ly === 'loading' ? spinner : ''}${open ? 'Ocultar letra' : 'Ver letra'}</button>
            <button type="button" class="btn btn-primary btn-sm${isAdded ? ' added' : ''}" data-act="addResult" data-rid="${esc(rid)}" ${isAdded ? 'disabled' : ''}>${isAdded ? 'Agregado' : 'Agregar'}</button>
          </div>
        </div>
        ${open ? `<div style="margin: 0 12px 12px">${lyricsBox(ly, `Letra de ${heading}`)}</div>` : ''}
        ${ly && ly.error ? `<div style="margin: 0 12px 12px">${errBox(ly.error)}</div>` : ''}
      </article>`;
  }).join('')}
    ${res.length ? '' : `<div style="padding: 20px; border-radius: 18px; border: 1.5px dashed #D2D2CC; display: flex; flex-direction: column; gap: 12px; align-items: flex-start">
      <span style="font: 400 15px/1.45 var(--g); color: #3F3F46">No hay coincidencias en el himnario ni en la biblioteca.</span>
      <a class="btn btn-secondary btn-sm" href="#/cancion-nueva?add=1&title=${encodeURIComponent(T.q.trim())}">Agregar canción nueva a la biblioteca</a>
    </div>`}`;
}

function agregar() {
  const tab = T.tab || 'todo';
  return `<main class="wrap w760" style="padding: 18px 20px 24px; display: flex; flex-direction: column; gap: 16px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back('#/orden', 'Orden del culto')}
      <h1 class="h1" tabindex="-1">Agregar al culto</h1>
    </div>
    <div class="seg" role="group" aria-label="Qué buscar">
      ${[['todo', 'Todo'], ['himnos', 'Himnos'], ['canciones', 'Canciones']].map(([v, l]) => `<button type="button" aria-pressed="${tab === v}" data-act="tab" data-v="${v}">${l}</button>`).join('')}
    </div>
    <div style="display: flex; flex-direction: column; gap: 6px">
      <label class="label" for="buscar">Buscar</label>
      <div style="position: relative">
        ${ic('search', 20, 1.8, 'style="position: absolute; left: 14px; top: 14px; color: #5F5F66"')}
        <input id="buscar" class="input has-icon" type="search" value="${esc(T.q || '')}" data-in="q" autocomplete="off">
      </div>
      <span class="hint">Himno por número (1–412) o por título. Canción por título.</span>
    </div>
    <div id="results" style="display: flex; flex-direction: column; gap: 10px" aria-live="polite">${searchResults()}</div>
    ${T.lastAdded ? `<div class="appear" role="status" style="margin-top: auto; display: flex; align-items: center; gap: 12px; padding: 12px 12px 12px 16px; border-radius: 16px; background: #18181B; color: #FFFFFF; flex-wrap: wrap">
      <span style="flex: 1 1 160px; font: 500 14px/1.4 var(--g)">${esc(T.lastAdded)}</span>
      <a class="btn btn-sm" href="#/orden" style="background: #FFFFFF; color: #18181B">Ver orden</a>
    </div>` : ''}
  </main>`;
}

const SEC_TYPES = { estrofa: 'verse', coro: 'chorus', puente: 'bridge' };
const SEC_NAMES = { estrofa: 'Estrofa', coro: 'Coro', puente: 'Puente' };
function nueva(q) {
  const f = T.song;
  if (!f) return `<main class="wrap w760" style="padding: 18px 20px 24px"><span class="hint" style="display: inline-flex; align-items: center; gap: 8px">${spinner}Cargando la canción…</span></main>`;
  const fromLib = q.get('from') === 'biblioteca';
  const backHref = fromLib ? '#/biblioteca' : '#/orden';
  const total = {};
  const n = {};
  f.sections.forEach((s) => { total[s.type] = (total[s.type] || 0) + 1; });
  const secs = f.sections.map((s) => {
    n[s.type] = (n[s.type] || 0) + 1;
    const label = SEC_NAMES[s.type] + (total[s.type] > 1 ? ` ${n[s.type]}` : '');
    return `<div class="card appear" style="padding: 12px; display: flex; flex-direction: column; gap: 10px">
      <div style="display: flex; align-items: center; gap: 8px">
        <label class="sr" for="tipo-${s.id}">Tipo de sección</label>
        <select id="tipo-${s.id}" class="input" style="width: auto; min-width: 150px" data-ch="secType" data-id="${s.id}">
          ${Object.entries(SEC_NAMES).map(([v, l]) => `<option value="${v}" ${s.type === v ? 'selected' : ''}>${l}</option>`).join('')}
        </select>
        <span style="flex: 1; font: 500 14px/1 var(--g); color: #52525B">${label}</span>
        <button type="button" class="icon-btn" aria-label="Quitar ${label}" data-act="secRemove" data-id="${s.id}">${ic('trash')}</button>
      </div>
      <label class="sr" for="letra-${s.id}">Letra de ${label}</label>
      <textarea id="letra-${s.id}" class="input" rows="5" data-in="secText" data-id="${s.id}" placeholder="Pega la letra de esta sección, un renglón por línea">${esc(s.text)}</textarea>
    </div>`;
  }).join('');
  return `<main class="wrap w760" style="padding: 18px 20px 24px; display: flex; flex-direction: column; gap: 18px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back(backHref, fromLib ? 'Biblioteca' : 'Orden del culto')}
      <h1 class="h1" tabindex="-1">${f.key ? 'Editar canción' : 'Agregar a la biblioteca'}</h1>
      <p class="lead">${q.get('item') ? 'Esta canción venía en el flyer pero no está guardada. ' : ''}${f.key ? 'Los cambios quedan en la biblioteca para las próximas semanas.' : 'Queda en la biblioteca para las próximas semanas.'}</p>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: 14px">
      <div style="display: flex; flex-direction: column; gap: 6px">
        <label class="label" for="titulo">Título principal</label>
        <input id="titulo" class="input" type="text" value="${esc(f.title_white)}" data-in="songTitle" data-v="title_white">
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px">
        <label class="label" for="titulo2">Título secundario <span style="font-weight: 400; color: #5F5F66">(opcional)</span></label>
        <input id="titulo2" class="input" type="text" value="${esc(f.title_cream)}" data-in="songTitle" data-v="title_cream" placeholder="Ej.: segunda línea, en crema">
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 12px">
      <div style="display: flex; align-items: baseline; justify-content: space-between">
        <h2 style="margin: 0; font: 600 17px/1.2 var(--g)">Letra por secciones</h2>
        <span class="hint">${plural(f.sections.length, 'sección', 'secciones')}</span>
      </div>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: 12px">${secs}</div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap">
        ${Object.entries(SEC_NAMES).map(([v, l]) => `<button type="button" class="btn btn-secondary btn-sm" data-act="secAdd" data-v="${v}">${ic('plus', 16, 2)}${l}</button>`).join('')}
      </div>
      <p class="hint" style="margin: 0">Un coro se escribe una vez. En las slides se repite donde lo indique el orden.</p>
    </div>
    ${errBox(T.err)}
    <div class="actions rev" style="margin-top: auto; padding-top: 12px">
      <a class="btn btn-ghost" href="${backHref}">Cancelar</a>
      <button type="button" class="btn btn-primary" data-act="saveSong" ${T.busy ? 'disabled' : ''}>${T.busy ? `${spinner}Guardando…` : 'Guardar en la biblioteca'}</button>
    </div>
  </main>`;
}

function versesHtml() {
  const items = S.sermon.items;
  if (T.passBusy) return `<span class="hint" style="display: inline-flex; align-items: center; gap: 8px">${spinner}Buscando el pasaje…</span>`;
  if (!items.length) return '<p class="hint" style="margin: 0">Escribe el pasaje y aquí aparece cada cita.</p>';
  return items.map((it, i) => `<div class="card" style="padding: 14px; display: flex; flex-direction: column; gap: 12px">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px">
        <h3 style="margin: 0; font: 600 15px/1.2 var(--g)">${esc(`${it.book} ${it.range}`)}</h3>
        ${it._todo && !(it._text || '').trim() ? '<span class="badge b-warn">Pendiente</span>' : `<span class="badge b-ok">${(it._text || '').trim() ? 'Texto propio' : 'RVR1960'}</span>`}
      </div>
      ${it._todo ? '<p class="hint" style="margin: 0; color: #7C3A0A">No encontré esta cita en la Reina-Valera 1960. Revisa el libro y los versículos, o pega el texto aquí.</p>' : ''}
      <div style="display: flex; flex-direction: column; gap: 6px">
        <label class="label" for="v-${i}">Texto propio <span style="font-weight: 400; color: #5F5F66">(opcional)</span></label>
        <textarea id="v-${i}" class="input${it._todo && !(it._text || '').trim() ? ' empty' : ''}" rows="3" data-in="ovr" data-i="${i}" placeholder="Déjalo vacío para usar el texto RVR1960">${esc(it._text || '')}</textarea>
      </div>
    </div>`).join('');
}

const sermonHint = () => (S.sermon.title.trim() ? 'Los cambios se guardan solos.' : 'Sin título, la presentación sale sin slide de prédica.');
function predica() {
  const sm = S.sermon;
  return `${steps(4, 'wrap w760')}
  <main class="wrap w760" style="padding: 22px 20px 24px; display: flex; flex-direction: column; gap: 20px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back('#/orden', 'Orden del culto')}
      <h1 class="h1" tabindex="-1">Prédica</h1>
      <p class="lead">El flyer casi nunca la trae. Pide los datos al pastor.</p>
    </div>
    <section class="card" style="padding: 16px; display: flex; flex-direction: column; gap: 14px" aria-label="Datos de la prédica">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: 14px">
        <div style="display: flex; flex-direction: column; gap: 6px">
          <label class="label" for="entrada">Frase de entrada</label>
          <input id="entrada" class="input" type="text" value="${esc(sm.lead)}" data-in="sermon" data-v="lead">
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px">
          <label class="label" for="titulo">Título</label>
          <input id="titulo" class="input" type="text" value="${esc(sm.title)}" data-in="sermon" data-v="title" placeholder="Ej.: Sed de Dios">
        </div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px">
        <label class="label" for="pasaje">Pasaje</label>
        <input id="pasaje" class="input" type="text" value="${esc(sm.passage)}" data-in="sermon" data-v="passage" placeholder="Ej.: Salmos 42:1-2 &amp; 63:1-3" aria-describedby="pasaje-h">
        <span class="hint" id="pasaje-h">Separa varios pasajes con &amp;.</span>
        <div id="pass-err">${errBox(T.passErr)}</div>
      </div>
    </section>
    <section style="display: flex; flex-direction: column; gap: 12px" aria-labelledby="vh">
      <h2 id="vh" style="margin: 0; font: 600 17px/1.2 var(--g)">Texto de los versículos</h2>
      <p class="hint" style="margin: 0">El texto RVR1960 se agrega solo. Pega un texto propio solo si quieres otro; deja una línea en blanco entre slides.</p>
      <div id="verses" style="display: flex; flex-direction: column; gap: 12px">${versesHtml()}</div>
    </section>
    <div class="actions between" style="margin-top: auto; padding-top: 8px">
      <span class="hint" id="sermon-hint">${sermonHint()}</span>
      <a class="btn btn-primary" href="#/lecturas">Continuar a lecturas</a>
    </div>
  </main>`;
}

function lecturas() {
  if (T.openRead === undefined) T.openRead = 'bienvenida';
  const cards = READINGS.map((d, i) => {
    const v = S.readings[d.id];
    const has = !!v.ref.trim();
    const open = T.openRead === d.id;
    const err = T.readErr && T.readErr[d.id];
    return `<article class="card" style="overflow: hidden">
      <div style="display: flex; align-items: center; gap: 12px; padding: 12px 8px 12px 16px">
        <span style="width: 28px; height: 28px; flex: none; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; font: 600 13px/1 var(--g); background: ${has ? '#18181B' : '#EDEDE9'}; color: ${has ? '#FFFFFF' : '#52525B'}">${i + 1}</span>
        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">
          <span style="font: 600 16px/1.25 var(--g)">${d.name}</span>
          <span style="font: 400 13px/1.35 var(--g); color: #5F5F66">${d.where}${has ? ` · <span style="color: #18181B; font-weight: 500">${esc(v.ref)}</span>` : ''}</span>
        </div>
        <button type="button" class="btn btn-ghost btn-sm" aria-expanded="${open}" data-act="toggleRead" data-id="${d.id}">${open ? 'Listo' : has ? 'Editar' : 'Agregar'}</button>
      </div>
      ${open ? `<div class="appear" style="display: flex; flex-direction: column; gap: 12px; padding: 14px 16px 16px; border-top: 1px solid #EFEFEB">
        <div style="display: flex; flex-direction: column; gap: 6px">
          <label class="label" for="ref-${d.id}">Pasaje</label>
          <input id="ref-${d.id}" class="input" type="text" value="${esc(v.ref)}" placeholder="Ej.: Salmos 100:1-2" data-in="rref" data-id="${d.id}">
          <div id="rerr-${d.id}">${err ? errBox(err) : v.items.some((x) => x._todo) ? '<p class="hint" style="margin: 0; color: #7C3A0A">No encontré esta cita en la Reina-Valera 1960: pega el texto abajo o sale como pendiente.</p>' : ''}</div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px">
          <label class="label" for="tx-${d.id}">Texto (Reina-Valera 1960)</label>
          <textarea id="tx-${d.id}" class="input" rows="4" placeholder="Opcional: el texto RVR1960 se agrega solo" data-in="rtext" data-id="${d.id}">${esc(v.text)}</textarea>
        </div>
        ${has ? `<button type="button" class="btn btn-ghost btn-sm" data-act="clearRead" data-id="${d.id}" style="align-self: flex-start; color: #9A3412">Quitar esta lectura</button>` : ''}
      </div>` : ''}
    </article>`;
  }).join('');
  return `${steps(5, 'wrap w760')}
  <main class="wrap w760" style="padding: 22px 20px 24px; display: flex; flex-direction: column; gap: 16px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back('#/predica', 'Prédica')}
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
        <h1 class="h1" tabindex="-1">Lecturas</h1>
        <span class="badge b-muted">Opcional</span>
      </div>
      <p class="lead">Las lecturas de quien dirige el culto. Cada una se inserta en su lugar. Usa solo las que tengas.</p>
    </div>
    ${cards}
    <div class="actions rev" style="margin-top: auto; padding-top: 12px">
      <a class="btn btn-ghost" href="#/descarga">Omitir lecturas</a>
      <a class="btn btn-primary" href="#/descarga">Ver vista previa</a>
    </div>
  </main>`;
}

async function loadPreview() {
  const my = (T.prevJob = (T.prevJob || 0) + 1);
  T.prev = { loading: true };
  render();
  const items = fullItems();
  try {
    // ponytail: one preview per item so slides can be grouped; /api/preview could return the item index per slide instead
    const res = await Promise.all(items.map((it) => api('/api/preview', { output: 'x.pptx', items: [strip(it)] })));
    if (my !== T.prevJob) return;
    T.prev = { groups: items.map((it, i) => ({ it, slides: res[i].slides })) };
  } catch (e) {
    if (my !== T.prevJob) return;
    T.prev = { error: e.message };
  }
  render();
}

function descarga() {
  if (!S.parsed) { setTimeout(() => location.replace('#/flyer')); return ''; }
  const pv = T.prev || { loading: true };
  let n = 0;
  const pend = [];
  const groups = (pv.groups || []).map(({ it, slides }) => {
    const l = look(it);
    const first = n + 1;
    const thumbs = slides.map((s, i) => {
      n += 1;
      if (s.pending) {
        pend.push({ title: `${l.short} sin texto`, hint: `${l.type} · slide ${n}`, href: it._role === 'sermon' ? '#/predica' : it._role ? '#/lecturas' : '#/orden', btn: it._role ? 'Completar' : 'Ver' });
        return `<div class="thumb"><div class="slide slide-pend" role="img" aria-label="Slide ${n}: pendiente, ${esc(l.short)} sin texto"><span style="font: 600 9px/1.2 var(--g); color: #F5B759; text-align: center">${esc(l.short)}<br>sin texto</span></div><span style="font: 500 11px/1 var(--g); color: #5F5F66; font-variant-numeric: tabular-nums">${n}</span></div>`;
      }
      const text = i === 0 ? (s.lines.slice(0, 2).join(' ') || l.short) : '';
      const body = text
        ? `<span style="font: 600 10px/1.2 var(--g); color: #FFFFFF; text-align: center; text-wrap: balance; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical">${esc(text)}</span>`
        : s.lines.slice(0, 4).map((x) => `<div class="bar" style="width: ${Math.max(18, Math.min(100, x.length * 2.4))}%"></div>`).join('');
      return `<div class="thumb"><div class="slide" role="img" aria-label="Slide ${n}${text ? `: ${esc(text)}` : ''}">${body}</div><span style="font: 500 11px/1 var(--g); color: #5F5F66; font-variant-numeric: tabular-nums">${n}</span></div>`;
    }).join('');
    if (it._v && it._v.review) pend.push({ title: `${l.short} · revisar`, hint: `Formato irregular en el himnario · slides ${first}–${n}`, href: '#/orden', btn: 'Ver' });
    return `<div style="display: flex; flex-direction: column; gap: 10px">
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
        <span class="badge ${l.cls}">${l.type}</span>
        <h3 style="margin: 0; font: 600 15px/1.3 var(--g)">${esc(l.heading)}</h3>
        <span style="font: 400 13px/1 var(--g); color: #5F5F66">${plural(slides.length, 'slide', 'slides')}</span>
        ${it._v && it._v.review ? '<span class="badge b-warn">Revisar</span>' : ''}
      </div>
      <div class="thumbs" tabindex="0" aria-label="Slides de ${esc(l.heading)}">${thumbs}</div>
    </div>`;
  }).join('');
  placeholders().forEach((p) => pend.push({ title: `${p._v.title} sin letra`, hint: 'No está en la biblioteca: no sale en la presentación', href: `#/cancion-nueva?item=${p._id}`, btn: 'Completar' }));
  if (!S.sermon.title.trim()) pend.push({ title: 'Sin prédica', hint: 'Falta el título de la prédica', href: '#/predica', btn: 'Completar' });
  return `${steps(6, 'wrap-wide')}
  <div class="wrap-wide" style="padding: 22px 20px 0; display: flex; flex-direction: column; gap: 8px">
    ${back('#/lecturas', 'Lecturas')}
    <div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap">
      <h1 class="h1" tabindex="-1">Vista previa</h1>
      <span style="font: 500 15px/1 var(--g); color: #52525B; font-variant-numeric: tabular-nums">${pv.groups ? plural(n, 'slide', 'slides') : ''}</span>
    </div>
  </div>
  <main class="wrap-wide" style="padding: 18px 20px 28px; display: flex; flex-direction: row-reverse; flex-wrap: wrap; align-items: flex-start; gap: 24px; flex: 1">
    <aside class="side" style="flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; gap: 14px" aria-label="Pendientes y descarga">
      ${pend.length && pv.groups ? `<section class="card" style="padding: 16px; display: flex; flex-direction: column; gap: 12px; border-color: #F1D9AE; background: #FFFCF5" aria-labelledby="pend">
        <div style="display: flex; align-items: center; gap: 10px">
          ${ic('warn', 20, 2, 'style="color: #9A4A0B"')}
          <h2 id="pend" style="margin: 0; font: 600 16px/1.2 var(--g); color: #7C3A0A">${plural(pend.length, 'pendiente', 'pendientes')}</h2>
        </div>
        <ul style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column">
          ${pend.map((p) => `<li style="display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid #F3E4C6">
            <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px">
              <span style="font: 600 14px/1.3 var(--g)">${esc(p.title)}</span>
              <span class="hint">${esc(p.hint)}</span>
            </div>
            <a class="btn btn-secondary btn-sm" href="${p.href}">${p.btn}</a>
          </li>`).join('')}
        </ul>
      </section>` : ''}
      <section class="card" style="padding: 16px; display: flex; flex-direction: column; gap: 14px" aria-label="Descargar">
        <div style="display: flex; flex-direction: column; gap: 6px">
          <label class="label" for="archivo">Nombre del archivo</label>
          <div style="display: flex; align-items: stretch">
            <input id="archivo" class="input" type="text" value="${esc(S.output)}" data-in="name" style="border-radius: 12px 0 0 12px; font-weight: 600">
            <span style="display: flex; align-items: center; padding: 0 14px; border: 1px solid #D4D4CF; border-left: 0; border-radius: 0 12px 12px 0; background: #F1F1EE; font: 500 15px/1 var(--g); color: #52525B">.pptx</span>
          </div>
          <span class="hint">Por default, el domingo siguiente.</span>
        </div>
        ${pend.length && pv.groups ? `<p style="margin: 0; font: 400 14px/1.45 var(--g); color: #7C3A0A">${pend.length === 1 ? 'Queda 1 pendiente' : `Quedan ${pend.length} pendientes`}. Puedes descargar igual y completarlos en PowerPoint.</p>` : ''}
        ${errBox(T.err)}
        <button type="button" class="btn btn-primary" data-act="download" ${T.busy ? 'disabled' : ''}>${T.busy ? `${spinner}Armando la presentación…` : `${ic('download', 18, 2)}Descargar .pptx`}</button>
        ${T.downloaded ? `<div class="appear" role="status" style="display: flex; flex-direction: column; gap: 6px; padding: 12px; border-radius: 12px; background: #F1F1EE">
          <span style="font: 600 14px/1.35 var(--g)">${esc(T.downloaded)} descargado</span>
          <span style="font: 400 14px/1.45 var(--g); color: #3F3F46">Cuando la revises en PowerPoint, súbela para generar el <a href="#/letras">PDF de letras</a>.</span>
        </div>` : ''}
      </section>
    </aside>
    <section style="flex: 999 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 22px" aria-label="Miniaturas de las slides" aria-busy="${!!pv.loading}">
      ${pv.loading ? `<span class="hint" style="display: inline-flex; align-items: center; gap: 8px">${spinner}Armando la vista previa…</span>` : ''}
      ${pv.error ? `${errBox(pv.error)}<button type="button" class="btn btn-secondary btn-sm" data-act="reloadPreview" style="align-self: flex-start">Intentar de nuevo</button>` : ''}
      ${groups}
    </section>
  </main>`;
}

const fileSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
function fileCard(file, id, ch, emptyHint) {
  return `<div class="card" style="padding: 12px 12px 12px 14px; display: flex; align-items: center; gap: 12px">
    <span style="width: 44px; height: 44px; flex: none; border-radius: 12px; background: #F1F1EE; display: inline-flex; align-items: center; justify-content: center; font: 700 10px/1 var(--g); color: #3F3F46; letter-spacing: .04em">PPTX</span>
    <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">
      <span style="font: 600 15px/1.3 var(--g); overflow: hidden; text-overflow: ellipsis; white-space: nowrap">${file ? esc(file.name) : 'Ningún archivo'}</span>
      <span class="hint">${file ? fileSize(file.size) : emptyHint}</span>
    </div>
    <label class="btn ${file ? 'btn-secondary' : 'btn-primary'} btn-sm" for="${id}" style="flex: none">${file ? 'Cambiar' : 'Elegir .pptx'}</label>
    <input id="${id}" class="file-in" type="file" accept=".pptx" data-ch="${ch}">
  </div>`;
}

function letras() {
  const ok = !!T.reviewed;
  return `<main class="wrap" style="padding: 18px 20px 28px; display: flex; flex-direction: column; gap: 20px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back('#/flyer', 'Inicio')}
      <h1 class="h1" tabindex="-1">PDF de letras para los cantantes</h1>
      <p class="lead">Una canción por página. Se hace con la presentación ya revisada en PowerPoint, para que lleve tus correcciones.</p>
    </div>
    <section style="display: flex; flex-direction: column; gap: 10px" aria-labelledby="s1">
      <h2 id="s1" style="margin: 0; display: flex; align-items: center; gap: 10px; font: 600 16px/1.2 var(--g)"><span class="num">1</span>Sube la presentación revisada</h2>
      ${fileCard(T.deck, 'pptx', 'deck', 'El .pptx que corregiste en PowerPoint')}
    </section>
    <section style="display: flex; flex-direction: column; gap: 10px" aria-labelledby="s2">
      <h2 id="s2" style="margin: 0; display: flex; align-items: center; gap: 10px; font: 600 16px/1.2 var(--g)"><span class="num">2</span>Confirma</h2>
      <label class="check${ok ? ' on' : ''}" for="ok">
        <input id="ok" type="checkbox" ${ok ? 'checked' : ''} data-ch="reviewed">
        <span style="display: flex; flex-direction: column; gap: 4px">
          <span style="font: 600 15px/1.35 var(--g)">Ya revisé esta presentación</span>
          <span class="hint">El PDF sale tal cual está este archivo.</span>
        </span>
      </label>
    </section>
    ${errBox(T.err)}
    ${T.pdf ? `<section class="card appear" style="padding: 16px; display: flex; flex-direction: column; gap: 14px" aria-label="PDF listo">
      <div style="display: flex; align-items: center; gap: 12px">
        <span style="width: 44px; height: 44px; flex: none; border-radius: 12px; background: #18181B; color: #FFFFFF; display: inline-flex; align-items: center; justify-content: center; font: 700 10px/1 var(--g); letter-spacing: .04em">PDF</span>
        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px">
          <span style="font: 600 15px/1.3 var(--g)">${esc(T.pdf.name)}</span>
          <span class="hint">${fileSize(T.pdf.blob.size)} · una canción por página</span>
        </div>
      </div>
      <button type="button" class="btn btn-primary" data-act="savePdf">${ic('download', 18, 2)}Descargar PDF</button>
      <button type="button" class="btn btn-secondary btn-sm" data-act="resetPdf">Generar de nuevo</button>
    </section>` : `
    <button type="button" class="btn btn-primary" data-act="makePdf" ${!ok || !T.deck || T.busy ? 'disabled' : ''}>${T.busy ? `${spinner}Generando PDF…` : 'Generar PDF de letras'}</button>
    ${!T.deck ? '<p class="hint" style="margin: -8px 0 0; text-align: center">Elige la presentación revisada.</p>' : !ok ? '<p class="hint" style="margin: -8px 0 0; text-align: center">Marca la confirmación para generar el PDF.</p>' : ''}`}
  </main>`;
}

async function loadLibrary() {
  T.lib = null;
  T.libErr = null;
  try { T.lib = await api('/api/library'); } catch (e) { T.libErr = e.message; }
  render();
}
function libList() {
  if (T.libErr) return `<li style="padding: 16px">${errBox(T.libErr)}</li>`;
  if (!T.lib) return `<li class="hint" style="padding: 20px 16px; display: flex; align-items: center; gap: 8px">${spinner}Cargando canciones…</li>`;
  const q = (T.libq || '').trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const list = T.lib.filter((s) => s.title.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').includes(q));
  if (!list.length) return `<li style="padding: 20px 16px; font: 400 15px/1.45 var(--g); color: #52525B">Ninguna canción coincide con «${esc(T.libq)}».</li>`;
  return list.map((s) => {
    const open = T.libOpen === s.key;
    const isNew = s.date_added === todayISO();
    const song = T.songs[s.key];
    const confirming = T.confirmDel === s.key;
    return `<li style="border-bottom: 1px solid #F0F0EC">
      <button type="button" class="row" aria-expanded="${open}" data-act="libToggle" data-key="${esc(s.key)}">
        <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px">
          <span style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font: 600 15px/1.3 var(--g)">${esc(s.title)}${isNew ? '<span class="badge b-new">Nueva</span>' : ''}</span>
          <span class="hint">${plural(s.slides, 'sección', 'secciones')}${isNew ? ' · agregada hoy' : ''}</span>
        </div>
        ${ic('chev', 18, 2, `class="chev" style="transform: rotate(${open ? 180 : 0}deg); flex: none; color: #52525B"`)}
      </button>
      ${open ? `<div class="appear" style="padding: 2px 16px 16px; display: flex; flex-direction: column; gap: 12px">
        ${song && song.sections ? `<div style="display: flex; gap: 6px; flex-wrap: wrap">${sectionLabels(song.sections).map((x) => `<span class="badge b-muted">${x}</span>`).join('')}</div>` : song && song.error ? errBox(song.error) : `<span class="hint" style="display: inline-flex; align-items: center; gap: 8px">${spinner}Cargando…</span>`}
        ${T.libLyrics === s.key && song && song.sections ? lyricsBox(song.sections, `Letra de ${s.title}`) : ''}
        ${T.delErr && confirming ? errBox(T.delErr) : ''}
        ${confirming ? `<div class="appear" style="display: flex; flex-direction: column; gap: 10px; padding: 12px; border-radius: 12px; background: #FDF2EC">
          <span style="font: 500 14px/1.45 var(--g); color: #7C2D12">¿Borrar «${esc(s.title)}» de la biblioteca? Las presentaciones ya descargadas no cambian.</span>
          <div style="display: flex; gap: 8px; justify-content: flex-end">
            <button type="button" class="btn btn-ghost btn-sm" data-act="delCancel">Cancelar</button>
            <button type="button" class="btn btn-danger btn-sm" data-act="delSong" data-key="${esc(s.key)}">Borrar</button>
          </div>
        </div>` : `<div style="display: flex; gap: 8px; flex-wrap: wrap">
          <button type="button" class="btn btn-secondary btn-sm" data-act="libLyrics" data-key="${esc(s.key)}" ${song && song.sections ? '' : 'disabled'}>${T.libLyrics === s.key ? 'Ocultar letra' : 'Ver letra'}</button>
          <a class="btn btn-secondary btn-sm" href="#/cancion-nueva?from=biblioteca&key=${encodeURIComponent(s.key)}">Editar</a>
          <button type="button" class="btn btn-ghost btn-sm" style="color: #9A3412" data-act="delAsk" data-key="${esc(s.key)}">Borrar</button>
        </div>`}
      </div>` : ''}
    </li>`;
  }).join('');
}
function biblioteca() {
  return `<main class="wrap w880" style="padding: 18px 20px 28px; display: flex; flex-direction: column; gap: 16px; flex: 1">
    <div style="display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; flex-wrap: wrap">
      <div style="display: flex; flex-direction: column; gap: 6px">
        <h1 class="h1" tabindex="-1">Biblioteca</h1>
        <span style="font: 400 15px/1.3 var(--g); color: #52525B">${T.lib ? `${plural(T.lib.length, 'canción guardada', 'canciones guardadas')}` : '&nbsp;'}</span>
      </div>
      <a class="btn btn-secondary btn-sm" href="#/importar">${ic('upload', 16, 1.9)}Importar desde .pptx</a>
    </div>
    <div style="position: relative">
      <label for="buscar" class="sr">Buscar por título</label>
      ${ic('search', 20, 1.8, 'style="position: absolute; left: 14px; top: 14px; color: #5F5F66"')}
      <input id="buscar" class="input has-icon" type="search" placeholder="Buscar por título" value="${esc(T.libq || '')}" data-in="libq" autocomplete="off">
    </div>
    <ul id="lib" class="card" style="list-style: none; margin: 0; padding: 0; overflow: hidden" aria-live="polite">${libList()}</ul>
  </main>`;
}

function importar() {
  const found = T.found;
  const count = found ? found.filter((f) => f.sel && !f.exists).length : 0;
  return `<main class="wrap w760" style="padding: 18px 20px 28px; display: flex; flex-direction: column; gap: 18px; flex: 1">
    <div style="display: flex; flex-direction: column; gap: 8px">
      ${back('#/biblioteca', 'Biblioteca')}
      <h1 class="h1" tabindex="-1">Importar desde una presentación</h1>
      <p class="lead">Sube un .pptx de otra semana. Te mostramos las canciones que encontramos y eliges cuáles guardar.</p>
    </div>
    ${fileCard(T.importFile, 'pptx', 'importDeck', 'Una presentación de otra semana')}
    ${errBox(T.err)}
    ${T.busy && !found ? `<span class="hint" style="display: inline-flex; align-items: center; gap: 8px">${spinner}Buscando canciones…</span>` : ''}
    ${T.savedMsg ? `<section class="card appear" style="padding: 18px; display: flex; flex-direction: column; gap: 14px" role="status">
      <div style="display: flex; align-items: center; gap: 12px">
        <span style="width: 32px; height: 32px; border-radius: 999px; background: #18181B; color: #FFFFFF; display: inline-flex; align-items: center; justify-content: center; flex: none">${ic('check', 16, 2.6)}</span>
        <span style="font: 600 16px/1.35 var(--g)">${esc(T.savedMsg)}</span>
      </div>
      <a class="btn btn-primary" href="#/biblioteca">Ver biblioteca</a>
    </section>` : found ? `
    <section style="display: flex; flex-direction: column; gap: 10px" aria-labelledby="found">
      <div style="display: flex; align-items: baseline; justify-content: space-between; gap: 10px; flex-wrap: wrap">
        <h2 id="found" style="margin: 0; font: 600 17px/1.2 var(--g)">${found.length ? `Encontramos ${plural(found.length, 'canción', 'canciones')}` : 'No encontramos canciones'}</h2>
        <span class="hint">Los himnos no se importan: vienen del himnario.</span>
      </div>
      ${found.length ? `<fieldset class="card" style="margin: 0; padding: 0; overflow: hidden">
        <legend class="sr">Canciones a guardar</legend>
        ${found.map((f, i) => `<label class="opt${f.exists ? ' opt-off' : ''}" for="c-${i}" style="border-bottom: 1px solid #F0F0EC">
          <input id="c-${i}" type="checkbox" ${f.sel && !f.exists ? 'checked' : ''} ${f.exists ? 'disabled' : ''} data-ch="importSel" data-i="${i}">
          <span style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px">
            <span style="font: 600 15px/1.3 var(--g); color: ${f.exists ? '#5F5F66' : '#18181B'}">${esc(f.title)}</span>
            <span class="hint">${plural(f.sections.length, 'sección detectada', 'secciones detectadas')}</span>
          </span>
          <span class="badge ${f.exists ? 'b-muted' : 'b-new'}">${f.exists ? 'Ya está' : 'Nueva'}</span>
        </label>`).join('')}
      </fieldset>` : ''}
    </section>
    <div class="actions rev" style="margin-top: auto; padding-top: 8px">
      <a class="btn btn-ghost" href="#/biblioteca">Cancelar</a>
      <button type="button" class="btn btn-primary" data-act="importSave" ${!count || T.busy ? 'disabled' : ''}>${T.busy ? `${spinner}Guardando…` : count === 1 ? 'Guardar 1 canción' : `Guardar ${count} canciones`}</button>
    </div>` : ''}
  </main>`;
}

// ------------------------------------------------------------------ routing

const routes = { flyer, ocr, corregir, listo, orden, agregar, 'cancion-nueva': nueva, predica, lecturas, descarga, letras, biblioteca, importar };
const titles = { flyer: 'Subir el flyer', ocr: 'Leyendo el flyer', corregir: 'Corregir líneas', listo: 'Flyer leído', orden: 'Orden del culto', agregar: 'Agregar al culto', 'cancion-nueva': 'Canción nueva', predica: 'Prédica', lecturas: 'Lecturas', descarga: 'Vista previa y descarga', letras: 'PDF de letras', biblioteca: 'Biblioteca', importar: 'Importar canciones' };
function route() {
  const [name, q] = location.hash.replace(/^#\/?/, '').split('?');
  return { name: routes[name] ? name : 'flyer', q: new URLSearchParams(q || '') };
}
function render() {
  const r = route();
  const focusId = document.activeElement && document.activeElement.id;
  $('#app').innerHTML = routes[r.name](r.q);
  document.title = `${titles[r.name]} · worshipdeck`;
  const el = focusId && document.getElementById(focusId);
  if (el && el !== document.activeElement) el.focus({ preventScroll: true });
}

// Work a screen does once when it opens.
const enter = {
  corregir: () => S.pend.filter((p) => p.status === 'pending' && !T.match[p.id]).forEach(refreshMatch),
  agregar: () => { T.lastAdded = null; },
  'cancion-nueva': async (q) => {
    const item = S.items.find((i) => String(i._id) === q.get('item'));
    T.song = { title_white: item ? item._v.title : q.get('title') || '', title_cream: '', sections: [{ id: 1, type: 'estrofa', text: '' }, { id: 2, type: 'coro', text: '' }], next: 3 };
    if (q.get('key')) {
      T.song = null;
      render();
      try {
        const s = await api(`/api/song/${encodeURIComponent(q.get('key'))}`);
        const types = { verse: 'estrofa', chorus: 'coro', bridge: 'puente' };
        T.song = { key: s.key, title_white: s.title_white ?? s.title, title_cream: s.title_cream || '', keep: Object.fromEntries(Object.entries({ artist: s.artist, source: s.source, verbatim: s.verbatim }).filter(([, v]) => v != null)), sections: s.sections.map((x, i) => ({ id: i + 1, type: types[x.kind] || 'estrofa', text: x.lines.join('\n') })), next: s.sections.length + 1 };
      } catch (e) {
        T.song = { title_white: '', title_cream: '', sections: [], next: 1 };
        T.err = e.message;
      }
      render();
    }
  },
  descarga: () => { T.downloaded = false; return loadPreview(); },
  letras: () => { T.pdf = null; },
  biblioteca: () => { T.libOpen = null; T.confirmDel = null; loadLibrary(); },
  importar: () => { T.found = null; T.importFile = null; T.savedMsg = null; },
};
function onRoute() {
  T.err = null;
  T.busy = false;
  const r = route();
  const p = enter[r.name] && enter[r.name](r.q);
  render();
  T.flash = null;
  window.scrollTo(0, 0);
  const h = $('h1');
  if (h) h.focus({ preventScroll: true });
  return p;
}
window.addEventListener('hashchange', onRoute);

// ------------------------------------------------------------------ actions

const byId = (id) => S.items.find((i) => String(i._id) === String(id));
const pendById = (id) => S.pend.find((p) => String(p.id) === String(id));

const A = {
  mode: (d) => { S.mode = d.v; T.err = null; save(); render(); },
  async readText() {
    const text = S.text;
    if (!text.trim()) { T.err = 'Pega la lista del culto primero.'; return render(); }
    newWeek({ mode: 'txt', text });
    T.busy = true;
    render();
    // Text goes in as line records (dummy boxes) so corrections work like the flyer's.
    const lines = text.split('\n').map((t, i) => ({ id: i, text: t, conf: 100, box: [0, 0, 0, 0] })).filter((l) => l.text.trim());
    try {
      applyParse(await api('/api/parse', { lines }), true);
      T.busy = false;
      if (S.pend.length) location.hash = '#/corregir'; else toOrder();
    } catch (e) {
      T.busy = false;
      T.err = e.message;
      render();
    }
  },
  retryOcr: () => runOcr(),
  cancelOcr: () => { job++; if (worker) worker.terminate(); worker = null; T.ocr = null; location.hash = '#/flyer'; },
  async confirm(d) {
    const p = pendById(d.id);
    p.text = p.text.trim();
    if ((T.match[p.id] || {}).text !== p.text) { clearTimeout(timers[`m${p.id}`]); await refreshMatch(p); } // typed faster than the match came back
    const m = T.match[p.id] || {};
    p.status = 'confirmed';
    p.final = m.ok ? m.label : `Canción nueva · ${p.text} (no está en la biblioteca)`;
    reparse();
  },
  discard(d) { pendById(d.id).status = 'discarded'; reparse(); },
  reopen(d) { const p = pendById(d.id); p.status = 'pending'; reparse().then(() => refreshMatch(p)); },
  toOrder: () => toOrder(),
  toggleItem(d) { T.open = T.open === Number(d.id) ? null : Number(d.id); render(); },
  chunk(d) {
    const it = byId(d.id);
    const v = /^\d+$/.test(d.v) ? Number(d.v) : d.v;
    if (it.op === 'hymn') { it.verse_chunk_size = v; it.chorus_chunk_size = v; } else if (v === 'auto') delete it.chunk_size; else it.chunk_size = v;
    save();
    render();
  },
  async itemLyrics(d) {
    const it = byId(d.id);
    if (T.lyrics[it._id] && T.lyrics[it._id] !== 'loading') { delete T.lyrics[it._id]; return render(); }
    T.lyrics[it._id] = 'loading';
    render();
    try { T.lyrics[it._id] = await fetchLyrics(it); } catch (e) { T.lyrics[it._id] = { error: e.message }; }
    render();
  },
  move(d) {
    const i = S.items.findIndex((x) => String(x._id) === d.id);
    const j = i + Number(d.v);
    const it = S.items[i];
    const nb = S.items[j];
    if (!nb) return;
    if (nb._block !== it._block) it._block = nb._block;
    else { S.items[i] = nb; S.items[j] = it; }
    save();
    render();
  },
  removeItem(d) { S.items = S.items.filter((x) => String(x._id) !== d.id); save(); render(); },
  tab(d) { T.tab = d.v; render(); },
  async resultLyrics(d) {
    const rid = d.rid;
    if (T.lyrics[rid] && T.lyrics[rid] !== 'loading') { delete T.lyrics[rid]; return patch('results', searchResults()); }
    const r = T.results.find((x) => (x.op === 'hymn' ? `h${x.himno}` : `s-${x.key}`) === rid);
    T.lyrics[rid] = 'loading';
    patch('results', searchResults());
    try { T.lyrics[rid] = await fetchLyrics(r); } catch (e) { T.lyrics[rid] = { error: e.message }; }
    patch('results', searchResults());
  },
  addResult(d) {
    const r = T.results.find((x) => (x.op === 'hymn' ? `h${x.himno}` : `s-${x.key}`) === d.rid);
    const block = Math.max(1, ...S.items.map((i) => i._block));
    const item = r.op === 'hymn' ? { op: 'hymn', himno: r.himno } : { op: 'song', key: r.key };
    S.items.push({ ...item, _v: { kind: r.kind, label: r.label, title: r.title }, _id: S.uid++, _block: block });
    save();
    T.lastAdded = `${r.op === 'hymn' ? r.label : r.title} se agregó al final del bloque ${block}.`;
    render();
  },
  secAdd(d) { T.song.sections.push({ id: T.song.next++, type: d.v, text: '' }); render(); },
  secRemove(d) { T.song.sections = T.song.sections.filter((s) => String(s.id) !== d.id); render(); },
  async saveSong() {
    const f = T.song;
    const q = route().q;
    const sections = f.sections.map((s) => ({ type: SEC_TYPES[s.type], lines: s.text.split('\n').map((x) => x.trim()).filter(Boolean) })).filter((s) => s.lines.length);
    if (!f.title_white.trim()) { T.err = 'Falta el título principal.'; return render(); }
    if (!sections.length) { T.err = 'Falta la letra: pega al menos una sección.'; return render(); }
    const entry = { title_white: f.title_white.trim(), title_cream: f.title_cream.trim(), sections };
    if (!entry.title_cream) delete entry.title_cream;
    const title = [entry.title_white, entry.title_cream].filter(Boolean).join(' ');
    const item = S.items.find((i) => String(i._id) === q.get('item'));
    const forCulto = item || q.get('add');
    const put = (spec) => {
      const full = { ...spec, _v: { kind: 'cancion', label: 'Canción', title } };
      if (item) { Object.keys(item).forEach((k) => { if (!['_id', '_block'].includes(k)) delete item[k]; }); Object.assign(item, full); } else S.items.push({ ...full, _id: S.uid++, _block: Math.max(1, ...S.items.map((i) => i._block)) });
      save();
    };
    T.busy = true;
    T.err = null;
    render();
    try {
      const { key } = await api('/api/library', f.key ? { ...f.keep, ...entry, replace: f.key } : entry);
      if (forCulto) put({ op: 'song', key });
      T.busy = false;
      location.hash = q.get('from') === 'biblioteca' ? '#/biblioteca' : '#/orden';
    } catch (e) {
      T.busy = false;
      if (e.status === 501 && forCulto) {
        put({ op: 'song', ...entry });
        T.flash = `«${title}» quedó guardada solo para el culto de esta semana: en esta versión en línea la biblioteca es de solo lectura.`;
        location.hash = '#/orden';
      } else {
        T.err = e.message;
        render();
      }
    }
  },
  toggleRead(d) { T.openRead = T.openRead === d.id ? null : d.id; render(); },
  clearRead(d) { S.readings[d.id] = { ref: '', text: '', items: [] }; if (T.readErr) delete T.readErr[d.id]; T.openRead = null; save(); render(); },
  reloadPreview: () => loadPreview(),
  async download() {
    T.busy = true;
    T.err = null;
    T.downloaded = false;
    render();
    const spec = deckSpec();
    try {
      saveBlob(await api('/api/build', spec, { blob: true }), spec.output);
      T.downloaded = spec.output;
    } catch (e) {
      T.err = e.message;
    }
    T.busy = false;
    render();
  },
  async makePdf() {
    const fd = new FormData();
    fd.append('deck', T.deck);
    fd.append('reviewed', 'true');
    T.busy = true;
    T.err = null;
    render();
    try {
      const blob = await api('/api/letras', fd, { blob: true });
      T.pdf = { blob, name: `Letras - ${T.deck.name.replace(/\.pptx$/i, '')}.pdf` };
    } catch (e) {
      T.err = e.message;
    }
    T.busy = false;
    render();
  },
  savePdf: () => saveBlob(T.pdf.blob, T.pdf.name),
  resetPdf: () => { T.pdf = null; render(); },
  async libToggle(d) {
    T.libOpen = T.libOpen === d.key ? null : d.key;
    T.confirmDel = null;
    patch('lib', libList());
    if (T.libOpen && !T.songs[d.key]) {
      try { T.songs[d.key] = await api(`/api/song/${encodeURIComponent(d.key)}`); } catch (e) { T.songs[d.key] = { error: e.message }; }
      patch('lib', libList());
    }
  },
  libLyrics(d) { T.libLyrics = T.libLyrics === d.key ? null : d.key; patch('lib', libList()); },
  delAsk(d) { T.confirmDel = d.key; T.delErr = null; patch('lib', libList()); },
  delCancel() { T.confirmDel = null; patch('lib', libList()); },
  async delSong(d) {
    try {
      await api(`/api/library/${encodeURIComponent(d.key)}`, undefined, { method: 'DELETE' });
      T.lib = T.lib.filter((s) => s.key !== d.key);
      T.libOpen = null;
      T.confirmDel = null;
      render();
    } catch (e) {
      T.delErr = e.message;
      patch('lib', libList());
    }
  },
  async importSave() {
    const pick = T.found.filter((f) => f.sel && !f.exists);
    T.busy = true;
    T.err = null;
    render();
    let saved = 0;
    try {
      for (const f of pick) {
        const { exists, sel, key, ...entry } = f;
        await api('/api/library', entry);
        f.exists = true;
        saved += 1;
      }
      T.savedMsg = `${saved === 1 ? '1 canción guardada' : `${saved} canciones guardadas`} en la biblioteca.`;
    } catch (e) {
      T.err = saved ? `Guardé ${saved}; la siguiente falló: ${e.message}` : e.message;
    }
    T.busy = false;
    render();
  },
};

const IN = {
  text: (v) => { S.text = v; save(); },
  pend(v, d) { const p = pendById(d.id); p.text = v; save(); patchPend(p); debounce(`m${p.id}`, 350, () => refreshMatch(p)); },
  q(v) {
    T.q = v;
    T.searchErr = null;
    debounce('q', 250, async () => {
      if (!v.trim()) { T.results = null; return patch('results', searchResults()); }
      T.searching = true;
      try { const r = await api(`/api/search?q=${encodeURIComponent(v.trim())}`); if (T.q === v) T.results = r; } catch (e) { T.searchErr = e.message; }
      T.searching = false;
      patch('results', searchResults());
    });
  },
  songTitle: (v, d) => { T.song[d.v] = v; },
  secText: (v, d) => { T.song.sections.find((s) => String(s.id) === d.id).text = v; },
  sermon(v, d) {
    S.sermon[d.v] = v;
    save();
    if (d.v === 'title') patch('sermon-hint', sermonHint());
    if (d.v !== 'passage') return;
    debounce('pass', 500, async () => {
      const old = S.sermon.items;
      T.passErr = null;
      try {
        const items = await passageItems(v, 'sermon');
        if (S.sermon.passage !== v) return;
        items.forEach((it) => { const o = old.find((x) => x.book === it.book && x.range === it.range); if (o && o._text) it._text = o._text; });
        S.sermon.items = items;
      } catch (e) {
        T.passErr = e.message;
      }
      save();
      patch('pass-err', errBox(T.passErr));
      patch('verses', versesHtml());
    });
  },
  ovr: (v, d) => { S.sermon.items[Number(d.i)]._text = v; save(); },
  rref(v, d) {
    const r = S.readings[d.id];
    r.ref = v;
    save();
    debounce(`r${d.id}`, 500, async () => {
      T.readErr = T.readErr || {};
      delete T.readErr[d.id];
      try {
        const items = await passageItems(v, d.id);
        if (r.ref !== v) return;
        r.items = items;
      } catch (e) {
        r.items = [];
        T.readErr[d.id] = e.message;
      }
      save();
      render();
    });
  },
  rtext: (v, d) => { S.readings[d.id].text = v; save(); },
  name: (v) => { S.output = v; S.outputTouched = true; T.downloaded = false; save(); },
  libq: (v) => { T.libq = v; patch('lib', libList()); },
};

const CH = {
  async photo(el) {
    const file = el.files[0];
    el.value = '';
    if (!file) return;
    if (/hei[cf]/i.test(file.type) || /\.hei[cf]$/i.test(file.name)) {
      T.err = 'HEIC no se puede leer aquí: cambia la cámara a JPG (Ajustes › Cámara › Formatos › Más compatible) o manda una captura.';
      return render();
    }
    try {
      const image = await downscale(file);
      newWeek({ mode: 'img', image });
      save();
      runOcr();
    } catch {
      T.err = 'No pude abrir esa imagen. Prueba con una foto JPG o PNG.';
      render();
    }
  },
  deck(el) { if (el.files[0]) { T.deck = el.files[0]; T.pdf = null; T.err = null; } render(); },
  reviewed(el) { T.reviewed = el.checked; render(); },
  secType(el, d) { T.song.sections.find((s) => String(s.id) === d.id).type = el.value; render(); },
  importSel(el, d) { T.found[Number(d.i)].sel = el.checked; render(); },
  async importDeck(el) {
    const file = el.files[0];
    if (!file) return;
    T.importFile = file;
    T.found = null;
    T.savedMsg = null;
    T.err = null;
    T.busy = true;
    render();
    const fd = new FormData();
    fd.append('deck', file);
    try { T.found = (await api('/api/import-deck', fd)).map((f) => ({ ...f, sel: !f.exists })); } catch (e) { T.err = e.message; }
    T.busy = false;
    render();
  },
};

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (!el || el.disabled) return;
  e.preventDefault();
  A[el.dataset.act](el.dataset, el);
});
document.addEventListener('input', (e) => { const el = e.target.closest('[data-in]'); if (el) IN[el.dataset.in](el.value, el.dataset, el); });
document.addEventListener('change', (e) => { const el = e.target.closest('[data-ch]'); if (el) CH[el.dataset.ch](el, el.dataset); });

onRoute();

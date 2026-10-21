// app.js
"use strict";

/* ====================== conexión con la API ====================== */
// Servido por FastAPI => mismo origen. Abierto como archivo => localhost:8000.
const API = location.protocol.startsWith("http") ? "" : "http://localhost:8000";

/** ID de sesión: lo crea el servidor en una cookie HttpOnly y viaja solo en
 *  cada request. /sesion devuelve un id público (hash de la cookie, no la
 *  cookie) que se guarda únicamente en memoria
 *  (no en localStorage) para mostrarlo y marcar "esta sesión" en el historial. */
let SESSION_ID = "";

// Versiones anteriores guardaban el id de sesión en localStorage: se borra.
try { localStorage.removeItem("session_id"); } catch {}

/** Extrae un mensaje legible del cuerpo de error de FastAPI. */
function mensajeError(cuerpo, status) {
  const d = cuerpo && cuerpo.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map(e => {
      const campo = (e.loc || []).filter(x => x !== "body").join(".");
      return campo ? `${campo}: ${e.msg}` : e.msg;
    }).join("\n");
  }
  return `Error HTTP ${status}`;
}

async function api(ruta, opciones = {}) {
  let r;
  try {
    r = await fetch(API + ruta, { ...opciones, credentials: "same-origin" });
  } catch {
    marcarEstado(false);
    throw new Error("No se pudo contactar la API. ¿Está levantado el servidor en el puerto 8000?");
  }
  marcarEstado(true);
  const texto = await r.text();
  const cuerpo = texto ? JSON.parse(texto) : null;
  if (!r.ok) throw new Error(mensajeError(cuerpo, r.status));
  return cuerpo;
}

const qs = obj => "?" + new URLSearchParams(obj).toString();
const jsonPost = cuerpo => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(cuerpo)
});

/* ====================== utilidades ====================== */
const $ = id => document.getElementById(id);

function fmt(n) {
  if (typeof n !== "number" || !isFinite(n)) return String(n);
  if (Number.isInteger(n)) return String(n);
  return parseFloat(n.toFixed(6)).toString();
}

function toast(titulo, detalle = "", tipo = "") {
  const el = document.createElement("div");
  el.className = "toast " + tipo;
  el.innerHTML = `<div class="t"></div><div class="d"></div>`;
  el.querySelector(".t").textContent = titulo;
  el.querySelector(".d").textContent = detalle;
  if (!detalle) el.querySelector(".d").remove();
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), tipo === "err" ? 7000 : 3500);
}

function marcarEstado(ok) {
  const el = $("estado");
  el.dataset.ok = ok ? "1" : "0";
  el.querySelector("span").textContent = ok ? "API conectada" : "API sin conexión";
}

/* ====================== estado del editor ====================== */
const editor = { datos: [[0, 0], [0, 0]], editandoId: null };

function dims() {
  return { f: editor.datos.length, c: editor.datos[0] ? editor.datos[0].length : 0 };
}

function redimensionar(filas, cols) {
  filas = Math.max(1, Math.min(10, filas));
  cols = Math.max(1, Math.min(10, cols));
  const nuevo = [];
  for (let i = 0; i < filas; i++) {
    const fila = [];
    for (let j = 0; j < cols; j++) {
      fila.push(editor.datos[i] && editor.datos[i][j] !== undefined ? editor.datos[i][j] : 0);
    }
    nuevo.push(fila);
  }
  editor.datos = nuevo;
  pintarEditor();
}

function pintarEditor() {
  const { f, c } = dims();
  $("outFilas").textContent = f;
  $("outCols").textContent = c;

  const g = $("mgrid");
  g.style.gridTemplateColumns = `repeat(${c}, auto)`;
  g.innerHTML = "";

  editor.datos.forEach((fila, i) => fila.forEach((valor, j) => {
    const inp = document.createElement("input");
    inp.type = "number";
    inp.step = "any";
    inp.value = valor;
    inp.dataset.i = i;
    inp.dataset.j = j;
    inp.setAttribute("aria-label", `fila ${i + 1}, columna ${j + 1}`);
    inp.addEventListener("input", () => {
      editor.datos[i][j] = inp.value === "" || isNaN(parseFloat(inp.value)) ? 0 : parseFloat(inp.value);
    });
    inp.addEventListener("focus", () => inp.select());
    inp.addEventListener("keydown", ev => moverFoco(ev, i, j));
    g.appendChild(inp);
  }));
}

function moverFoco(ev, i, j) {
  const { f, c } = dims();
  let di = 0, dj = 0;
  if (ev.key === "ArrowUp") di = -1;
  else if (ev.key === "ArrowDown") di = 1;
  else if (ev.key === "Enter") { dj = 1; }
  else return;
  ev.preventDefault();
  let ni = i + di, nj = j + dj;
  if (nj >= c) { nj = 0; ni++; }
  if (ni < 0 || ni >= f) return;
  const destino = $("mgrid").querySelector(`input[data-i="${ni}"][data-j="${nj}"]`);
  if (destino) destino.focus();
}

function cargarEnEditor(datos, nombre, id) {
  editor.datos = datos.map(fila => fila.slice());
  editor.editandoId = id ?? null;
  $("nombre").value = nombre ?? "";
  $("modoEditor").textContent = id ? `editando #${id}` : "nueva";
  $("btnActualizar").disabled = !id;
  $("btnActualizar").textContent = id ? `Actualizar #${id}` : "Actualizar";
  pintarEditor();
  marcarSeleccion();
}

function leerEditor() {
  const nombre = $("nombre").value.trim();
  if (!nombre) throw new Error("La matriz necesita un nombre.");
  return { nombre, datos: editor.datos.map(f => f.map(Number)) };
}

/* ====================== CRUD ====================== */
let matrices = [];

async function recargar() {
  matrices = await api("/matrices");
  pintarLista();
  pintarSelects();
  $("conteo").textContent = matrices.length;
}

function pintarLista() {
  const cont = $("lista");
  cont.innerHTML = "";
  if (!matrices.length) {
    cont.innerHTML = `<p class="vacio">Sin matrices todavía. Creá una desde el editor.</p>`;
    return;
  }
  for (const m of matrices) {
    const f = m.datos.length, c = m.datos[0] ? m.datos[0].length : 0;
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.id = m.id;
    card.innerHTML = `
      <div class="top">
        <span class="id">#${m.id}</span>
        <span class="nom"></span>
        <span class="dim">${f}×${c}</span>
        <span class="acts">
          <button class="mini" data-act="editar">Editar</button>
          <button class="mini" data-act="a">→ A</button>
          <button class="mini" data-act="b">→ B</button>
          <button class="mini danger" data-act="borrar">Eliminar</button>
        </span>
      </div>
      <div class="preview"></div>`;
    card.querySelector(".nom").textContent = m.nombre;
    card.querySelector(".preview").textContent =
      m.datos.map(fila => "[ " + fila.map(fmt).join("  ") + " ]").join("\n");

    card.querySelector('[data-act="editar"]').onclick = () => abrirParaEditar(m.id);
    card.querySelector('[data-act="a"]').onclick = () => { $("selA").value = m.id; marcarSeleccion(); };
    card.querySelector('[data-act="b"]').onclick = () => { $("selB").value = m.id; marcarSeleccion(); };
    card.querySelector('[data-act="borrar"]').onclick = () => eliminar(m.id, m.nombre);
    cont.appendChild(card);
  }
  marcarSeleccion();
}

function pintarSelects() {
  for (const sid of ["selA", "selB"]) {
    const sel = $(sid);
    const previo = sel.value;
    sel.innerHTML = "";
    if (!matrices.length) {
      sel.innerHTML = `<option value="">— sin matrices —</option>`;
      continue;
    }
    for (const m of matrices) {
      const o = document.createElement("option");
      o.value = m.id;
      o.textContent = `#${m.id} · ${m.nombre} (${m.datos.length}×${m.datos[0].length})`;
      sel.appendChild(o);
    }
    if (matrices.some(m => String(m.id) === previo)) sel.value = previo;
    else sel.selectedIndex = sid === "selB" && matrices.length > 1 ? 1 : 0;
  }
  marcarSeleccion();
}

function marcarSeleccion() {
  const a = $("selA").value, b = $("selB").value;
  for (const card of $("lista").children) {
    if (!card.dataset) continue;
    const id = card.dataset.id;
    card.classList.toggle("sel", id === a || id === b || String(editor.editandoId) === id);
  }
}

async function guardarNueva() {
  try {
    const nueva = await api("/matrices", jsonPost(leerEditor()));
    await recargar();
    cargarEnEditor(nueva.datos, nueva.nombre, nueva.id);
    $("selA").value = nueva.id; marcarSeleccion();
    toast(`Matriz #${nueva.id} creada`, nueva.nombre, "ok");
  } catch (e) { toast("No se pudo crear", e.message, "err"); }
}

async function actualizar() {
  if (!editor.editandoId) return;
  const id = editor.editandoId;
  try {
    const m = await api(`/matrices/${id}`, { ...jsonPost(leerEditor()), method: "PUT" });
    await recargar();
    toast(`Matriz #${id} actualizada`, m.nombre, "ok");
  } catch (e) { toast("No se pudo actualizar", e.message, "err"); }
}

async function abrirParaEditar(id) {
  try {
    const m = await api(`/matrices/${id}`);       // GET /matrices/{id}
    cargarEnEditor(m.datos, m.nombre, m.id);
  } catch (e) { toast("No se pudo abrir", e.message, "err"); }
}

async function eliminar(id, nombre) {
  if (!confirm(`¿Eliminar la matriz #${id} "${nombre}"?`)) return;
  try {
    await api(`/matrices/${id}`, { method: "DELETE" });
    if (editor.editandoId === id) cargarEnEditor(editor.datos, $("nombre").value, null);
    await recargar();
    toast(`Matriz #${id} eliminada`, "", "ok");
  } catch (e) { toast("No se pudo eliminar", e.message, "err"); }
}

/* ====================== operaciones ====================== */
let ultimoResultado = null;

async function operar(op) {
  const a = $("selA").value, b = $("selB").value;
  if (!a) return toast("Elegí una matriz A", "Todavía no hay matrices guardadas.", "err");

  try {
    let datos, etiqueta;
    if (op === "sumar" || op === "multiplicar") {
      if (!b) return toast("Elegí una matriz B", "", "err");
      datos = await api(`/operaciones/${op}${qs({ id1: a, id2: b })}`, { method: "POST" });
      etiqueta = op === "sumar" ? `#${a} + #${b}` : `#${a} × #${b}`;
    } else {
      if (op === "determinante" && matrices.find(m => String(m.id) === a)?.datos.length > 8) {
        toast("Puede tardar", "El determinante se calcula por cofactores; con n>8 es muy costoso.", "");
      }
      datos = await api(`/operaciones/${op}${qs({ id: a })}`);
      etiqueta = op === "transponer" ? `#${a}ᵀ` : `det(#${a})`;
    }
    mostrarResultado(datos, etiqueta);
  } catch (e) {
    mostrarResultado(null, "error");
    toast("Operación rechazada", e.message, "err");
  } finally {
    cargarHistorial();   // el log registra tanto el éxito como el fallo
  }
}

function mostrarResultado(respuesta, etiqueta) {
  const cont = $("resultado");
  cont.innerHTML = "";
  $("tagResultado").textContent = etiqueta;
  $("detalleJson").hidden = !respuesta;
  $("accionesResultado").hidden = true;
  ultimoResultado = null;

  if (!respuesta) {
    cont.innerHTML = `<p class="vacio">La última operación falló. Revisá las dimensiones.</p>`;
    return;
  }
  $("jsonOut").textContent = JSON.stringify(respuesta, null, 2);

  const r = respuesta.resultado;
  if (typeof r === "number") {
    const el = document.createElement("div");
    el.className = "escalar";
    el.textContent = fmt(r);
    cont.appendChild(el);
    return;
  }

  const g = document.createElement("div");
  g.className = "matriz-out";
  g.style.gridTemplateColumns = `repeat(${r[0].length}, auto)`;
  for (const fila of r) for (const v of fila) {
    const celda = document.createElement("div");
    celda.className = "celda";
    celda.textContent = fmt(v);
    g.appendChild(celda);
  }
  cont.appendChild(g);

  ultimoResultado = { datos: r, etiqueta };
  $("accionesResultado").hidden = false;
}

async function guardarResultado() {
  if (!ultimoResultado) return;
  const nombre = prompt("Nombre para la matriz resultado:", ultimoResultado.etiqueta);
  if (!nombre) return;
  try {
    const m = await api("/matrices", jsonPost({ nombre, datos: ultimoResultado.datos }));
    await recargar();
    toast(`Resultado guardado como #${m.id}`, nombre, "ok");
  } catch (e) { toast("No se pudo guardar", e.message, "err"); }
}

/* ====================== log de ejecución (MongoDB) ====================== */
let mongoOk = false;

async function revisarMongo() {
  try {
    const est = await api("/logs/estado");
    mongoOk = est.conectado;
    $("mongoOff").hidden = mongoOk;
    $("mongoErr").textContent = mongoOk ? "" : "La base de datos no responde. Revisá el log del servidor.";
    $("tagMongo").textContent = mongoOk ? "MongoDB" : "desconectado";
    return mongoOk;
  } catch {
    mongoOk = false;
    $("mongoOff").hidden = false;
    $("tagMongo").textContent = "desconectado";
    return false;
  }
}

function filtrosHistorial() {
  const f = {};
  if ($("filtroSesion").value === "mia") f.mia = true;
  if ($("filtroExito").value) f.exitoso = $("filtroExito").value;
  if ($("filtroTipo").value) f.tipo = $("filtroTipo").value;
  return f;
}

async function cargarHistorial() {
  if (!await revisarMongo()) {
    $("logs").innerHTML = `<p class="vacio">El historial requiere MongoDB.</p>`;
    $("resumen").innerHTML = "";
    return;
  }
  try {
    const filtros = filtrosHistorial();
    const [entradas, resumen] = await Promise.all([
      api("/logs" + qs({ ...filtros, limite: 50 })),
      api("/logs/resumen" + (filtros.mia ? qs({ mia: true }) : ""))
    ]);
    pintarResumen(resumen);
    pintarLogs(entradas);
  } catch (e) {
    toast("No se pudo leer el historial", e.message, "err");
  }
}

function pintarResumen(r) {
  const cont = $("resumen");
  cont.innerHTML = "";
  const chips = [
    ["Ejecuciones", r.total, ""],
    ["Exitosas", r.exitosas, "ok"],
    ["Fallidas", r.fallidas, "err"],
    ["Sesiones", r.sesiones, ""],
  ];
  for (const [etiqueta, valor, clase] of chips) {
    const el = document.createElement("div");
    el.className = "chip " + clase;
    el.innerHTML = `<b></b><span></span>`;
    el.querySelector("b").textContent = valor ?? 0;
    el.querySelector("span").textContent = etiqueta;
    cont.appendChild(el);
  }
}

function pintarLogs(entradas) {
  const cont = $("logs");
  cont.innerHTML = "";
  if (!entradas.length) {
    cont.innerHTML = `<p class="vacio">Sin ejecuciones registradas para este filtro.</p>`;
    return;
  }
  for (const l of entradas) {
    const exitoso = l.resultado.exitoso;
    const params = Object.entries(l.operacion.parametros).map(([k, v]) => `${k}=${v}`).join(" ");
    const el = document.createElement("div");
    el.className = "log" + (exitoso ? "" : " fallo");
    el.innerHTML = `
      <div class="cab">
        <span class="op"></span>
        <span class="ts"></span>
        <span class="sid"></span>
        <span class="ms"></span>
      </div>
      <div class="err-msg" hidden></div>
      <details>
        <summary>operación y resultado (JSON)</summary>
        <pre class="json"></pre>
      </details>`;
    el.querySelector(".op").textContent = `${exitoso ? "✓" : "✕"} ${l.operacion.tipo} ${params}`;
    el.querySelector(".ts").textContent = new Date(l.datetime).toLocaleString();
    el.querySelector(".sid").textContent =
      l.session_id === SESSION_ID ? "esta sesión" : l.session_id.slice(0, 8);
    el.querySelector(".ms").textContent = `${fmt(l.duracion_ms)} ms`;
    if (!exitoso) {
      const err = el.querySelector(".err-msg");
      err.hidden = false;
      err.textContent = l.resultado.error;
    }
    el.querySelector(".json").textContent =
      JSON.stringify({ operacion: l.operacion, resultado: l.resultado }, null, 2);
    cont.appendChild(el);
  }
}

/* ====================== eventos ====================== */
document.querySelectorAll("[data-dim]").forEach(btn => btn.onclick = () => {
  const { f, c } = dims();
  const paso = Number(btn.dataset.paso);
  redimensionar(btn.dataset.dim === "filas" ? f + paso : f,
                btn.dataset.dim === "cols" ? c + paso : c);
});

$("btnGuardar").onclick = guardarNueva;
$("btnActualizar").onclick = actualizar;
$("btnRecargar").onclick = () => recargar().catch(e => toast("Error", e.message, "err"));
$("btnGuardarRes").onclick = guardarResultado;
$("btnEditarRes").onclick = () => {
  if (ultimoResultado) cargarEnEditor(ultimoResultado.datos, ultimoResultado.etiqueta, null);
};

$("btnNueva").onclick = () => cargarEnEditor([[0, 0], [0, 0]], "", null);
$("btnCeros").onclick = () => {
  editor.datos = editor.datos.map(f => f.map(() => 0));
  pintarEditor();
};
$("btnIdentidad").onclick = () => {
  const { f, c } = dims();
  const n = Math.min(f, c);
  redimensionar(n, n);
  editor.datos = editor.datos.map((fila, i) => fila.map((_, j) => (i === j ? 1 : 0)));
  pintarEditor();
};
$("btnAleatoria").onclick = () => {
  editor.datos = editor.datos.map(f => f.map(() => Math.floor(Math.random() * 19) - 9));
  pintarEditor();
};

$("btnCargarJson").onclick = () => {
  try {
    const datos = JSON.parse($("jsonIn").value);
    if (!Array.isArray(datos) || !datos.length || !datos.every(Array.isArray))
      throw new Error("Se espera una lista de listas, p. ej. [[1,2],[3,4]].");
    const largos = new Set(datos.map(f => f.length));
    if (largos.size !== 1 || datos[0].length === 0)
      throw new Error("Todas las filas deben tener el mismo largo.");
    if (!datos.every(f => f.every(v => typeof v === "number" && isFinite(v))))
      throw new Error("Todos los valores deben ser números.");
    if (datos.length > 10 || datos[0].length > 10)
      throw new Error("El editor admite hasta 10×10.");
    editor.datos = datos;
    pintarEditor();
    toast("JSON cargado", `${datos.length}×${datos[0].length}`, "ok");
  } catch (e) { toast("JSON inválido", e.message, "err"); }
};
$("btnVolcarJson").onclick = () => { $("jsonIn").value = JSON.stringify(editor.datos); };

document.querySelectorAll("[data-op]").forEach(b => b.onclick = () => operar(b.dataset.op));
$("selA").onchange = marcarSeleccion;
$("selB").onchange = marcarSeleccion;

$("btnRecargarLogs").onclick = cargarHistorial;
$("btnReintentar").onclick = cargarHistorial;
["filtroSesion", "filtroExito", "filtroTipo"].forEach(id => $(id).onchange = cargarHistorial);

async function cargarSesion() {
  try {
    SESSION_ID = (await api("/sesion")).id;
    $("sesion").textContent = "sesión: " + SESSION_ID.slice(0, 8);
  } catch {
    $("sesion").textContent = "sesión: —";
  }
}

$("sesion").onclick = async () => {
  if (!SESSION_ID) return;
  try {
    await navigator.clipboard.writeText(SESSION_ID);
    toast("ID de sesión copiado", SESSION_ID, "ok");
  } catch { toast("ID de sesión", SESSION_ID); }
};

$("btnTema").onclick = () => {
  const nuevo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = nuevo;
  try { localStorage.setItem("tema", nuevo); } catch {}
};
try {
  const guardado = localStorage.getItem("tema");
  if (guardado) document.documentElement.dataset.theme = guardado;
  else if (matchMedia("(prefers-color-scheme: light)").matches)
    document.documentElement.dataset.theme = "light";
} catch {}

/* ====================== arranque ====================== */
pintarEditor();
cargarSesion()
  .then(recargar)
  .then(cargarHistorial)
  .catch(e => {
    pintarLista();
    pintarSelects();
    toast("Sin conexión con la API", e.message, "err");
  });

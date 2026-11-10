// viewer.js
"use strict";

/** Cambia el texto y el color (por clase CSS, no style en línea) de un indicador. */
function marcar(el, texto, estado) {
  el.textContent = texto;
  el.className = "estado " + estado;
}

// 1. Inicialización de la Escena 3D
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

camera.position.set(0, 0, 5);

// Grupo contenedor cuya matriz será controlada por FastAPI
const modelGroup = new THREE.Group();
modelGroup.matrixAutoUpdate = false; // Importante: deshabilitamos auto-update para usar la matriz de la API
scene.add(modelGroup);

const modeloSelect = document.getElementById('modelo-select');
const puntosEl = document.getElementById('point-count');
const figuraEl = document.getElementById('figura-nombre');

/** Nombre visible de un modelo CSV ("dona" -> "Dona"). */
function capitalizar(nombre) {
  return nombre.charAt(0).toUpperCase() + nombre.slice(1);
}

/**
 * Muestra una nube de puntos [[x, y, z], ...].
 * Si la cantidad de puntos no cambia (el caso del slider) se reutiliza la
 * geometría y solo se actualizan las posiciones.
 */
function mostrarPuntos(vertices) {
  puntosEl.textContent = vertices.length;
  const coords = new Float32Array(vertices.flat());
  const actual = modelGroup.children[0];

  if (actual && actual.geometry.attributes.position.count === vertices.length) {
    actual.geometry.attributes.position.array.set(coords);
    actual.geometry.attributes.position.needsUpdate = true;
    actual.geometry.computeBoundingSphere();
    return;
  }

  // Quitar el modelo anterior y liberar su memoria en la GPU
  for (const hijo of [...modelGroup.children]) {
    modelGroup.remove(hijo);
    hijo.geometry.dispose();
    hijo.material.dispose();
  }
  if (vertices.length === 0) return;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(coords, 3));
  const material = new THREE.PointsMaterial({ color: 0x00ff88, size: 0.08 });
  modelGroup.add(new THREE.Points(geometry, material));
}

// Qué se está mostrando: un modelo CSV o el morph. Las respuestas del morph
// que lleguen después de elegir un CSV se descartan.
let vista = 'csv';

// 2. Cargar los puntos del CSV desde FastAPI
async function cargarCSV(modelo) {
  vista = 'csv';
  try {
    const response = await fetch(`${location.origin}/api/modelo-csv?modelo=${encodeURIComponent(modelo)}`);
    const data = await response.json();
    if (vista !== 'csv') return;
    mostrarPuntos(data.vertices ?? []);
    figuraEl.textContent = capitalizar(modelo);
  } catch (err) {
    console.error("Error al cargar el CSV:", err);
  }
}

async function iniciarModelos() {
  try {
    const modelos = await (await fetch(`${location.origin}/api/modelos`)).json();
    for (const nombre of modelos) {
      modeloSelect.add(new Option(capitalizar(nombre), nombre));
    }
    modeloSelect.addEventListener('change', () => cargarCSV(modeloSelect.value));
    cargarCSV(modeloSelect.value);
  } catch (err) {
    console.error("Error al listar los modelos:", err);
  }
}

iniciarModelos();

// 3. Conexión WebSocket: matriz 4x4 de transformación y relevo del morph
const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${wsProto}://${location.host}/ws/transform`);
const statusEl = document.getElementById('ws-status');
const calcEl = document.getElementById('calc-status');
// Solo se envía un cuadro nuevo cuando la calculadora respondió el anterior
let esperandoRespuesta = false;

function enviar(mensaje) {
  if (ws.readyState !== WebSocket.OPEN) return false;
  ws.send(JSON.stringify(mensaje));
  return true;
}

// ---------- Morph dona -> taza ----------
// 100 x 100 = 10,000 puntos, igual que dona.csv
const RESOLUCION_MORPH = 100;
const slider = document.getElementById('morph-slider');
const tEl = document.getElementById('morph-t');
const msgEl = document.getElementById('morph-msg');
const nombreInput = document.getElementById('figura-input');
const figurasSelect = document.getElementById('figuras-select');

function mensaje(texto, estado = '') {
  msgEl.textContent = texto;
  msgEl.className = 'mensaje ' + estado;
}

/** t del slider, siempre dentro de [0, 1]. */
function leerT() {
  const t = Number(slider.value);
  return Number.isFinite(t) ? Math.min(1, Math.max(0, t)) : 0;
}

// Un solo morph en vuelo: si el slider se mueve mientras tanto, se guarda el
// último valor y se pide cuando llegue la respuesta.
let morphEnVuelo = false;
let tPendiente = null;

function pedirMorph(t) {
  vista = 'morph';
  tPendiente = t;
  enviarMorphPendiente();
}

function enviarMorphPendiente() {
  if (morphEnVuelo || tPendiente === null) return;
  if (enviar({ tipo: 'morph', t: tPendiente, resolucion: RESOLUCION_MORPH })) {
    morphEnVuelo = true;
    tPendiente = null;
  }
}

slider.addEventListener('input', () => {
  const t = leerT();
  tEl.textContent = t.toFixed(2);
  pedirMorph(t);
});

document.getElementById('guardar-figura').addEventListener('click', () => {
  const nombre = nombreInput.value.trim();
  if (!nombre) {
    mensaje('Escribe un nombre para la figura', 'error');
    return;
  }
  enviar({ tipo: 'guardar_figura', nombre, t: leerT(), resolucion: RESOLUCION_MORPH });
});

document.getElementById('cargar-figura').addEventListener('click', () => {
  if (!figurasSelect.value) {
    mensaje('Elige una figura guardada', 'error');
    return;
  }
  vista = 'morph';
  tPendiente = null; // la figura cargada manda sobre un morph que estuviera pendiente
  enviar({ tipo: 'cargar_figura', nombre: figurasSelect.value });
});

function mostrarListaFiguras(figuras) {
  const elegida = figurasSelect.value;
  figurasSelect.length = 1; // deja solo la opción vacía
  for (const f of figuras) {
    figurasSelect.add(new Option(`${f.nombre} (t = ${f.t.toFixed(2)})`, f.nombre));
  }
  figurasSelect.value = [...figurasSelect.options].some((o) => o.value === elegida) ? elegida : '';
}

/** Respuesta "morph": la de un t del slider o la de una figura guardada (trae nombre). */
function recibirMorph(data) {
  const cargada = typeof data.nombre === 'string';
  if (!cargada) {
    morphEnVuelo = false;
  }
  if (vista === 'morph') {
    mostrarPuntos(data.vertices);
    figuraEl.textContent = cargada ? data.nombre : data.figura;
    if (cargada) {
      slider.value = data.t;
      tEl.textContent = Number(data.t).toFixed(2);
      mensaje(`Figura "${data.nombre}" cargada`, 'ok');
    }
  }
  enviarMorphPendiente();
}

// ---------- WebSocket ----------
ws.onopen = () => {
  marcar(statusEl, "Conectado", "ok");
  enviar({ tipo: 'listar_figuras' });
};

ws.onerror = () => {
  marcar(statusEl, "Error de conexión", "error");
};

ws.onclose = () => {
  if (!statusEl.classList.contains("error")) marcar(statusEl, "Desconectado", "error");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  const tipo = data.tipo ?? 'transform';

  if (data.status === "error") {
    if (tipo === 'transform') esperandoRespuesta = false;
    if (tipo === 'morph') {
      morphEnVuelo = false;
      enviarMorphPendiente();
    }
    // La caída de la calculadora se informa una sola vez, en su indicador
    if (data.error === "Calculadora no disponible") marcar(calcEl, data.error, "error");
    else if (tipo !== 'transform') mensaje(data.error, 'error');
    console.error(data.error);
    return;
  }

  switch (tipo) {
    case 'transform':
      esperandoRespuesta = false;
      // Aplicar la matriz 4x4 calculada por la Calculadora de Matrices al objeto 3D
      modelGroup.matrix.fromArray(data.matrix);
      marcar(calcEl, "Conectada", "ok");
      break;
    case 'morph':
      recibirMorph(data);
      break;
    case 'figura_guardada':
      figuraEl.textContent = data.nombre;
      mensaje(`Figura "${data.nombre}" guardada`, 'ok');
      nombreInput.value = '';
      enviar({ tipo: 'listar_figuras' });
      break;
    case 'figuras':
      mostrarListaFiguras(data.figuras);
      break;
  }
};

// 4. Bucle de Animación y Envío de Parámetros
let angle = 0;
function animate() {
  requestAnimationFrame(animate);

  // Si el WebSocket está abierto, enviamos ángulos/traslaciones continuas
  if (ws.readyState === WebSocket.OPEN && !esperandoRespuesta) {
    esperandoRespuesta = true;
    angle += 0.8;
    ws.send(JSON.stringify({
      tx: Math.sin(angle * 0.02) * 0.5,
      ty: 0,
      tz: 0,
      rx: angle,
      ry: angle * 0.5,
      rz: 0
    }));
  }

  renderer.render(scene, camera);
}

animate();

// Ajustar renderizador al cambiar tamaño de la ventana
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

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

// 2. Cargar los puntos del CSV desde FastAPI
const modeloSelect = document.getElementById('modelo-select');

async function cargarCSV(modelo) {
  try {
    const response = await fetch(`${location.origin}/api/modelo-csv?modelo=${encodeURIComponent(modelo)}`);
    const data = await response.json();
    document.getElementById('point-count').textContent = data.total_puntos ?? 0;

    // Quitar el modelo anterior y liberar su memoria en la GPU
    for (const hijo of [...modelGroup.children]) {
      modelGroup.remove(hijo);
      hijo.geometry.dispose();
      hijo.material.dispose();
    }

    if (data.vertices && data.vertices.length > 0) {
      // Aplanar coordenadas [[x,y,z], ...] -> [x,y,z, x,y,z, ...]
      const vertices = new Float32Array(data.vertices.flat());

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));

      // Estilo de la nube de puntos
      const material = new THREE.PointsMaterial({ color: 0x00ff88, size: 0.08 });
      const pointCloud = new THREE.Points(geometry, material);

      modelGroup.add(pointCloud);
    }
  } catch (err) {
    console.error("Error al cargar el CSV:", err);
  }
}

async function iniciarModelos() {
  try {
    const modelos = await (await fetch(`${location.origin}/api/modelos`)).json();
    for (const nombre of modelos) {
      modeloSelect.add(new Option(nombre.charAt(0).toUpperCase() + nombre.slice(1), nombre));
    }
    modeloSelect.addEventListener('change', () => cargarCSV(modeloSelect.value));
    cargarCSV(modeloSelect.value);
  } catch (err) {
    console.error("Error al listar los modelos:", err);
  }
}

iniciarModelos();

// 3. Conexión WebSocket para enviar parámetros y recibir la Matriz 4x4
const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${wsProto}://${location.host}/ws/transform`);
const statusEl = document.getElementById('ws-status');
const calcEl = document.getElementById('calc-status');
// Solo se envía un cuadro nuevo cuando la calculadora respondió el anterior
let esperandoRespuesta = false;

ws.onopen = () => {
  marcar(statusEl, "Conectado", "ok");
};

ws.onerror = () => {
  marcar(statusEl, "Error de conexión", "error");
};

ws.onclose = () => {
  if (!statusEl.classList.contains("error")) marcar(statusEl, "Desconectado", "error");
};

ws.onmessage = (event) => {
  esperandoRespuesta = false;
  const data = JSON.parse(event.data);
  if (data.matrix) {
    // Aplicar la matriz 4x4 calculada por la Calculadora de Matrices al objeto 3D
    modelGroup.matrix.fromArray(data.matrix);
    marcar(calcEl, "Conectada", "ok");
  } else if (data.status === "error") {
    marcar(calcEl, data.error || "No disponible", "error");
    console.error(data.error);
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

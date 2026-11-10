# TecDeSoftware — Calculadora de Matrices + Visualizador 3D (morph dona → taza)

Dos servicios FastAPI que trabajan juntos:

| Proyecto | Qué hace | Puerto |
|---|---|---|
| [`calculadora-de-matrices/`](calculadora-de-matrices/) | API de matrices (suma, producto, transformaciones 4×4), **cálculo del morph dona → taza** y **figuras guardadas con nombre**. Guarda logs y figuras en MongoDB. | 8000 |
| [`modelado-3d/`](modelado-3d/) | Visor 3D (Three.js) que se comunica por **WebSocket** con su backend, el cual releva las peticiones a la calculadora. | 8001 |
| MongoDB | Logs de ejecución y figuras guardadas. | 27017 |
| n8n | Automatizaciones (opcional). | 5678 (solo localhost) |

```
 Navegador (visor /view)
      │  WebSocket /ws/transform  {tipo: "morph", t, resolucion}
      ▼
 modelado-3d :8001  ── valida y releva ──►  calculadora :8000  ──►  MongoDB
      ▲                                         │  V(t) = (1 − t)·Dona + t·Taza
      └──────── vértices [[x, y, z], …] ◄───────┘
```

---

## 1. Requisitos

- **Docker Desktop** (con Docker Compose v2). En Windows debe estar **abierto** antes de correr cualquier comando de `docker`.
- Solo para correr las pruebas: **Python 3.12+**.

## 2. Levantar el sistema

Desde la raíz del repositorio:

```bash
docker compose up -d --build
```

Esto levanta la calculadora, MongoDB, el visor y n8n, y conecta los servicios entre sí. La primera vez tarda unos minutos mientras se descargan las imágenes.

Comprueba que todo esté arriba (todos deben aparecer como `healthy` o `Up`):

```bash
docker compose ps
```

| Abrir en el navegador | Para qué |
|---|---|
| <http://localhost:8001/view> | **Visor 3D con el morph dona → taza** |
| <http://localhost:8000> | Interfaz web de la calculadora de matrices |
| <http://localhost:8001> | Estado del backend del visor (JSON) |

Otros comandos útiles:

```bash
docker compose logs -f api matrix-api   # ver logs de la calculadora y del visor
docker compose restart api matrix-api   # aplicar cambios de código (el código se monta como volumen, pero no hay recarga automática)
docker compose down                     # detener todo (las figuras y los logs se conservan en el volumen de Mongo)
docker compose down -v                  # detener y BORRAR los datos de Mongo
```

### Configuración opcional

- `SERVICIO_TOKEN` (en el `.env` de cada proyecto): es un token compartido que permite a modelado-3d identificarse ante la calculadora como sesión `modelado-3d` en los logs. Debe tener el mismo valor en ambos proyectos. Si falta, todo funciona igual, pero las peticiones del visor aparecen en los logs con una sesión anónima.
- `HABILITAR_DOCS=1`: expone `/docs` (Swagger) en ambos servicios. Está comentado en los `docker-compose` y se recomienda solo para desarrollo.

## 3. Uso: el visor y el morph

Abre <http://localhost:8001/view>. El panel muestra:

- **Estado WebSocket / Calculadora de Matrices**: deben aparecer en verde (`Conectado` / `Conectada`).
- **Modelo**: los modelos CSV originales (dona, esfera, cubo).
- **Figura**: el nombre de lo que se está mostrando: `Dona`, `Taza`, `Dona → Taza (NN%)`, un modelo CSV o el nombre de una figura guardada.
- **Slider Dona ↔ Taza** (de **0 a 1** únicamente, en pasos de 0.01): al moverlo, el visor pide el morph por el WebSocket y la calculadora devuelve los vértices. La resolución es 100 × 100 = **10,000 puntos**, igual que `dona.csv`. Con `t = 0` se obtienen exactamente los puntos de la dona y con `t = 1`, los de la taza.
- **Guardar**: escribe un nombre y guarda la figura que se muestra en ese momento (su `t`).
- **Cargar**: elige una figura guardada. El visor la muestra con su nombre y mueve el slider a su `t`.

> La dona y la taza son superficies con un solo agujero (género 1): durante el morph, el agujero de la dona se convierte en el de la oreja de la taza.

### Reglas de validación

| Dato | Regla | Si no se cumple |
|---|---|---|
| `t` | número entre 0 y 1 (incluidos) | 422 en la API · mensaje de error en el visor |
| `resolucion` | entero entre 4 y 150 (por defecto **100** = 10,000 puntos) | 422 · mensaje de error |
| `nombre` de figura | 1 a 50 caracteres: letras, números, espacio, `.`, `-`, `_`; debe empezar con letra o número. Se ignoran los espacios sobrantes. | 422 · mensaje de error |
| nombre repetido | único sin distinguir mayúsculas (`Mi Taza` = `mi taza`) | 409 "ya existe una figura…" |
| MongoDB caído | el morph sigue funcionando; guardar o consultar figuras no | 503 "MongoDB no disponible…" |
| calculadora caída | el visor no se congela y muestra "Calculadora no disponible" | — |

## 4. Uso: la API

### Morph (calculadora, puerto 8000)

```bash
curl -X POST http://localhost:8000/operaciones/morph \
     -H "Content-Type: application/json" \
     -d '{"t": 0.5, "resolucion": 100}'
```

```json
{"t": 0.5, "resolucion": 100, "figura": "Dona → Taza (50%)",
 "total_vertices": 10000, "vertices": [[x, y, z], ...]}
```

### Figuras guardadas (calculadora, puerto 8000)

| Método y ruta | Descripción | Respuestas |
|---|---|---|
| `POST /figuras` `{"nombre", "t", "resolucion"?}` | Calcula el morph y lo guarda con ese nombre | 201 · 409 · 422 · 503 |
| `GET /figuras` | Lista de figuras (sin vértices), las más nuevas primero | 200 · 503 |
| `GET /figuras/{nombre}` | Figura completa con sus vértices | 200 · 404 · 503 |
| `DELETE /figuras/{nombre}` | Elimina la figura | 200 · 404 · 503 |

```bash
curl -X POST http://localhost:8000/figuras -H "Content-Type: application/json" \
     -d '{"nombre": "mi taza", "t": 1}'
curl http://localhost:8000/figuras
curl "http://localhost:8000/figuras/mi%20taza"
```

### WebSocket del visor (modelado-3d, `ws://localhost:8001/ws/transform`)

Solo acepta conexiones desde el origen del visor (`http://localhost:8001`). Cada mensaje es un objeto JSON y cada respuesta incluye `tipo` y `status` (`ok` o `error`, este último con `error`):

| Se envía | Se recibe |
|---|---|
| `{"tx", "ty", "tz", "rx", "ry", "rz"}` (sin `tipo`) | `{"tipo": "transform", "matrix": [16 valores column-major]}` |
| `{"tipo": "morph", "t": 0.5, "resolucion": 100}` | `{"tipo": "morph", "figura", "total_vertices", "vertices", ...}` |
| `{"tipo": "guardar_figura", "nombre", "t", "resolucion"?}` | `{"tipo": "figura_guardada", "nombre", ...}` (sin vértices) |
| `{"tipo": "cargar_figura", "nombre"}` | `{"tipo": "morph", "nombre", "t", "vertices", ...}` |
| `{"tipo": "listar_figuras"}` | `{"tipo": "figuras", "figuras": [...]}` |

Un mensaje inválido (JSON mal formado, valores fuera de rango o `tipo` desconocido) recibe una respuesta de error y la conexión **sigue abierta**.

## 5. Pruebas

Instala las dependencias una sola vez en un entorno virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # en Git Bash / Linux / macOS: source .venv/Scripts/activate  (o .venv/bin/activate)
pip install -r tests/requirements.txt
playwright install chromium         # solo para las pruebas E2E
```

### Pruebas en proceso — `tests/` (no requieren Docker)

Cargan la calculadora y el visor en memoria. El WebSocket de modelado-3d se prueba contra la calculadora **real**, servida en proceso, y MongoDB se simula, de modo que nunca se toca la base real.

```bash
python -m pytest tests
```

| Archivo | Cubre |
|---|---|
| `test_morph_servicio.py` | Cálculo del morph: N² vértices, 10,000 por defecto, coincidencia con `dona.csv`, geometría de la taza, interpolación lineal y validaciones |
| `test_morph_endpoint.py` | `POST /operaciones/morph`: respuestas, límites y errores 422 |
| `test_figuras.py` | `/figuras`: guardar, consultar, listar y eliminar; errores 409, 404 y 422; 503 sin MongoDB |
| `test_ws_morph.py` | Relevo por WebSocket: morph, figuras, mensajes malformados, calculadora o Mongo caídos, origen rechazado |
| `test_visor.py` | Slider de 0 a 1, etiqueta de la figura y CSP |

### Pruebas E2E con navegador — `tests_e2e/` (requieren el sistema levantado)

```bash
docker compose up -d --build
python -m pytest tests_e2e
```

`test_visor.py::test_visor_sin_calculadora_muestra_error_y_no_se_congela` necesita la calculadora **detenida**. Con el sistema completo se omite (`skipped`); para ejecutarla:

```bash
docker compose stop api
python -m pytest tests_e2e/test_visor.py
docker compose start api
```

Las URLs se pueden cambiar con las variables `CALCULADORA_URL` y `VISOR_URL`.

## 6. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `failed to connect to the docker API … dockerDesktopLinuxEngine` | Docker Desktop no está abierto. Ábrelo, espera a que diga *Engine running* y repite el comando. |
| `port is already allocated` | Otro programa usa el puerto 8000, 8001 o 27017. Ciérralo o cambia el puerto en el `docker-compose`. |
| El visor dice "Calculadora no disponible" | El servicio `api` está detenido o arrancando: revisa `docker compose ps` y `docker compose logs api`. |
| Guardar una figura responde 503 | MongoDB no responde: revisa `docker compose ps mongo`. El morph funciona igual. |
| Los cambios de código no se reflejan | Ejecuta `docker compose restart api matrix-api`. Los archivos del visor (`static/`) se sirven sin caché: basta con recargar la página. |

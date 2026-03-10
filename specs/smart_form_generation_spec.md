# SDD — Smart Form Generation v0.18.0

**Sprint 13 · Estado:** Draft
**Fecha:** 2026-03-10
**Dependencias:** Sprint 9 (FormIngestor), Sprint 12 (DevToolsPanel)

---

## 1. Problema

El Google Form generado automáticamente tiene tres deficiencias:

1. **Campo de fechas como texto libre** — el cómico escribe lo que quiere, dificultando el scoring y la ingesta.
2. **Sin descripción contextual** — el form no dice a qué open mic corresponde ni dónde es.
3. **Color de fondo siempre igual** — todos los forms son visualmente idénticos.

Además, la ficha del open mic carece del campo **cadencia** (frecuencia del evento), necesario para calcular las fechas y para la descripción del form.

---

## 2. Cambios por capa

### 2.1 DB — `config.info` (sin migración de schema)

Dos nuevos campos opcionales en el JSONB `config.info` del open mic:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `cadencia` | string | `"semanal"` \| `"quincenal"` \| `"mensual"` \| `"unico"` |
| `fecha_inicio` | string ISO `YYYY-MM-DD` | Referencia para calcular fechas (quincenal/mensual) |
| `form_bg_color` | string hex `#RRGGBB` | Color asignado al crear el form, persistido para referencia |

No se requiere migración SQL — son claves nuevas dentro del JSONB existente, guardadas via RPC `update_open_mic_config_keys`.

---

### 2.2 Frontend — `OpenMicDetail.jsx` (tab Info)

**Añadir al editor de info del open mic:**

#### Selector `cadencia`
```
Label: "Frecuencia"
Tipo: select / radio pills
Opciones:
  semanal      → "Semanalmente"
  quincenal    → "Quincenalmente"
  mensual      → "Mensualmente"
  unico        → "Evento único"
```
- Se persiste en `config.info.cadencia` via RPC `update_open_mic_config_keys`.
- Se muestra en el bloque de info del open mic (junto a día y hora).

#### Campo `fecha_inicio`
```
Label: "Fecha de inicio"
Tipo: <input type="date">
Visible: siempre (necesario para quincenal y mensual)
```
- Se persiste en `config.info.fecha_inicio` (string ISO).
- Usado por el backend para calcular fechas en el form.

#### Visualización en `InfoRow`
```
cadencia=semanal   → "Miércoles · 20:00 · Semanal"
cadencia=quincenal → "Jueves · 21:00 · Quincenal (desde 05-03-26)"
cadencia=unico     → "Evento único · 12-03-26"
```

---

### 2.3 Backend — `webhook_listener.py`

#### Endpoint `POST /api/open-mic/create-form`

Cambio: leer el `config` completo del open mic desde Supabase en el endpoint y pasarlo al builder como parámetro `info`.

```python
# Antes
result = builder.create_form_for_open_mic(open_mic_id, nombre)

# Después
info = existing.data.get("config", {}).get("info", {})
result = builder.create_form_for_open_mic(open_mic_id, nombre, info)
```

El endpoint también persiste el `form_bg_color` generado en el config:
```python
current_config["form"]["bg_color"] = result.bg_color
```

---

### 2.4 Backend — `google_form_builder.py`

#### `FormCreationResult`
```python
@dataclass
class FormCreationResult:
    form_id:   str
    form_url:  str
    sheet_id:  str
    sheet_url: str
    bg_color:  str  # NUEVO: hex color aplicado al form
```

#### `create_form_for_open_mic(open_mic_id, nombre, info={})`
```python
def create_form_for_open_mic(self, open_mic_id, nombre, info=None):
    info = info or {}
    bg_color  = self._random_form_color()
    form_id   = self._create_form(nombre, info, bg_color)
    self._add_questions(form_id, info)
    sheet_id  = self._get_linked_sheet_id(form_id, nombre)
    self._inject_open_mic_id_column(sheet_id, open_mic_id)
    try:
        self.deploy_submit_webhook(form_id, open_mic_id, bg_color)
    except Exception as e:
        print(f"[GoogleFormBuilder] Apps Script no desplegado: {e}")
    ...
    return FormCreationResult(..., bg_color=bg_color)
```

#### `_random_form_color() -> str`

Paleta curada de 12 colores vivos pero no agresivos:
```python
_FORM_BG_PALETTE = [
    "#F28B82", "#FBBC04", "#FFF475", "#CCFF90",
    "#A8DAB5", "#CBF0F8", "#AECBFA", "#D7AEFB",
    "#FDCFE8", "#E6C9A8", "#E8EAED", "#FF8A65",
]
```
Se elige uno aleatoriamente con `random.choice`.

#### `_create_form(nombre, info, bg_color) -> str`

Añade descripción al form al crearlo:
```python
def _build_description(nombre, info) -> str:
    parts = [f"Formulario de inscripción al Open mic de comedia {nombre}"]
    if info.get("local"):
        parts.append(f"en {info['local']}")
    if info.get("direccion"):
        parts.append(f"en la calle {info['direccion']}")
    if info.get("dia_semana"):
        cadencia_label = {
            "semanal":    "semanalmente",
            "quincenal":  "cada dos semanas",
            "mensual":    "mensualmente",
            "unico":      "",
        }.get(info.get("cadencia", ""), "")
        dia_str = info["dia_semana"]
        if cadencia_label:
            dia_str += f" {cadencia_label}"
        parts.append(f"los {dia_str}")
    return " ".join(parts)
```

Llamada a la Forms API para crear el form con descripción:
```python
body = {
    "info": {
        "title": f"Solicitudes — {nombre}",
        "description": self._build_description(nombre, info),
    }
}
result = self._forms.forms().create(body=body).execute()
```

#### `_build_date_options(info) -> list[str]`

Calcula las fechas seleccionables según cadencia. Devuelve lista de strings `"dd-MM-YY"`.

```
cadencia = semanal:
  - Obtener todos los [dia_semana] del MES ACTUAL
  - Filtrar >= hoy
  - Formato dd-MM-YY

cadencia = quincenal:
  - Partir de fecha_inicio (o hoy si no hay)
  - Avanzar de 14 en 14 días hasta tener 4 fechas >= hoy

cadencia = mensual:
  - Partir de fecha_inicio (o hoy)
  - Próximas 3 fechas, sumando 1 mes cada vez (mismo día del mes)
  - Si el día no existe en ese mes (ej: 31 de febrero), usar último día del mes

cadencia = unico (o sin cadencia):
  - Devuelve []
```

Mapping `dia_semana` → `weekday()`:
```python
_DIA_SEMANA_MAP = {
    "Lunes": 0, "Martes": 1, "Miércoles": 2, "Miercoles": 2,
    "Jueves": 3, "Viernes": 4, "Sábado": 5, "Sabado": 5, "Domingo": 6,
}
```

#### `_add_questions(form_id, info) -> None`

Cambia la pregunta de fechas:
- **Antes**: `textQuestion` "¿Qué fechas te vienen bien?"
- **Después**: `choiceQuestion` tipo `CHECKBOX` con las opciones calculadas por `_build_date_options(info)`
- **Si `cadencia == 'unico'`** (o `_build_date_options` devuelve `[]`): omitir la pregunta de fechas completamente.

Orden de preguntas resultante:
1. Nombre artístico (text)
2. Instagram (text)
3. WhatsApp (text)
4. ¿Cuántas veces has actuado? (radio)
5. ¿Qué fechas te vienen bien? (checkbox, **omitida si evento único**)
6. ¿Estarías disponible de última hora? (radio)
7. ¿Tienes algún show próximo? (text paragraph)
8. ¿Cómo nos conociste? (text)

#### `deploy_submit_webhook(form_id, open_mic_id, bg_color)`

Añadir al final de la función `setup()` en `_APPS_SCRIPT_TEMPLATE`:
```javascript
function setup() {
  // ... triggers existentes ...
  FormApp.openById("{form_id}").setBackgroundColor("{bg_color}");
}
```

---

## 3. Flujo end-to-end

```
Host configura open mic:
  → añade cadencia + fecha_inicio en la ficha
  → guarda via update_open_mic_config_keys

Host pulsa "Crear formulario":
  → POST /api/open-mic/create-form
  → endpoint lee config completo del open mic
  → llama builder.create_form_for_open_mic(id, nombre, info)
     ├─ _random_form_color()          → bg_color
     ├─ _create_form(nombre,info,_)   → form con descripción
     ├─ _build_date_options(info)     → fechas calculadas
     ├─ _add_questions(form_id,info)  → preguntas incl. fechas como checkbox
     └─ deploy_submit_webhook(...)    → Apps Script aplica bg_color al form
  → persiste form_id, form_url, sheet_id, bg_color en config
  → devuelve FormCreationResult
```

---

## 4. Tests

### Backend (pytest)

| Test | Descripción |
|------|-------------|
| `test_build_date_options_semanal` | Devuelve todos los [dia_semana] del mes actual >= hoy |
| `test_build_date_options_quincenal` | Devuelve 4 fechas cada 14 días desde fecha_inicio |
| `test_build_date_options_mensual` | Devuelve 3 fechas mensuales desde fecha_inicio |
| `test_build_date_options_unico` | Devuelve lista vacía |
| `test_build_description_completa` | Genera descripción con local, dirección, cadencia |
| `test_build_description_parcial` | Sin local ni dirección, solo nombre |
| `test_random_form_color` | Devuelve hex de la paleta |
| `test_add_questions_omite_fecha_unico` | No incluye pregunta de fechas si unico |
| `test_add_questions_checkbox_semanal` | Incluye pregunta tipo CHECKBOX con fechas |

### Frontend (Vitest)

| Test | Descripción |
|------|-------------|
| `renders_cadencia_selector` | Selector de frecuencia visible en tab Info |
| `persists_cadencia_on_save` | Llama a RPC con cadencia correcto |
| `shows_fecha_inicio_field` | Campo fecha_inicio visible |

---

## 5. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `backend/src/core/google_form_builder.py` | Mayor: descripción, fechas calculadas, color, info param |
| `backend/src/triggers/webhook_listener.py` | Menor: pasar info al builder, guardar bg_color |
| `frontend/src/components/OpenMicDetail.jsx` | Menor: selector cadencia + campo fecha_inicio |
| `backend/tests/core/test_google_form_builder.py` | Nuevo: 9 tests |
| `frontend/src/test/OpenMicDetail.test.jsx` | Menor: 3 tests nuevos |

---

## 6. Avisos de formulario desactualizado

### 6.1 Info del open mic cambiada con form existente

**Trigger:** el host guarda cualquier campo de info (cadencia, local, dirección, dia_semana, fecha_inicio) y ya existe un form creado (`config.form.form_id` presente).

#### 6.1.1 Popup inmediato al guardar

Al detectar el cambio en el frontend (al hacer save de info), si hay form creado, mostrar un modal de aviso:

```
⚠️ El formulario puede haber quedado desactualizado

Has modificado información del open mic. El formulario de Google
que tienes creado puede contener fechas o descripción incorrectas.

Te recomendamos borrarlo y volver a generarlo para que refleje
los nuevos datos.

[ Entendido ]
```

#### 6.1.2 Flag persistido en config

Junto al save de info, si hay form creado, se guarda también en Supabase:
```json
{ "form": { "info_changed": true } }
```
via `update_open_mic_config_keys`. Se limpia (`info_changed: false`) cuando el form se regenera.

#### 6.1.3 Badge ⚠️ persistente en la sección del formulario

Mientras `config.form.info_changed === true`, mostrar junto al título de la sección del formulario un icono `⚠️` amarillo con tooltip en hover:

```
⚠️  La información del open mic ha cambiado.
    El formulario actual puede mostrar fechas o
    descripción incorrectas. Reconsidera regenerarlo.
```

El badge desaparece cuando `info_changed` vuelve a `false` (form regenerado).

---

### 6.2 Fechas del formulario obsoletas

**Trigger:** las fechas calculadas al generar el form han quedado en el pasado o están a punto de hacerlo.

#### 6.2.1 Dato necesario: `config.form.last_date`

Al crear el form, el backend almacena la fecha más tardía de las opciones calculadas:
```python
dates = self._build_date_options(info)   # lista de strings "dd-MM-YY"
last_date = dates[-1] if dates else None # última fecha
```
Se persiste en `config.form.last_date` (string `dd-MM-YY`). Si `cadencia == 'unico'` y no hay fechas, campo omitido.

#### 6.2.2 Lógica de detección en el frontend

```
hoy = Date.now()
last_date = parseDDMMYY(config.form.last_date)   // dd-MM-YY → Date
dias_restantes = diff(last_date, hoy) en días

SI dias_restantes <= 7 Y dias_restantes >= 0:
  → mostrar aviso "última semana"
SI dias_restantes < 0:
  → mostrar aviso "fechas expiradas"
```

#### 6.2.3 Badge en la sección del formulario

Se muestra **adicionalmente** al badge de `info_changed` (pueden convivir ambos, o fusionarse en uno si los dos están activos).

Icono: 🗓️ rojo/naranja con tooltip en hover:

```
// Última semana:
🗓️  Las fechas del formulario caducan en X días.
    Considera regenerarlo para el próximo mes.

// Expiradas:
🗓️  Las fechas del formulario ya han pasado.
    El formulario actual no acepta inscripciones útiles.
    Regenera el formulario.
```

#### 6.2.4 Sin aviso para `cadencia == 'unico'`

Si no hay `last_date` en config (evento único o form sin fechas), no se muestra ningún aviso de caducidad.

---

## 7. Archivos afectados (actualizado)

| Archivo | Cambio |
|---------|--------|
| `backend/src/core/google_form_builder.py` | Mayor: descripción, fechas calculadas, color, info param, last_date |
| `backend/src/triggers/webhook_listener.py` | Menor: pasar info al builder, guardar bg_color + last_date + info_changed |
| `frontend/src/components/OpenMicDetail.jsx` | Mayor: selector cadencia, fecha_inicio, popup aviso, badges ⚠️ 🗓️ |
| `backend/tests/core/test_google_form_builder.py` | Nuevo: 9 tests |
| `frontend/src/test/OpenMicDetail.test.jsx` | Menor: tests nuevos (popup + badges) |

---

## 8. Tests adicionales (sección 6)

### Frontend (Vitest)

| Test | Descripción |
|------|-------------|
| `shows_popup_on_save_when_form_exists` | Modal aparece al guardar info si hay form creado |
| `no_popup_if_no_form` | Sin form creado, no muestra popup |
| `shows_info_changed_badge` | Badge ⚠️ visible cuando `info_changed=true` |
| `hides_info_changed_badge` | Badge oculto cuando `info_changed=false` |
| `shows_expiry_badge_last_week` | Badge 🗓️ visible si `last_date` ≤ 7 días |
| `shows_expiry_badge_expired` | Badge 🗓️ visible si `last_date` en el pasado |
| `no_expiry_badge_if_no_last_date` | Sin `last_date` (evento único), no muestra badge de caducidad |

---

## 9. Nota sobre el campo anterior "Fuera de alcance"

- Cambiar la cadencia de un open mic ya existente no regenera el form automáticamente — el sistema avisa (sección 6.1) pero no actúa solo.
- El color del form solo es visible en Google Forms directamente; no se replica en la UI de la app (salvo uso futuro de `form_bg_color` para estilizar).

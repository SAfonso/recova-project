# SDD — Onboarding Tutorial (v0.20.0)

---

## Objetivo

Tutorial interactivo paso a paso para hosts nuevos. Se muestra automáticamente
la primera vez que el host accede a la app, y nunca más. Informativo puro
(solo botones Siguiente/Cerrar, sin forzar acciones al usuario).

---

## Librería

**React Joyride** `^2.x`

```bash
npm install react-joyride
```

---

## Persistencia

`localStorage` key: `recova_tutorial_done`

- Si existe y es `"true"` → no mostrar
- Al completar o cerrar → setear `"true"`
- No depende de Supabase ni del usuario — es por navegador

---

## Archivos

| Archivo | Cambio |
|---------|--------|
| `frontend/src/components/OnboardingTutorial.jsx` | Componente nuevo — steps + Joyride |
| `frontend/src/main.jsx` | Montar `<OnboardingTutorial />` una vez en root |
| `package.json` | Añadir `react-joyride` |

---

## Steps del tutorial

El tutorial cubre el flujo completo del host. Los `target` apuntan a selectores
CSS que se añadirán como `data-tutorial` attributes en los componentes existentes.

| # | Target | Título | Descripción |
|---|--------|--------|-------------|
| 1 | `[data-tutorial="open-mic-selector"]` | Tus Open Mics | Aquí ves y seleccionas todos tus open mics. Puedes tener varios a la vez. |
| 2 | `[data-tutorial="create-open-mic"]` | Crear un Open Mic | Crea un nuevo open mic dándole nombre. Cada uno tiene su propia config y lineup. |
| 3 | `[data-tutorial="open-mic-detail-info"]` | Pestaña Info | Configura los datos de tu open mic: cadencia, fecha de inicio y descripción. |
| 4 | `[data-tutorial="open-mic-detail-scoring"]` | Pestaña Scoring | Define cómo se puntúan los cómicos: básico, personalizado o sin scoring. |
| 5 | `[data-tutorial="lineup-view"]` | El Lineup | Aquí ves todos los cómicos que han solicitado actuar, ordenados por score. |
| 6 | `[data-tutorial="comic-card"]` | Tarjeta de Cómico | Cada tarjeta muestra el nombre, score, categoría y disponibilidad del cómico. |
| 7 | `[data-tutorial="puede-hoy-badge"]` | Disponible Hoy | El badge ámbar indica que el cómico puede actuar hoy a última hora — útil si hay huecos. |
| 8 | `[data-tutorial="single-date-badge"]` | Solo Puede Hoy | El badge rojo indica que esta es la única fecha disponible del cómico. Prioridad alta. |
| 9 | `[data-tutorial="validate-button"]` | Validar Lineup | Cuando tengas los 5 cómicos listos, pulsa aquí para confirmar el lineup definitivo. |
| 10 | `[data-tutorial="telegram-button"]` | Notificaciones en el móvil | Conecta el bot de Telegram para recibir el lineup confirmado directamente en tu móvil. ¡Solo tienes que hacerlo una vez! |

---

## Comportamiento

- **Posición**: `bottom` por defecto; `top` si el elemento está en la mitad inferior
- **Locale**: botones en español — `{ back: 'Atrás', close: 'Cerrar', last: 'Fin', next: 'Siguiente', skip: 'Saltar' }`
- **Skip**: botón "Saltar" siempre visible — marca `recova_tutorial_done = true` igual que completar
- **Scroll**: `scrollToFirstStep: true`, `scrollOffset: 80`
- **Overlay**: `disableOverlayClose: false` — cerrar overlay = saltar tutorial
- **Estilo**: usar variables del design system (`--c-paper`, `--shadow-hard`, Bangers para títulos)

---

## Estilos Joyride (custom)

```js
const joyrideStyles = {
  options: {
    primaryColor: '#8C2020',       // rojo show
    backgroundColor: '#FEFDF8',    // c-paper
    textColor: '#1a1a1a',
    arrowColor: '#FEFDF8',
    zIndex: 10000,
  },
  tooltip: {
    borderRadius: 0,
    border: '3px solid #000',
    boxShadow: '5px 5px 0 #000',   // shadow-hard
    fontFamily: 'Space Grotesk, sans-serif',
  },
  tooltipTitle: {
    fontFamily: 'Bangers, cursive',
    fontSize: '1.4rem',
    letterSpacing: '0.05em',
  },
  buttonNext: {
    backgroundColor: '#8C2020',
    borderRadius: 0,
    border: '2px solid #000',
    boxShadow: '3px 3px 0 #000',
    fontFamily: 'Space Grotesk, sans-serif',
    fontWeight: 700,
  },
  buttonBack: {
    color: '#8C2020',
    fontFamily: 'Space Grotesk, sans-serif',
  },
  buttonSkip: {
    color: '#666',
    fontFamily: 'Space Grotesk, sans-serif',
  },
}
```

---

## Lógica del componente

```jsx
// OnboardingTutorial.jsx — pseudocódigo
const STORAGE_KEY = 'recova_tutorial_done'

export function OnboardingTutorial() {
  const [run, setRun] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) !== 'true') {
      // Pequeño delay para que la UI esté montada
      setTimeout(() => setRun(true), 800)
    }
  }, [])

  function handleCallback({ status }) {
    if (['finished', 'skipped'].includes(status)) {
      localStorage.setItem(STORAGE_KEY, 'true')
      setRun(false)
    }
  }

  return (
    <Joyride
      steps={STEPS}
      run={run}
      continuous
      showSkipButton
      scrollToFirstStep
      styles={joyrideStyles}
      locale={LOCALE_ES}
      callback={handleCallback}
    />
  )
}
```

---

## data-tutorial attributes a añadir

| Componente | Elemento | Attribute |
|-----------|----------|-----------|
| `OpenMicSelector.jsx` | Container lista open mics | `data-tutorial="open-mic-selector"` |
| `OpenMicSelector.jsx` | Botón crear nuevo | `data-tutorial="create-open-mic"` |
| `OpenMicDetail.jsx` | Tab Info | `data-tutorial="open-mic-detail-info"` |
| `OpenMicDetail.jsx` | Tab Scoring | `data-tutorial="open-mic-detail-scoring"` |
| `App.jsx` | Container lineup | `data-tutorial="lineup-view"` |
| `ComicCard.jsx` | Primera card | `data-tutorial="comic-card"` (solo index===0) |
| `ComicCard.jsx` | Badge puede_hoy | `data-tutorial="puede-hoy-badge"` |
| `ComicCard.jsx` | Badge is_single_date | `data-tutorial="single-date-badge"` |
| `App.jsx` | Botón validar | `data-tutorial="validate-button"` |
| `OpenMicSelector.jsx` | Botón Telegram | `data-tutorial="telegram-button"` |

---

## Tests

| Test | Descripción |
|------|-------------|
| `OnboardingTutorial.test.jsx` | No renderiza si `recova_tutorial_done=true` en localStorage |
| `OnboardingTutorial.test.jsx` | Renderiza si key no existe |
| `OnboardingTutorial.test.jsx` | Al llamar callback con `finished` → setea localStorage |
| `OnboardingTutorial.test.jsx` | Al llamar callback con `skipped` → setea localStorage |

---

## Notas

- Los steps que apuntan a badges (`puede-hoy`, `single-date`) solo se muestran
  si el elemento existe en el DOM. Joyride los salta automáticamente si el target
  no está montado — no es necesario manejo especial.
- No hay cambios en backend.
- No hay nuevas RPCs ni tablas.

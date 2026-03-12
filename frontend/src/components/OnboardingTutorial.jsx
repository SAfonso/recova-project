import { useEffect, useState } from 'react';
import Joyride, { EVENTS, ACTIONS, STATUS } from 'react-joyride';

const STORAGE_KEY = 'recova_tutorial_done';

const LOCALE_ES = {
  back: 'Atrás',
  close: 'Cerrar',
  last: 'Fin',
  next: 'Siguiente',
  skip: 'Saltar',
};

const joyrideStyles = {
  options: {
    primaryColor: '#8C2020',
    backgroundColor: '#FEFDF8',
    textColor: '#1a1a1a',
    arrowColor: '#FEFDF8',
    zIndex: 10000,
  },
  tooltip: {
    borderRadius: 0,
    border: '3px solid #000',
    boxShadow: '5px 5px 0 #000',
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
};

const STEPS = [
  {
    target: '[data-tutorial="open-mic-selector"]',
    title: 'Tus Open Mics',
    content: 'Aquí ves y seleccionas todos tus open mics. Puedes tener varios a la vez.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="create-open-mic"]',
    title: 'Crear un Open Mic',
    content: 'Crea un nuevo open mic dándole nombre. Cada uno tiene su propia config y lineup.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="open-mic-detail-info"]',
    title: 'Pestaña Info',
    content: 'Configura los datos de tu open mic: cadencia, fecha de inicio y descripción.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="open-mic-detail-scoring"]',
    title: 'Pestaña Scoring',
    content: 'Define cómo se puntúan los cómicos: básico, personalizado o sin scoring.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="lineup-view"]',
    title: 'El Lineup',
    content: 'Aquí ves todos los cómicos que han solicitado actuar, ordenados por score.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="comic-card"]',
    title: 'Tarjeta de Cómico',
    content: 'Cada tarjeta muestra el nombre, score, categoría y disponibilidad del cómico.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="puede-hoy-badge"]',
    title: 'Disponible Hoy',
    content: 'El badge ámbar indica que el cómico puede actuar hoy a última hora — útil si hay huecos.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="single-date-badge"]',
    title: 'Solo Puede Hoy',
    content: 'El badge rojo indica que esta es la única fecha disponible del cómico. Prioridad alta.',
    placement: 'bottom',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="validate-button"]',
    title: 'Validar Lineup',
    content: 'Cuando tengas los 5 cómicos listos, pulsa aquí para confirmar el lineup definitivo.',
    placement: 'top',
    disableBeacon: true,
  },
  {
    target: '[data-tutorial="telegram-button"]',
    title: 'Notificaciones en el móvil',
    content: 'Conecta el bot de Telegram para recibir el lineup confirmado directamente en tu móvil. ¡Solo tienes que hacerlo una vez!',
    placement: 'bottom',
    disableBeacon: true,
  },
];

export function OnboardingTutorial() {
  const [run, setRun] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  // Start: poll until the first target appears in the DOM
  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === 'true') return;
    const poll = setInterval(() => {
      if (document.querySelector('[data-tutorial="open-mic-selector"]')) {
        clearInterval(poll);
        clearTimeout(maxWait);
        setRun(true);
      }
    }, 150);
    const maxWait = setTimeout(() => { clearInterval(poll); setRun(true); }, 8000);
    return () => { clearInterval(poll); clearTimeout(maxWait); };
  }, []);

  function handleCallback({ status, type, index, action }) {
    // Target not found → skip to next step (so tour always completes)
    if (type === EVENTS.TARGET_NOT_FOUND) {
      setStepIndex(index + 1);
      return;
    }
    // Advance step index after each step
    if (type === EVENTS.STEP_AFTER) {
      setStepIndex(index + (action === ACTIONS.PREV ? -1 : 1));
      return;
    }
    // Tour done
    if ([STATUS.FINISHED, STATUS.SKIPPED].includes(status)) {
      localStorage.setItem(STORAGE_KEY, 'true');
      setRun(false);
      setStepIndex(0);
    }
  }

  return (
    <Joyride
      steps={STEPS}
      run={run}
      stepIndex={stepIndex}
      continuous
      showSkipButton
      scrollToFirstStep
      scrollOffset={80}
      disableOverlayClose={false}
      styles={joyrideStyles}
      locale={LOCALE_ES}
      callback={handleCallback}
    />
  );
}

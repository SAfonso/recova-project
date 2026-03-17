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
  buttonClose: {
    color: '#666',
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
    target: '[data-tutorial="telegram-button"]',
    title: '⚠️ Conecta Telegram primero',
    content: 'Antes de validar tu primer lineup, conecta el bot de Telegram. Es imprescindible para recibir el lineup confirmado en tu móvil. ¡Solo tienes que hacerlo una vez!',
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
];

const PAUSE_HINTS = {
  3: 'Abre un open mic para continuar el tour →',
  4: 'Abre un open mic para continuar el tour →',
  5: 'Ve al lineup para continuar el tour →',
  6: 'Ve al lineup para continuar el tour →',
  7: 'Ve al lineup para continuar el tour →',
  8: 'Ve al lineup para continuar el tour →',
  9: 'Ve al lineup para continuar el tour →',
};

export function OnboardingTutorial() {
  const [run, setRun] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [done, setDone] = useState(
    () => localStorage.getItem(STORAGE_KEY) === 'true',
  );
  const [showQuitConfirm, setShowQuitConfirm] = useState(false);

  // Single effect: whenever run=false and !done, poll until the current
  // step's target appears in the DOM, then resume. Works for both
  // initial start (stepIndex=0) and mid-tour navigation pauses.
  useEffect(() => {
    if (done || run) return;
    const target = STEPS[stepIndex]?.target;
    if (!target) return;

    const poll = setInterval(() => {
      if (document.querySelector(target)) {
        clearInterval(poll);
        setRun(true);
      }
    }, 300);

    return () => clearInterval(poll);
  }, [run, stepIndex, done]);

  function finishTutorial() {
    localStorage.setItem(STORAGE_KEY, 'true');
    setDone(true);
    setRun(false);
    setStepIndex(0);
    setShowQuitConfirm(false);
  }

  function handleCallback({ status, type, index, action }) {
    if (type === EVENTS.TARGET_NOT_FOUND) {
      setRun(false); // pause — effect above re-polls until target appears
      return;
    }
    if (type === EVENTS.STEP_AFTER) {
      setStepIndex(index + (action === ACTIONS.PREV ? -1 : 1));
      return;
    }
    // Intercept close/skip — show confirmation modal instead of finishing
    if (action === ACTIONS.CLOSE || status === STATUS.SKIPPED) {
      setRun(false);
      setShowQuitConfirm(true);
      return;
    }
    if (status === STATUS.FINISHED) {
      finishTutorial();
    }
  }

  if (done) return null;

  return (
    <>
      <Joyride
        steps={STEPS}
        run={run}
        stepIndex={stepIndex}
        continuous
        showSkipButton
        scrollToFirstStep
        scrollOffset={80}
        disableCloseOnEsc={false}
        styles={joyrideStyles}
        locale={LOCALE_ES}
        callback={handleCallback}
      />
      {!run && stepIndex > 0 && PAUSE_HINTS[stepIndex] && !showQuitConfirm && (
        <div className="fixed bottom-6 left-6 z-[9999] flex items-center gap-2 rounded border-2 border-[#1a1a1a] bg-[#fff8e7] px-3 py-2 text-xs font-bold shadow-[3px_3px_0_#000]">
          <span>📍</span>
          <span>{PAUSE_HINTS[stepIndex]}</span>
          <button
            type="button"
            onClick={() => setShowQuitConfirm(true)}
            className="ml-1 text-[#6B5C4A] hover:text-[#DC2626]"
            aria-label="Cerrar tour"
          >
            ✕
          </button>
        </div>
      )}
      {showQuitConfirm && (
        <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/50">
          <div className="paper-drop animate-pop-in max-w-sm mx-4">
            <div className="paper-rough paper-note border-[4px] border-[#1a1a1a] bg-[#fffef5] p-6 text-center">
              <p className="mb-2 font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">
                ¿Seguro que quieres salir del tutorial?
              </p>
              <p className="mb-6 text-sm text-[#6B5C4A]">
                El paso de Telegram es obligatorio para usar el bot.
              </p>
              <div className="flex justify-center gap-4">
                <button
                  type="button"
                  onClick={finishTutorial}
                  className="comic-shadow cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#DC2626] px-5 py-2 font-bold text-white transition-all duration-150 hover:bg-[#B91C1C] hover:scale-[1.03] active:scale-[0.97]"
                >
                  Salir
                </button>
                <button
                  type="button"
                  onClick={() => { setShowQuitConfirm(false); setRun(true); }}
                  className="cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#e5e7eb] px-5 py-2 font-bold text-[#1a1a1a] transition-all duration-150 hover:bg-[#d1d5db]"
                >
                  Continuar tutorial
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

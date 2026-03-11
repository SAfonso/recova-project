/**
 * FormWarningBadges — badges de aviso para el formulario de Google.
 *
 * Muestra hasta dos badges:
 *   ⚠️  info_changed: la info del open mic cambió desde que se generó el form.
 *   🗓️  expiración: las fechas del form caducan pronto o ya han pasado.
 */

function parseDDMMYY(ddmmyy) {
  if (!ddmmyy) return null;
  const [dd, mm, yy] = ddmmyy.split('-');
  if (!dd || !mm || !yy) return null;
  return new Date(2000 + parseInt(yy, 10), parseInt(mm, 10) - 1, parseInt(dd, 10));
}

function diffDays(dateA, dateB) {
  return Math.floor((dateA - dateB) / (1000 * 60 * 60 * 24));
}

export function FormWarningBadges({ formConfig = {} }) {
  const { info_changed, last_date } = formConfig;

  const lastDateObj = parseDDMMYY(last_date);
  const today       = new Date();
  today.setHours(0, 0, 0, 0);
  const daysLeft    = lastDateObj ? diffDays(lastDateObj, today) : null;

  const showInfoChanged = info_changed === true;
  const showExpiry      = daysLeft !== null && daysLeft <= 7;
  const isExpired       = daysLeft !== null && daysLeft < 0;

  if (!showInfoChanged && !showExpiry) return null;

  return (
    <span className="ml-1 inline-flex items-center gap-1">
      {showInfoChanged && (
        <span
          role="img"
          aria-label="Formulario desactualizado: la información del open mic ha cambiado"
          title="La información del open mic ha cambiado. El formulario actual puede mostrar fechas o descripción incorrectas. Reconsidera regenerarlo."
          className="text-yellow-500 cursor-help"
        >
          ⚠️
        </span>
      )}
      {showExpiry && (
        <span
          role="img"
          aria-label={
            isExpired
              ? 'Fechas del formulario en el pasado: el formulario actual no acepta inscripciones útiles'
              : `Fechas del formulario caducan en ${daysLeft} días`
          }
          title={
            isExpired
              ? 'Las fechas del formulario ya han pasado. El formulario actual no acepta inscripciones útiles. Regenera el formulario.'
              : `Las fechas del formulario caducan en ${daysLeft} días. Considera regenerarlo para el próximo mes.`
          }
          className="text-orange-500 cursor-help"
        >
          🗓️
        </span>
      )}
    </span>
  );
}

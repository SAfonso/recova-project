import { supabase } from '../../supabaseClient';

const SparkIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
  </svg>
);

const BackIcon = () => (
  <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

function formatDateForSheet(value) {
  if (!value) return '--/--/--';
  const [year, month, day] = value.split('-');
  if (!year || !month || !day) return '--/--/--';
  return `${day}-${month}-${year.slice(2)}`;
}

export function Header({ eventDate, onEventDateChange, selectedCount, hostEmail, onBack }) {
  const handleLogout = () => supabase.auth.signOut();

  return (
    <header className="flex flex-col items-center gap-2 pb-4 pt-6">
      {onBack && (
        <div className="w-full">
          <button type="button" onClick={onBack} className="btn-back">
            <BackIcon />
            Volver al Open Mic
          </button>
        </div>
      )}

      <div className="flex items-center gap-3">
        <SparkIcon className="animate-spark h-5 w-5 text-[#C4905A]" style={{ animationDelay: '0.3s' }} />
        <h1 className="font-['Bangers'] text-4xl tracking-wider text-[#0D0D0D] sm:text-5xl">
          AI LINEUP ARCHITECT
        </h1>
        <SparkIcon className="animate-spark h-5 w-5 text-[#C4905A]" style={{ animationDelay: '1.2s' }} />
      </div>

      <div className="relative inline-flex items-center gap-3">
        <div className="relative inline-block px-1">
          <p className="font-['Bangers'] text-3xl tracking-wider text-[#0D0D0D]">{formatDateForSheet(eventDate)}</p>
          <div className="absolute -bottom-1 left-0 right-0 h-[3px] bg-[#2C4A52]" aria-hidden="true" />
          <div className="absolute -bottom-2.5 left-1 right-0 h-px bg-[#2C4A52]/30" aria-hidden="true" />
          <input
            type="date"
            value={eventDate}
            onChange={(e) => onEventDateChange(e.target.value)}
            className="absolute inset-0 cursor-pointer opacity-0"
            aria-label="Cambiar fecha del evento"
          />
        </div>
        <span className={`rounded-none border-[3px] border-[#0D0D0D] px-3 py-1 text-sm font-bold transition-colors duration-200 ${selectedCount === 5 ? 'bg-[#5E7260] text-[#F5F5F0]' : 'bg-[#EDE8DC] text-[#0D0D0D]'}`}>
          {selectedCount}/5
        </span>
      </div>

      {hostEmail && (
        <div className="flex items-center gap-2 text-xs text-[#1a1a1a]/60">
          <span>{hostEmail}</span>
          <button type="button" onClick={handleLogout} className="cursor-pointer font-bold underline underline-offset-2 hover:text-[#3D5F6C]">
            Cerrar sesión
          </button>
        </div>
      )}
    </header>
  );
}

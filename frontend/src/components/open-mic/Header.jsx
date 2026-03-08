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
        <SparkIcon className="animate-spark h-5 w-5 text-[#F97316]" style={{ animationDelay: '0.3s' }} />
        <h1 className="font-['Bangers'] text-4xl tracking-wider text-[#1a1a1a] drop-shadow-[2px_2px_0px_rgba(255,255,255,0.35)] sm:text-5xl">
          AI LINEUP ARCHITECT
        </h1>
        <SparkIcon className="animate-spark h-5 w-5 text-[#F97316]" style={{ animationDelay: '1.2s' }} />
      </div>

      <div className="relative inline-flex items-center gap-3">
        <div className="relative inline-block px-1">
          <p className="font-['Bangers'] text-3xl tracking-wider text-[#fff8e7]">{formatDateForSheet(eventDate)}</p>
          <svg className="absolute -bottom-1 left-0 w-full" height="6" viewBox="0 0 200 6" fill="none" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0,3 Q20,0 40,4 T80,2 T120,5 T160,1 T200,3" stroke="#DC2626" strokeWidth="3" fill="none" strokeLinecap="round" />
          </svg>
          <input
            type="date"
            value={eventDate}
            onChange={(e) => onEventDateChange(e.target.value)}
            className="absolute inset-0 cursor-pointer opacity-0"
            aria-label="Cambiar fecha del evento"
          />
        </div>
        <span className={`rounded-full border-2 border-[#1a1a1a] px-3 py-1 text-sm font-bold transition-colors duration-200 ${selectedCount === 5 ? 'bg-[#22C55E] text-[#fff8e7]' : 'bg-[#F5F0E1] text-[#1a1a1a]'}`}>
          {selectedCount}/5
        </span>
      </div>

      {hostEmail && (
        <div className="flex items-center gap-2 text-xs text-[#1a1a1a]/60">
          <span>{hostEmail}</span>
          <button type="button" onClick={handleLogout} className="cursor-pointer font-bold underline underline-offset-2 hover:text-[#DC2626]">
            Cerrar sesión
          </button>
        </div>
      )}
    </header>
  );
}

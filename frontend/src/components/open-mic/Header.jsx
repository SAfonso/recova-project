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
        <div className="relative inline-block px-2 pb-3">
          <p className="font-['Oswald'] text-4xl font-bold italic tracking-wider text-[#0D0D0D] sm:text-5xl">{formatDateForSheet(eventDate)}</p>
          {/* Chalk underline — tiza sobre pizarra */}
          <svg
            className="absolute left-0 w-full overflow-visible"
            style={{ bottom: '2px' }}
            height="10"
            viewBox="0 0 100 10"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {/* Difuminado chalk dust */}
            <path d="M0,6 C8,4 16,8 24,5.5 C32,3 40,7.5 48,5 C56,3 64,7 72,5 C80,3.5 88,7 96,5 L100,5.5"
              stroke="rgba(255,255,255,0.22)" strokeWidth="8" fill="none" strokeLinecap="round"
              style={{ filter:'blur(2px)' }}
            />
            {/* Trazo principal — grueso e irregular */}
            <path d="M0,6 C8,4 16,8 24,5.5 C32,3 40,7.5 48,5 C56,3 64,7 72,5 C80,3.5 88,7 96,5 L100,5.5"
              stroke="rgba(255,255,255,0.88)" strokeWidth="4.5" fill="none" strokeLinecap="round"
              style={{ filter:'blur(0.5px)' }}
            />
            {/* Hilo de luz — borde brillante del trazo */}
            <path d="M0,5 C8,3.5 16,6.5 24,4.5 C32,2.5 40,6 48,4 C56,2.5 64,5.5 72,4 C80,3 88,5.5 96,4 L100,4.5"
              stroke="rgba(255,255,255,0.45)" strokeWidth="1.5" fill="none" strokeLinecap="round"
            />
          </svg>
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

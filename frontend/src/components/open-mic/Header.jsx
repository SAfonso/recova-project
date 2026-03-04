function formatDateForSheet(value) {
  if (!value) {
    return '--/--/--';
  }

  const [year, month, day] = value.split('-');
  if (!year || !month || !day) {
    return '--/--/--';
  }

  return `${day}-${month}-${year.slice(2)}`;
}

import { supabase } from '../../supabaseClient';

export function Header({ eventDate, onEventDateChange, selectedCount, hostEmail }) {
  const handleLogout = () => supabase.auth.signOut();

  return (
    <header className="flex flex-col items-center gap-2 pb-4 pt-6">
      <h1 className="font-['Bangers'] text-4xl tracking-wider text-[#1a1a1a] drop-shadow-[2px_2px_0px_rgba(255,255,255,0.3)] sm:text-5xl">
        AI LINEUP ARCHITECT
      </h1>

      <div className="relative inline-flex items-center gap-3">
        <div className="relative inline-block px-1">
          <p className="font-['Patrick_Hand'] text-2xl text-[#1a1a1a]">{formatDateForSheet(eventDate)}</p>
          <svg
            className="absolute -bottom-1 left-0 w-full"
            height="6"
            viewBox="0 0 200 6"
            fill="none"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              d="M0,3 Q20,0 40,4 T80,2 T120,5 T160,1 T200,3"
              stroke="#DC2626"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
          <input
            type="date"
            value={eventDate}
            onChange={(event) => onEventDateChange(event.target.value)}
            className="absolute inset-0 cursor-pointer opacity-0"
            aria-label="Cambiar fecha del evento"
          />
        </div>

        <span className="rounded-full border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-1 text-sm font-bold text-[#1a1a1a]">
          {selectedCount}/5
        </span>
      </div>

      {hostEmail && (
        <div className="flex items-center gap-2 text-xs text-[#6B5C4A]">
          <span>{hostEmail}</span>
          <button
            type="button"
            onClick={handleLogout}
            className="font-bold underline underline-offset-2 hover:text-[#DC2626]"
          >
            Cerrar sesión
          </button>
        </div>
      )}
    </header>
  );
}

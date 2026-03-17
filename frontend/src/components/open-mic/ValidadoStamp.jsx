export function ValidadoStamp() {
  return (
    <div className="flex justify-center">
      <div className="-rotate-6">
        <div
          className="animate-stamp-in flex items-center gap-2 rounded-lg border-[4px] border-double border-[#15803D] bg-[#dcfce7]/90 px-6 py-2 text-2xl font-black uppercase tracking-widest text-[#15803D] shadow-[3px_3px_0px_rgba(0,0,0,0.2)]"
        >
          <svg className="h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          VALIDADO
        </div>
      </div>
    </div>
  );
}

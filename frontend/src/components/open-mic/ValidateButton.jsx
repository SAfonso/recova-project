const CheckIcon = () => (
  <svg className="h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export function ValidateButton({ disabled, saving, isValidated, onClick }) {
  const bg = isValidated ? 'bg-[#15803D] hover:bg-[#15803D]' : 'bg-[#22C55E] hover:bg-[#16A34A]';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`comic-shadow mx-auto flex cursor-pointer items-center gap-3 rounded-xl border-[4px] border-[#1a1a1a] ${bg} px-8 py-3 text-xl font-bold text-[#fff8e7] transition-all duration-200 hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50`}
      aria-label="Validar lineup"
    >
      <CheckIcon />
      <span>{saving ? 'Enviando a n8n...' : 'Validar LineUp'}</span>
    </button>
  );
}

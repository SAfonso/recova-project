const CheckIcon = () => (
  <svg className="h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export function ValidateButton({ disabled, saving, isValidated, onClick }) {
  const bg = isValidated ? 'bg-[#3D5F6C] hover:bg-[#2D4A57]' : 'bg-[#5E7260] hover:bg-[#4A5C4C]';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`comic-shadow mx-auto flex cursor-pointer items-center gap-3 rounded-none border-[3px] border-[#0D0D0D] ${bg} px-8 py-3 text-xl font-bold text-[#0D0D0D] transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50`}
      aria-label="Validar lineup"
    >
      <CheckIcon />
      <span>{saving ? 'Enviando a n8n...' : 'Validar LineUp'}</span>
    </button>
  );
}

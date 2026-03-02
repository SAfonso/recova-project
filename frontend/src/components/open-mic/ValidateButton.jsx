export function ValidateButton({ disabled, saving, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="comic-shadow mx-auto flex items-center gap-3 rounded-xl border-[4px] border-[#1a1a1a] bg-[#22C55E] px-8 py-3 text-xl font-bold text-[#fff8e7] transition-all hover:scale-105 hover:bg-[#16A34A] active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
      aria-label="Validar lineup"
    >
      <span className="text-2xl">✓</span>
      <span>{saving ? 'Enviando a n8n...' : 'Validar LineUp'}</span>
    </button>
  );
}

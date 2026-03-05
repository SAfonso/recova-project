const PencilIcon = () => (
  <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
  </svg>
);

export function CambiarButton({ onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="comic-shadow mx-auto flex cursor-pointer items-center gap-3 rounded-xl border-[4px] border-[#1a1a1a] bg-[#EAB308] px-8 py-3 text-xl font-bold text-[#1a1a1a] transition-all duration-200 hover:scale-105 hover:bg-[#CA8A04] active:scale-95"
      aria-label="Cambiar lineup validado"
    >
      <PencilIcon />
      <span>Cambiar!</span>
    </button>
  );
}

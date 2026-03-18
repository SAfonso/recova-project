export function RecoveryNotes({ value, onChange }) {
  return (
    <section className="paper-drop mx-auto w-full max-w-3xl"><div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-4">
      <label htmlFor="recovery-notes" className="mb-2 block font-['Bangers'] text-lg tracking-wide text-[#1a1a1a]">
        Notas de recuperación
      </label>
      <textarea
        id="recovery-notes"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Contexto para Telegram/n8n si el flujo necesita recovery..."
        className="min-h-24 w-full rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] p-3 text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
      />
    </div></section>
  );
}

export function CambiarConfirmModal({ onAccept, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="paper-drop animate-pop-in max-w-sm mx-4"><div className="paper-rough paper-note border-[4px] border-[#1a1a1a] bg-[#fffef5] p-6 text-center">
        <p className="mb-6 text-lg font-bold text-[#1a1a1a]">
          ¿Seguro que quieres cambiar el lineup validado?
        </p>
        <div className="flex justify-center gap-4">
          <button
            type="button"
            onClick={onAccept}
            className="comic-shadow cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#EAB308] px-5 py-2 font-bold text-[#1a1a1a] transition-all duration-150 hover:bg-[#CA8A04] hover:scale-[1.03] active:scale-[0.97]"
          >
            Aceptar
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#e5e7eb] px-5 py-2 font-bold text-[#1a1a1a] transition-all duration-150 hover:bg-[#d1d5db]"
          >
            Cancelar
          </button>
        </div>
      </div></div>
    </div>
  );
}

export function LoadingSkeleton() {
  return (
    <section className="notebook-lines relative mx-auto w-full max-w-lg overflow-hidden rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-8 py-6 lg:max-w-4xl">
      <div className="ml-8 flex flex-col gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="w-5 shrink-0 text-right text-xs text-[#C8B89A]">{i + 1}.</span>
            <div
              className="h-5 rounded"
              style={{
                width: `${55 + (i * 13) % 35}%`,
                background: 'linear-gradient(90deg, #e8dfc8 25%, #f5f0e1 50%, #e8dfc8 75%)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 1.4s infinite',
                animationDelay: `${i * 0.1}s`,
              }}
            />
            <div className="ml-auto h-2.5 w-2.5 shrink-0 rounded-full border border-[#1a1a1a]/20 bg-[#C8B89A]" />
          </div>
        ))}
      </div>
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </section>
  );
}

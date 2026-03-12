/* BgIcons — decoración de fondo fija para todas las vistas */

const StarOutline = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="0.8" aria-hidden="true">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

const StarFill = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
  </svg>
);

const MicIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2H3v2a9 9 0 0 0 8 8.94V22H8v2h8v-2h-3v-1.06A9 9 0 0 0 21 12v-2h-2z"/>
  </svg>
);

const BeerIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" aria-hidden="true">
    <path d="M6 3h10l1.5 16H4.5L6 3z"/>
    <path d="M16.5 7H19a2 2 0 0 1 0 4h-2.5"/>
    <path d="M7 9h8M7 13h8"/>
  </svg>
);

const NotebookIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" aria-hidden="true">
    <rect x="3" y="2" width="18" height="20" rx="1"/>
    <line x1="7" y1="2" x2="7" y2="22"/>
    <line x1="11" y1="7" x2="19" y2="7"/>
    <line x1="11" y1="11" x2="19" y2="11"/>
    <line x1="11" y1="15" x2="19" y2="15"/>
  </svg>
);

const SpotlightIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="5" r="2.5"/>
    <path d="M5 22L9.5 9.5h5L19 22"/>
    <path d="M6.5 22h11"/>
    <path d="M10 9.5L8 3M14 9.5L16 3"/>
  </svg>
);

/* Posiciones fijas — distribuidas por todo el viewport */
const ITEMS = [
  /* ── Zona superior ─────────────────────── */
  { Icon: StarOutline, s: { left:'2%',   top:'8%',    width:'7rem',  transform:'rotate(-10deg)', color:'rgba(255,248,231,0.16)' } },
  { Icon: MicIcon,     s: { right:'4%',  top:'6%',    width:'4rem',  transform:'rotate(14deg)',  color:'rgba(255,248,231,0.13)' } },
  { Icon: SpotlightIcon,s:{ left:'24%',  top:'3%',    width:'5rem',  transform:'rotate(-6deg)',  color:'rgba(201,166,107,0.20)' } },
  { Icon: StarFill,    s: { right:'22%', top:'12%',   width:'2rem',  transform:'rotate(20deg)',  color:'rgba(201,166,107,0.22)' } },
  { Icon: NotebookIcon,s: { right:'14%', top:'18%',   width:'3.5rem',transform:'rotate(-12deg)', color:'rgba(255,248,231,0.12)' } },

  /* ── Zona media ─────────────────────────── */
  { Icon: BeerIcon,    s: { left:'4%',   top:'42%',   width:'3.5rem',transform:'rotate(8deg)',   color:'rgba(255,248,231,0.14)' } },
  { Icon: StarOutline, s: { right:'6%',  top:'38%',   width:'5rem',  transform:'rotate(-8deg)',  color:'rgba(255,248,231,0.13)' } },
  { Icon: MicIcon,     s: { left:'46%',  top:'46%',   width:'2.5rem',transform:'rotate(-4deg)',  color:'rgba(255,248,231,0.10)' } },
  { Icon: SpotlightIcon,s:{ right:'32%', top:'55%',   width:'3rem',  transform:'rotate(22deg)',  color:'rgba(201,166,107,0.14)' } },

  /* ── Zona inferior ──────────────────────── */
  { Icon: MicIcon,     s: { right:'3%',  bottom:'14%',width:'6rem',  transform:'rotate(18deg)',  color:'rgba(255,248,231,0.11)' } },
  { Icon: BeerIcon,    s: { left:'16%',  bottom:'7%', width:'4rem',  transform:'rotate(-14deg)', color:'rgba(201,166,107,0.16)' } },
  { Icon: StarFill,    s: { right:'28%', bottom:'10%',width:'2.5rem',transform:'rotate(5deg)',   color:'rgba(255,248,231,0.16)' } },
  { Icon: NotebookIcon,s: { left:'38%',  bottom:'4%', width:'5rem',  transform:'rotate(-10deg)', color:'rgba(255,248,231,0.12)' } },
  { Icon: StarOutline, s: { left:'80%',  bottom:'28%',width:'3rem',  transform:'rotate(12deg)',  color:'rgba(201,166,107,0.18)' } },
];

export function BgIcons() {
  return (
    <div
      className="pointer-events-none select-none"
      aria-hidden="true"
      style={{ position:'fixed', inset:0, zIndex:0, overflow:'hidden' }}
    >
      {ITEMS.map(({ Icon, s }, i) => (
        <Icon key={i} className="absolute" style={s} />
      ))}
    </div>
  );
}

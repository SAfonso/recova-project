# Frontend Recova (Vite + React + Tailwind)

## Configuración
1. Copia `.env.example` a `.env`.
2. Define `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`.

## Desarrollo
```bash
npm install
npm run dev
```

## Build para Vercel
```bash
npm run build
```

La app usa `@supabase/supabase-js` con `db.schema = 'gold'` por defecto.

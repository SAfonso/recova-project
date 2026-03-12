/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Cartoon-Matte Brutalist — colores oscurecidos para WCAG AAA
        'matte-bg':           '#F5F0E8',
        'matte-paper':        '#F0E8D5',
        'matte-paper-alt':    '#E8DFCC',
        'matte-ink':          '#0D0D0D',
        'matte-muted':        '#5A5248',
        'matte-petrol':       '#3D5F6C',
        'matte-petrol-dark':  '#2D4A57',
        'matte-sage':         '#5E7260',
        'matte-sage-dark':    '#4A5C4C',
        'matte-ochre':        '#C4905A',
        'matte-ochre-dark':   '#A67440',
      },
      boxShadow: {
        'hard':    '5px 5px 0 #000000',
        'hard-md': '3px 3px 0 #000000',
        'hard-sm': '2px 2px 0 #000000',
        'hard-xs': '1px 1px 0 #000000',
      },
      fontFamily: {
        bangers: ['Bangers', 'Impact', 'sans-serif'],
        hand:    ['Patrick Hand', 'Comic Sans MS', 'cursive'],
      },
    },
  },
  plugins: [],
};

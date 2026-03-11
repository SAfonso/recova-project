/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Cartoon-Matte Brutalist palette
        'matte-bg':      '#F5F5F0',
        'matte-paper':   '#EDE8DC',
        'matte-paper-alt':'#E4DDD0',
        'matte-ink':     '#0D0D0D',
        'matte-muted':   '#6A6358',
        'matte-petrol':  '#4A6D7C',
        'matte-petrol-dark': '#3A5A6A',
        'matte-sage':    '#7B8E7E',
        'matte-sage-dark': '#68786A',
        'matte-ochre':   '#D4A373',
        'matte-ochre-dark': '#B8864F',
      },
      boxShadow: {
        'hard':    '4px 4px 0 #000000',
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

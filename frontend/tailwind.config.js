/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#fef7ee',
          100: '#fdedd6',
          200: '#fad8ac',
          300: '#f6bd78',
          400: '#f19941',
          500: '#ed7d1a',
          600: '#de6212',
          700: '#bc4710',
          800: '#953712',
          900: '#772e11',
        },
        f1: {
          red: '#DC143C',
          black: '#15151E',
          dark: '#1E1E26',
          gray: '#2D2D3A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
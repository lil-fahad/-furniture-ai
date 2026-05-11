/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./frontend/**/*.{js,jsx,ts,tsx}", "./frontend/index.html"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d7fe',
          300: '#a5b8fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        ikea:    { DEFAULT: '#0058A3', light: '#E8F4FD' },
        alibaba: { DEFAULT: '#FF6A00', light: '#FFF3E8' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 2px 12px 0 rgba(0,0,0,0.08)',
        'card-hover': '0 8px 30px 0 rgba(0,0,0,0.14)',
      },
    },
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#e8eef7',
          100: '#c5d3eb',
          200: '#9fb5de',
          300: '#7897d0',
          400: '#5a80c7',
          500: '#3c6abd',
          600: '#2e5aa8',
          700: '#1e4690',
          800: '#003366',
          900: '#001a3d',
        },
        gov: {
          blue: '#003366',
          lightblue: '#1351b4',
          yellow: '#ffcd07',
          green: '#168821',
          gray: '#555770',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

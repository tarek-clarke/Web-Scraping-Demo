/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: '#0f172a',
        darkCard: '#1e293b',
        cadillacGold: '#C5A880',
        cadillacSilver: '#C0C0C0',
      },
    }
  },
  plugins: [],
}
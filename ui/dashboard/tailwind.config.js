/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        dark: {
          900: "#0a0a0f",
          800: "#12121a",
          700: "#1a1a2e",
          600: "#232340",
        },
        neon: {
          green: "#00ff88",
          red: "#ff4466",
          blue: "#4488ff",
          purple: "#8844ff",
          yellow: "#ffaa00",
        },
      },
    },
  },
  plugins: [],
};

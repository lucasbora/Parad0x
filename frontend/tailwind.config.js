/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        pmt: {
          blue: "#005BBC",
          slate: "#0F172A",
          bg: "#F8FAFC",
          emerald: "#059669",
          amber: "#D97706",
          red: "#DC2626",
        },
      },
      fontFamily: {
        sans: ["'Noto Sans Inscriptional Pahlavi'", "ui-sans-serif", "system-ui", "sans-serif"],
        // secondary font (numbers, times, data labels): use the font-secondary class.
        // Sunflower has no Romanian diacritics or minus / middle-dot / em-dash glyphs; the main font fills those in.
        secondary: ["Sunflower", "'Noto Sans Inscriptional Pahlavi'", "ui-sans-serif", "system-ui", "sans-serif"],
        // no monospace anywhere: Tailwind's base styles give code/kbd/pre the "mono" stack, so point it at the secondary font
        mono: ["Sunflower", "'Noto Sans Inscriptional Pahlavi'", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        island: "0 10px 30px -12px rgba(15, 23, 42, 0.35), 0 2px 6px -2px rgba(15, 23, 42, 0.12)",
      },
      keyframes: {
        pulseRing: {
          "0%": { transform: "scale(0.9)", opacity: "0.85" },
          "70%": { transform: "scale(1.9)", opacity: "0" },
          "100%": { transform: "scale(1.9)", opacity: "0" },
        },
        slideIn: {
          "0%": { transform: "translateX(24px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        drive: {
          "0%": { transform: "translateY(110%)" },
          "100%": { transform: "translateY(-110%)" },
        },
      },
      animation: {
        pulseRing: "pulseRing 1.6s cubic-bezier(0.2, 0.6, 0.4, 1) infinite",
        slideIn: "slideIn 0.28s ease-out",
      },
    },
  },
  plugins: [],
};

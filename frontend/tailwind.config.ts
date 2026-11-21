import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#08090c",
        surface: "#10131a",
        "surface-2": "#171b26",
        "surface-3": "#1f2534",
        border: "#262d3d",
        foreground: "#f2f5fa",
        muted: "#8b96ab",
        accent: {
          DEFAULT: "#7c8cf8",
          dim: "#5b6ef0",
          2: "#22d3ee",
        },
        success: "#34d399",
        warning: "#fbbf24",
        error: "#f87171",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

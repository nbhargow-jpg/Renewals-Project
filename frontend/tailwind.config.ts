/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#12284C',
          light: '#1B3B6F',
          dark: '#0A172C',
          deep: '#050D19',
        },
        teal: {
          DEFAULT: '#00A3AD',
          light: '#00C4D0',
          dark: '#007A82',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',   // badges and delta chips (6px)
        DEFAULT: '8px',
        md: '8px',   // buttons, inputs, selects (8px)
        lg: '12px',  // cards, tables, panels (rounded-xl / 12px)
        xl: '12px',  // rounded-xl (12px)
        '2xl': '16px', // modals and drawers (16px)
      },
      boxShadow: {
        card: '0 1px 2px rgba(16,24,40,0.05), 0 1px 3px rgba(16,24,40,0.08)',
        elevation: '0 4px 16px rgba(16,24,40,0.12)',
      },
      transitionDuration: {
        fast: '140ms',
      },
    },
  },
  plugins: [],
}

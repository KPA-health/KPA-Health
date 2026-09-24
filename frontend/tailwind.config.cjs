module.exports = {
  content: ['./frontend/index.html', './frontend/js/**/*.js'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#1f4a2a', dark: '#16361e', light: '#2d673c', hover: '#265933' },
        secondary: { DEFAULT: '#3b8070', dark: '#2e6357', light: '#4d9f8d', hover: '#337062' },
        tertiary: { DEFAULT: '#9ed3a2', light: '#eaf6ed', ultralight: '#f4fbf5', dark: '#7fb884' },
        clinical: { bg: '#fcfdfd', card: '#ffffff', border: '#e2e8f0', text: '#0f172a' }
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        dyslexic: ['"Comic Sans MS"', '"OpenDyslexic"', 'sans-serif']
      },
      boxShadow: {
        soft: '0 2px 10px -2px rgba(31, 74, 42, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.02)',
        card: '0 4px 20px -2px rgba(31, 74, 42, 0.06), 0 2px 6px -1px rgba(0, 0, 0, 0.04)',
        dropdown: '0 10px 30px -4px rgba(31, 74, 42, 0.12), 0 6px 12px -3px rgba(0, 0, 0, 0.08)'
      }
    }
  }
};

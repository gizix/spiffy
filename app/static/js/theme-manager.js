/**
 * Theme manager for Spiffy
 * Handles theme switching, persistence and system preference detection
 */

// Get the stored theme from localStorage
const getStoredTheme = () => localStorage.getItem('theme');

// Get preferred theme (stored or system preference)
const getPreferredTheme = () => {
    const storedTheme = getStoredTheme();
    if (storedTheme) {
        return storedTheme;
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

// Set theme on document and localStorage
const setTheme = theme => {
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
    updateThemeIcon(theme);
};

// Update theme icon based on current theme
const updateThemeIcon = theme => {
    const themeIcon = document.getElementById('theme-icon');
    if (themeIcon) {
        if (theme === 'dark') {
            themeIcon.classList.remove('bi-sun-fill');
            themeIcon.classList.add('bi-moon-fill');
        } else {
            themeIcon.classList.remove('bi-moon-fill');
            themeIcon.classList.add('bi-sun-fill');
        }
    }
};

// Toggle between light and dark themes
const toggleTheme = () => {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
};

// Initialize theme system
const initTheme = () => {
    // Set the initial theme
    setTheme(getPreferredTheme());

    // Add click handler for theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Listen for system preference changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const storedTheme = getStoredTheme();
        if (!storedTheme) {
            setTheme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        }
    });
};

// Apply the theme immediately to prevent flashing on page load
setTheme(getPreferredTheme());

// Initialize when DOM is fully loaded
document.addEventListener('DOMContentLoaded', initTheme);

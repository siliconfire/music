/** @type {import('tailwindcss').Config} */
export default {
    content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
    theme: {
        extend: {
            fontFamily: {
                // Since you installed @fontsource/google-sans-flex
                sans: ['"Google Sans Flex"', 'ui-sans-serif', 'system-ui'],
                mono: ['"Jetbrains Mono"', 'monospace'],
            },
            // Official Material 3 "Expressive" Radius Tokens
            borderRadius: {
                'm3-xs': '4px',
                'm3-sm': '8px',
                'm3-md': '12px',
                'm3-lg': '16px',
                'm3-xl': '28px',
                'm3-xxl': '32px',
                'm3-full': '1000px',
            },
        },
    },
}


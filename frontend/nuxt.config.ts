export default defineNuxtConfig({
  future: {
    compatibilityVersion: 4,
  },
  ssr: false,
  devtools: { enabled: true },
  modules: ['@vueuse/nuxt'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000/api',
    },
  },
  vite: {
    server: {
      hmr: {
        protocol: 'ws',
        host:     'localhost',
        port:     3000,
        clientPort: 3000,
      },
    },
  },
  app: {
    head: {
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap',
        },
      ],
    },
  },
})
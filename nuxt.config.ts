export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  app: { baseURL: process.env.NUXT_APP_BASE_URL || '/', head: { title: 'ВЫБОРЫ — результаты', meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }] } },
  nitro: { prerender: { routes: ['/'] } },
  css: ['~/assets/main.css']
})

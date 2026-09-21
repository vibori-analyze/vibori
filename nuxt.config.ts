import { existsSync, readFileSync } from 'node:fs'

const routeFile = new URL('./public/data/routes.json', import.meta.url)
const staticRoutes: string[] = existsSync(routeFile) ? JSON.parse(readFileSync(routeFile, 'utf8')) : ['/']

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: true },
  app: { baseURL: process.env.NUXT_APP_BASE_URL || '/', head: { title: 'ВЫБОРЫ — результаты', meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }] } },
  nitro: { prerender: { routes: staticRoutes } },
  css: ['~/assets/main.css']
})

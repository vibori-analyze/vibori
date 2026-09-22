import { existsSync, readFileSync } from 'node:fs'

const routeFile = new URL('./public/data/routes.json', import.meta.url)
const staticRoutes: string[] = existsSync(routeFile)
  ? JSON.parse(readFileSync(routeFile, 'utf8')) as string[]
  : ['/']

export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },
  experimental: { defaults: { nuxtLink: { prefetch: false } } },
  dir: {
    public: process.env.VIBORI_STATIC_BUILD ? 'public-app' : 'public',
  },
  app: {
    baseURL: process.env.NUXT_APP_BASE_URL || '/',
    head: {
      title: 'ВЫБОРЫ — результаты',
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
    },
  },
  nitro: {
    prerender: {
      routes: staticRoutes,
      // The election archive can contain hundreds of thousands of JSON files.
      // They are copied as public assets, but do not need to be treated as routes.
      ignoreUnprefixedPublicAssets: true,
    },
  },
  css: ['~/assets/main.css', '~/assets/shpilkin.css'],
})

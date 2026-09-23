<script setup lang="ts">
import type { PartyRecord } from '~/types/election'

const props = withDefaults(defineProps<{ party?: PartyRecord, size?: 'small' | 'large' }>(), { size: 'small' })
const base = useRuntimeConfig().app.baseURL.replace(/\/$/, '')
</script>

<template>
  <span v-if="party" class="party-logo" :class="`party-logo-${props.size}`">
    <img :src="`${base}/data/${party.logo}`" :alt="`Логотип партии «${party.name}»`">
  </span>
</template>

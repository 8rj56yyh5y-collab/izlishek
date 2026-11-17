<script setup lang="ts">
import { lang, setLang, t, type Lang } from '@/i18n'
import { THEMES, setTheme, theme, seg } from '@/theme'

defineProps<{ canLogout?: boolean }>()
const emit = defineEmits<{ logout: [] }>()
const langs: { v: Lang; label: string }[] = [{ v: 'uk', label: 'УКР' }, { v: 'ru', label: 'РУС' }]
</script>

<template>
  <div class="settings">
    <div class="mg-sub q-mb-xs">{{ t('settings.lang') }}</div>
    <q-btn-toggle :model-value="lang" spread no-caps unelevated dense toggle-color="primary"
      :color="seg.color" :text-color="seg.text" :options="langs.map((l) => ({ label: l.label, value: l.v }))"
      @update:model-value="setLang" />
    <div class="mg-sub q-mt-md q-mb-xs">{{ t('settings.theme') }}</div>
    <div class="themes">
      <button v-for="th in THEMES" :key="th.id" type="button" class="th" :class="{ on: theme === th.id }"
        @click="setTheme(th.id)">
        <span class="sw" :style="{ background: `linear-gradient(135deg, ${th.swatch[0]} 50%, ${th.swatch[1]} 50%)` }" />
        <span>{{ t(`theme.${th.id}`) }}</span>
      </button>
    </div>
    <q-btn v-if="canLogout" flat no-caps dense icon="logout" :label="t('settings.logout')" class="q-mt-md full-width"
      @click="emit('logout')" />
  </div>
</template>

<style scoped>
.settings { padding: 14px; width: 250px; }
.themes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.th { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 8px 4px; border-radius: 8px;
  border: 1px solid var(--mg-border-strong); background: transparent; color: var(--mg-fg); font: inherit; font-size: 12px; cursor: pointer; }
.th.on { border-color: var(--mg-primary); box-shadow: 0 0 0 1px var(--mg-primary); }
.sw { width: 30px; height: 30px; border-radius: 50%; border: 1px solid var(--mg-border-strong); }
</style>

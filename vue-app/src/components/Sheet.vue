<script setup lang="ts">
// Нижня «шторка» на телефоні, звичайне вікно на компʼютері — як у сучасних застосунках.
import { useQuasar } from 'quasar'

defineProps<{ title?: string }>()
const open = defineModel<boolean>({ required: true })
const $q = useQuasar()
</script>

<template>
  <q-dialog v-model="open" :position="$q.screen.lt.sm ? 'bottom' : 'standard'" transition-duration="220">
    <div class="sheet" :class="{ phone: $q.screen.lt.sm }">
      <div v-if="$q.screen.lt.sm" class="grip" />
      <div v-if="title" class="sheet-h">
        <div class="sheet-t">{{ title }}</div>
        <q-btn flat round dense icon="close" @click="open = false" />
      </div>
      <div class="sheet-b"><slot /></div>
      <div v-if="$slots.actions" class="sheet-f"><slot name="actions" /></div>
    </div>
  </q-dialog>
</template>

<style scoped>
.sheet { width: 460px; max-width: 96vw; background: var(--mg-bg-3); color: var(--mg-fg); border-radius: 22px;
  box-shadow: 0 24px 60px -20px rgba(0, 0, 0, 0.5); overflow: hidden; display: flex; flex-direction: column; max-height: 88vh; }
.sheet.phone { width: 100vw; max-width: 100vw; border-radius: 22px 22px 0 0; padding-bottom: env(safe-area-inset-bottom); }
.grip { width: 40px; height: 5px; border-radius: 3px; background: var(--mg-border-strong); margin: 8px auto 0; }
.sheet-h { display: flex; align-items: center; gap: 8px; padding: 14px 16px 4px 20px; }
.sheet-t { flex: 1; font-family: var(--mg-display); font-weight: 600; font-size: 18px; }
.sheet-b { padding: 8px 20px 16px; overflow-y: auto; }
.sheet-f { display: flex; gap: 8px; padding: 12px 20px 16px; border-top: 1px solid var(--mg-border); }
.sheet-f :deep(.q-btn) { flex: 1; min-height: 46px; }
</style>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { authLost } from '@/api'
import { t } from '@/i18n'
import BrandLogo from '@/components/BrandLogo.vue'
import EntryScreen from '@/components/EntryScreen.vue'
import AppSettings from '@/components/AppSettings.vue'

const router = useRouter()
const tabs = computed(() => [
  { to: '/reconcile', label: t('nav.reconcile'), icon: 'compare_arrows' },
  { to: '/', label: t('nav.overview'), icon: 'insights' },
  { to: '/shipments', label: t('nav.shipments'), icon: 'local_shipping' },
  { to: '/directory', label: t('nav.directory'), icon: 'tune' },
])

// checking → entry (заставка / вхід) → app
const stage = ref<'checking' | 'entry' | 'app'>('checking')
const needPassword = ref(false)
const passwordEnabled = ref(false)
const appKey = ref(0)

function introSeen(set = false): boolean {
  try {
    if (set) sessionStorage.setItem('bt_intro', '1')
    return sessionStorage.getItem('bt_intro') === '1'
  } catch {
    return false
  }
}

async function check() {
  try {
    const s = (await axios.get<{ required: boolean; ok: boolean }>('/api/v1/auth/status')).data
    passwordEnabled.value = s.required
    needPassword.value = s.required && !s.ok
  } catch {
    needPassword.value = false
  }
  stage.value = needPassword.value || !introSeen() ? 'entry' : 'app'
}
onMounted(check)

function entered() {
  introSeen(true)
  authLost.value = false
  appKey.value++ // перезавантажити дані сторінки після входу
  stage.value = 'app'
}

watch(authLost, (v) => {
  if (v && stage.value === 'app') {
    needPassword.value = true
    stage.value = 'entry'
  }
})

async function logout() {
  await axios.post('/api/v1/auth/logout')
  needPassword.value = true
  stage.value = 'entry'
  router.push('/reconcile')
}
</script>

<template>
  <EntryScreen v-if="stage === 'entry'" :need-password="needPassword" @done="entered" />
  <q-layout v-if="stage === 'app'" view="hHh lpR fFf" class="app-in">
    <q-header class="app-header">
      <q-toolbar class="app-toolbar">
        <router-link to="/" class="brand">
          <BrandLogo :size="26" />
          <span>{{ t('brand') }}</span>
        </router-link>
        <q-space />
        <q-tabs dense no-caps inline-label class="gt-xs" active-color="primary" indicator-color="primary">
          <q-route-tab v-for="tb in tabs" :key="tb.to" :to="tb.to" :icon="tb.icon" :label="tb.label" exact />
        </q-tabs>
        <q-btn flat round dense icon="palette" class="q-ml-sm" :aria-label="t('settings.theme')">
          <q-menu anchor="bottom right" self="top right">
            <AppSettings :can-logout="passwordEnabled" @logout="logout" />
          </q-menu>
        </q-btn>
      </q-toolbar>
    </q-header>

    <q-footer class="lt-sm app-footer">
      <q-tabs dense no-caps active-color="primary" indicator-color="transparent" class="full-width">
        <q-route-tab v-for="tb in tabs" :key="tb.to" :to="tb.to" :icon="tb.icon" :label="tb.label" exact />
      </q-tabs>
    </q-footer>

    <q-page-container>
      <router-view :key="appKey" />
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.app-in { animation: app-in 0.4s ease both; }
@keyframes app-in { from { opacity: 0; transform: translateY(6px); } }
.app-header { background: var(--mg-bg); color: var(--mg-fg); border-bottom: 1px solid var(--mg-border); }
.app-toolbar { max-width: 1280px; margin: 0 auto; width: 100%; }
.brand { display: flex; align-items: center; gap: 8px; text-decoration: none; color: var(--mg-fg);
  font-family: 'Unbounded', 'Inter', sans-serif; font-weight: 800; font-size: 17px; letter-spacing: 0.01em; }
.app-footer { background: var(--mg-bg); color: var(--mg-fg-2); border-top: 1px solid var(--mg-border); }
</style>

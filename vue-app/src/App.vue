<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { authLost } from '@/api'
import { t } from '@/i18n'
import BrandLogo from '@/components/BrandLogo.vue'
import EntryScreen from '@/components/EntryScreen.vue'
import AppSettings from '@/components/AppSettings.vue'
import ReceiverApp from '@/pages/ReceiverApp.vue'

const router = useRouter()
const tabs = computed(() => [
  { to: '/reconcile', label: t('nav.reconcile'), icon: 'compare_arrows' },
  { to: '/', label: t('nav.overview'), icon: 'insights' },
  { to: '/shipments', label: t('nav.shipments'), icon: 'local_shipping' },
  { to: '/directory', label: t('nav.directory'), icon: 'tune' },
])

interface Status { required: boolean; ok: boolean; role: string | null; receiver_mode: boolean }

// checking → entry (заставка / вхід) → app
const stage = ref<'checking' | 'entry' | 'app'>('checking')
const status = ref<Status>({ required: false, ok: false, role: null, receiver_mode: false })
const role = ref<'admin' | 'receiver'>('admin')
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
    status.value = (await axios.get<Status>('/api/v1/auth/status')).data
  } catch { /* сервер недоступний — покажемо вхід */ }
  role.value = status.value.role === 'receiver' ? 'receiver' : 'admin'
  stage.value = !status.value.ok || !introSeen() ? 'entry' : 'app'
}
onMounted(check)

function entered(r: string) {
  introSeen(true)
  authLost.value = false
  role.value = r === 'receiver' ? 'receiver' : 'admin'
  status.value = { ...status.value, ok: true, role: role.value }
  appKey.value++ // перезавантажити дані сторінки після входу
  stage.value = 'app'
}

watch(authLost, (v) => {
  if (v && stage.value === 'app') {
    status.value = { ...status.value, ok: false }
    stage.value = 'entry'
  }
})

async function logout() {
  await axios.post('/api/v1/auth/logout')
  status.value = { ...status.value, ok: false, role: null }
  stage.value = 'entry'
  router.push('/reconcile')
}
</script>

<template>
  <Transition name="fade">
    <EntryScreen v-if="stage === 'entry'" :need-password="status.required && !status.ok"
      :receiver-mode="status.receiver_mode" @done="entered" />
  </Transition>

  <ReceiverApp v-if="stage === 'app' && role === 'receiver'" :key="appKey" @logout="logout" />

  <q-layout v-else-if="stage === 'app'" view="hHh lpR fFf" class="app-in">
    <q-header class="app-header">
      <q-toolbar class="app-toolbar">
        <router-link to="/" class="brand" :aria-label="t('brand')">
          <BrandLogo :size="34" />
          <span class="brand-word gt-xs">{{ t('brand') }}</span>
        </router-link>
        <q-space />
        <nav class="nav gt-xs">
          <router-link v-for="tb in tabs" :key="tb.to" :to="tb.to" class="nav-item" exact-active-class="on">
            <q-icon :name="tb.icon" size="18px" />
            <span>{{ tb.label }}</span>
          </router-link>
        </nav>
        <q-btn flat round dense icon="tune" class="q-ml-sm" :aria-label="t('settings.title')">
          <q-menu anchor="bottom right" self="top right" :offset="[0, 8]">
            <AppSettings :can-logout="status.required" @logout="logout" />
          </q-menu>
        </q-btn>
      </q-toolbar>
    </q-header>

    <q-footer class="lt-sm app-footer">
      <nav class="tabbar">
        <router-link v-for="tb in tabs" :key="tb.to" :to="tb.to" class="tab" exact-active-class="on">
          <span class="pill"><q-icon :name="tb.icon" size="22px" /></span>
          <span class="lbl">{{ tb.label }}</span>
        </router-link>
      </nav>
    </q-footer>

    <q-page-container>
      <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="`${appKey}-${route.path}`" class="mg-page-in" />
      </router-view>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.fade-leave-active { transition: opacity 0.3s; }
.fade-leave-to { opacity: 0; }
.app-in { animation: app-in 0.5s cubic-bezier(0.16, 1, 0.3, 1) both; }
@keyframes app-in { from { opacity: 0; } }

.app-header {
  background: color-mix(in srgb, var(--mg-bg-2) 78%, transparent);
  backdrop-filter: saturate(1.4) blur(16px); -webkit-backdrop-filter: saturate(1.4) blur(16px);
  color: var(--mg-fg); border-bottom: 1px solid var(--mg-border);
}
.app-toolbar { max-width: 1280px; margin: 0 auto; width: 100%; min-height: 60px; }
.brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--mg-fg); }
.brand-word { font-family: var(--mg-display); font-weight: 700; font-size: 16px; letter-spacing: -0.01em; }

.nav { display: flex; gap: 4px; padding: 4px; border-radius: 14px; background: var(--mg-bg); border: 1px solid var(--mg-border); }
.nav-item {
  display: flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: 10px;
  color: var(--mg-fg-2); text-decoration: none; font-weight: 600; font-size: 14px;
  transition: background 0.2s, color 0.2s;
}
.nav-item:hover { color: var(--mg-fg); background: var(--mg-primary-soft); }
.nav-item.on { background: var(--mg-primary); color: var(--mg-on-primary); }

.app-footer {
  background: color-mix(in srgb, var(--mg-bg) 88%, transparent);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--mg-border); padding-bottom: env(safe-area-inset-bottom);
}
.tabbar { display: grid; grid-template-columns: repeat(4, 1fr); height: 62px; }
.tab { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; text-decoration: none; color: var(--mg-fg-3); }
.tab .pill { width: 52px; height: 30px; border-radius: 999px; display: grid; place-items: center; transition: background 0.25s, color 0.25s; }
.tab .lbl { font-size: 11px; font-weight: 600; }
.tab.on { color: var(--mg-fg); }
.tab.on .pill { background: var(--mg-primary); color: var(--mg-on-primary); }
</style>

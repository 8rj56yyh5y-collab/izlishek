<script setup lang="ts">
const tabs = [
  { to: '/reconcile', label: 'Звірка', icon: 'compare_arrows' },
  { to: '/', label: 'Огляд', icon: 'insights' },
  { to: '/shipments', label: 'Відвантаження', icon: 'local_shipping' },
  { to: '/directory', label: 'Довідники', icon: 'tune' },
]
</script>

<template>
  <q-layout view="hHh lpR fFf">
    <q-header class="app-header">
      <q-toolbar class="app-toolbar">
        <div class="brand">
          <q-icon name="scale" size="22px" />
          <span>Надлишки приймальника</span>
        </div>
        <q-space />
        <q-tabs dense no-caps inline-label class="gt-xs" active-color="primary" indicator-color="primary">
          <q-route-tab v-for="t in tabs" :key="t.to" :to="t.to" :icon="t.icon" :label="t.label" exact />
        </q-tabs>
      </q-toolbar>
    </q-header>

    <q-footer class="lt-sm app-footer">
      <q-tabs dense no-caps active-color="primary" indicator-color="transparent" class="full-width">
        <q-route-tab v-for="t in tabs" :key="t.to" :to="t.to" :icon="t.icon" :label="t.label" exact />
      </q-tabs>
    </q-footer>

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<style scoped>
.app-header {
  background: var(--mg-bg);
  color: var(--mg-fg);
  border-bottom: 1px solid var(--mg-border);
}
.app-toolbar { max-width: 1280px; margin: 0 auto; width: 100%; }
.brand { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; color: var(--mg-primary); }
.brand span { color: var(--mg-fg); }
.app-footer { background: var(--mg-bg); color: var(--mg-fg-2); border-top: 1px solid var(--mg-border); }
</style>

<script setup lang="ts">
import { t } from '@/i18n'
import { onMounted, ref, watch } from 'vue'
import { cleanParams, http, type Period, type ShipmentListItem } from '@/api'
import { dateUa, devClass, devKg, devMoney, kg } from '@/format'
import PeriodFilter from '@/components/PeriodFilter.vue'
import ShipmentDialog from '@/components/ShipmentDialog.vue'

const period = ref<Period>({ date_from: null, date_to: null, point_id: null })
const items = ref<ShipmentListItem[]>([])
const loading = ref(false)
const open = ref(false)
const currentId = ref<number | null>(null)

async function load() {
  loading.value = true
  try {
    items.value = (await http.get<ShipmentListItem[]>('/shipments', { params: cleanParams(period.value) })).data
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(period, load, { deep: true })

function edit(id: number | null) {
  currentId.value = id
  open.value = true
}
</script>

<template>
  <q-page class="page">
    <div class="row items-center q-mb-md">
      <h1 class="mg-h">{{ t('sh.listTitle') }}</h1>
      <q-space />
      <q-btn unelevated no-caps color="primary" icon="compare_arrows" :label="t('sh.new')" to="/reconcile" />
    </div>
    <PeriodFilter v-model="period" class="q-mb-md" />

    <div class="mg-card">
      <div v-if="!items.length && !loading" class="empty">{{ t('sh.none') }}</div>
      <div v-for="s in items" :key="s.id" class="item" @click="edit(s.id)">
        <div class="date num">{{ dateUa(s.ship_date) }}</div>
        <div class="who">
          <div class="text-weight-medium">{{ s.receiver_name }}</div>
          <div class="mg-sub">{{ s.point_name }} → {{ s.destination }} · {{ s.lines_count }} {{ t('sh.items') }} · {{ kg(s.totals.point_kg) }} {{ t('common.kg') }}</div>
        </div>
        <div class="split num gt-xs">
          <span class="dev-pos">{{ devKg(s.totals.surplus_kg) }}</span>
          <span class="mg-muted"> / </span>
          <span class="dev-neg">{{ devKg(s.totals.shortage_kg) }}</span>
          <div class="mg-sub">{{ t('sh.split') }}</div>
        </div>
        <div class="total">
          <div class="num text-weight-bold" :class="devClass(s.totals.deviation_amount)">{{ devMoney(s.totals.deviation_amount) }}</div>
          <div class="mg-sub num">{{ devKg(s.totals.deviation_kg) }} {{ t('common.kg') }}</div>
        </div>
        <q-icon name="chevron_right" color="grey-5" />
      </div>
      <q-inner-loading :showing="loading" />
    </div>

    <ShipmentDialog v-model="open" :shipment-id="currentId" @saved="load" @deleted="load" />
  </q-page>
</template>

<style scoped>
.page { max-width: 1080px; margin: 0 auto; padding: 20px 16px 32px; }
.empty { padding: 32px 16px; text-align: center; color: var(--mg-fg-3); }
.item { display: flex; align-items: center; gap: 14px; padding: 12px 16px; border-bottom: 1px solid var(--mg-border); cursor: pointer; }
.item:last-child { border-bottom: 0; }
.item:hover { background: var(--mg-bg-2); }
.date { width: 84px; color: var(--mg-fg-2); font-weight: 500; }
.who { flex: 1; min-width: 0; }
.split { text-align: right; width: 170px; }
.total { text-align: right; width: 110px; }
@media (max-width: 600px) {
  .item { gap: 10px; padding: 12px; }
  .date { width: 72px; font-size: 13px; }
}
</style>

<script setup lang="ts">
import { t } from '@/i18n'
import { computed, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { http, type LedgerRow, type ReceiverBalance, type Summary } from '@/api'
import { dateUa, devClass, devKg, devMoney } from '@/format'
import ShipmentDialog from '@/components/ShipmentDialog.vue'
import SettlementDialog from '@/components/SettlementDialog.vue'

const props = defineProps<{ name: string }>()
const $q = useQuasar()
const rows = ref<LedgerRow[]>([])
const balance = ref<ReceiverBalance | null>(null)
const shipOpen = ref(false)
const shipId = ref<number | null>(null)
const settleOpen = ref(false)

async function load() {
  const [l, s] = await Promise.all([
    http.get<LedgerRow[]>(`/receivers/${encodeURIComponent(props.name)}/ledger`),
    http.get<Summary>('/summary'),
  ])
  rows.value = l.data
  balance.value = s.data.receivers.find((r) => r.receiver_name === props.name) ?? null
}
onMounted(load)

const owed = computed(() => balance.value?.materials.filter((m) => m.balance_kg < -0.0005) ?? [])

function open(r: LedgerRow) {
  if (r.kind === 'shipment') {
    shipId.value = r.ref_id
    shipOpen.value = true
    return
  }
  $q.dialog({ title: t('st.cancelQ'), message: `${r.material_name}: ${devKg(r.kg)} ${t('common.kg')}`, cancel: { label: t('common.cancel'), flat: true }, ok: { label: t('common.delete'), color: 'negative' } })
    .onOk(async () => {
      await http.delete(`/settlements/${r.ref_id}`)
      load()
    })
}
</script>

<template>
  <q-page class="page">
    <q-btn flat dense no-caps icon="arrow_back" :label="t('rc.back')" color="primary" to="/" class="q-mb-sm" />
    <div class="row items-center q-mb-md q-gutter-sm">
      <div>
        <h1 class="mg-h">{{ name }}</h1>
        <div v-if="balance" class="mg-sub">{{ balance.shipments }} {{ t('rc.shipments') }}</div>
      </div>
      <q-space />
      <q-btn unelevated no-caps color="primary" icon="task_alt" :label="t('st.title')" @click="settleOpen = true" />
    </div>

    <div v-if="balance" class="mg-card q-pa-md q-mb-md">
      <div class="row items-end q-gutter-lg">
        <div>
          <div class="mg-sub">{{ t('ov.balance') }}</div>
          <div class="num bal" :class="devClass(balance.balance_amount)">{{ devMoney(balance.balance_amount) }}</div>
          <div class="mg-sub num">{{ devKg(balance.balance_kg) }} {{ t('common.kg') }}</div>
        </div>
        <div v-if="owed.length" class="col">
          <div class="mg-sub q-mb-xs">{{ t('rc.owes') }}</div>
          <div class="chips">
            <span v-for="m in owed" :key="m.material_id" class="chip num">{{ m.material_name }} · {{ devKg(-m.balance_kg).replace('+', '') }} {{ t('common.kg') }}</span>
          </div>
        </div>
        <div v-else class="col mg-sub">{{ t('rc.noDebt') }}</div>
      </div>
    </div>

    <div class="mg-card">
      <div v-if="!rows.length" class="empty">{{ t('rc.none') }}</div>
      <table v-else class="tbl">
        <thead>
          <tr><th>{{ t('common.date') }}</th><th>{{ t('rc.event') }}</th><th>{{ t('common.material') }}</th><th class="r">{{ t('common.kg') }}</th><th class="r gt-xs">₴</th><th class="r">{{ t('rc.balKg') }}</th><th class="r gt-xs">{{ t('rc.balUah') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="i" class="clk" @click="open(r)">
            <td class="num">{{ dateUa(r.on_date) }}</td>
            <td>
              <q-icon :name="r.kind === 'shipment' ? 'local_shipping' : 'task_alt'" size="16px"
                :color="r.kind === 'shipment' ? 'grey-6' : 'primary'" class="q-mr-xs" />
              <span class="gt-xs">{{ r.title }}</span>
            </td>
            <td>{{ r.material_name }}</td>
            <td class="r num" :class="devClass(r.kg)">{{ devKg(r.kg) }}</td>
            <td class="r num gt-xs" :class="devClass(r.amount)">{{ devMoney(r.amount) }}</td>
            <td class="r num" :class="devClass(r.balance_kg)">{{ devKg(r.balance_kg) }}</td>
            <td class="r num gt-xs" :class="devClass(r.balance_amount)">{{ devMoney(r.balance_amount) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <ShipmentDialog v-model="shipOpen" :shipment-id="shipId" @saved="load" @deleted="load" />
    <SettlementDialog v-model="settleOpen" :receiver="name" @saved="load" />
  </q-page>
</template>

<style scoped>
.page { max-width: 1080px; margin: 0 auto; padding: 12px 16px 32px; }
.bal { font-size: 26px; font-weight: 700; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { background: var(--mg-negative-soft); color: var(--mg-negative); border-radius: 999px; padding: 3px 10px; font-size: 13px; font-weight: 500; }
.empty { padding: 32px 16px; text-align: center; color: var(--mg-fg-3); }
.r { text-align: right; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th { font-weight: 600; color: var(--mg-fg-3); font-size: 12px; text-align: left; padding: 8px; border-bottom: 1px solid var(--mg-border); }
.tbl th.r { text-align: right; }
.tbl td { padding: 8px; border-bottom: 1px solid var(--mg-border); }
.tbl th:first-child, .tbl td:first-child { padding-left: 16px; }
.tbl th:last-child, .tbl td:last-child { padding-right: 16px; }
.clk { cursor: pointer; }
.clk:hover { background: var(--mg-bg-2); }
</style>

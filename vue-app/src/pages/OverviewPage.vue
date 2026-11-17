<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { cleanParams, http, type Period, type ReceiverBalance, type Summary } from '@/api'
import { devClass, devKg, devMoney, devPct, kg } from '@/format'
import PeriodFilter from '@/components/PeriodFilter.vue'
import DeviationChart from '@/components/DeviationChart.vue'
import ShipmentDialog from '@/components/ShipmentDialog.vue'
import SettlementDialog from '@/components/SettlementDialog.vue'

const router = useRouter()
const period = ref<Period>({ date_from: null, date_to: null, point_id: null })
const data = ref<Summary | null>(null)
const loading = ref(false)
const expanded = ref<string[]>([])

const shipOpen = ref(false)
const shipId = ref<number | null>(null)
const settle = ref({ open: false, receiver: '', materialId: null as number | null, kg: null as number | null })

async function load() {
  loading.value = true
  try {
    data.value = (await http.get<Summary>('/summary', { params: cleanParams(period.value) })).data
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(period, load, { deep: true })

function openShipment(id: number | null) {
  shipId.value = id
  shipOpen.value = true
}
function openSettle(r: ReceiverBalance, materialId: number | null = null, balance: number | null = null) {
  settle.value = { open: true, receiver: r.receiver_name, materialId, kg: balance === null ? null : -balance }
}
function toggle(name: string) {
  expanded.value = expanded.value.includes(name) ? expanded.value.filter((x) => x !== name) : [...expanded.value, name]
}
function exportXlsx() {
  const q = new URLSearchParams(cleanParams(period.value) as Record<string, string>).toString()
  window.location.href = `/api/v1/surplus/export.xlsx${q ? '?' + q : ''}`
}
</script>

<template>
  <q-page class="page">
    <div class="row items-center q-mb-md q-gutter-sm">
      <div>
        <h1 class="mg-h">Відхилення по відвантаженнях</h1>
        <div class="mg-sub">Склад мінус пункт: «+» — надлишок, «−» — недостача, яку приймальник має заготовити</div>
      </div>
      <q-space />
      <q-btn outline no-caps color="primary" icon="download" label="Excel" @click="exportXlsx" />
      <q-btn unelevated no-caps color="primary" icon="add" label="Відвантаження" @click="openShipment(null)" />
    </div>

    <PeriodFilter v-model="period" class="q-mb-md" />

    <template v-if="data">
      <div class="kpis q-mb-md">
        <div class="mg-card kpi">
          <div class="mg-sub">Відвантажень</div>
          <div class="kpi-v num">{{ data.shipments }}</div>
          <div class="mg-sub num">{{ kg(data.totals.point_kg) }} кг за пунктом</div>
        </div>
        <div class="mg-card kpi">
          <div class="mg-sub">Надлишок</div>
          <div class="kpi-v num dev-pos">{{ devKg(data.totals.surplus_kg) }} кг</div>
          <div class="mg-sub num">{{ devMoney(data.totals.surplus_amount) }}</div>
        </div>
        <div class="mg-card kpi">
          <div class="mg-sub">Недостача</div>
          <div class="kpi-v num dev-neg">{{ devKg(data.totals.shortage_kg) }} кг</div>
          <div class="mg-sub num">{{ devMoney(data.totals.shortage_amount) }}</div>
        </div>
        <div class="mg-card kpi">
          <div class="mg-sub">Разом за період</div>
          <div class="kpi-v num" :class="devClass(data.totals.deviation_amount)">{{ devMoney(data.totals.deviation_amount) }}</div>
          <div class="mg-sub num">
            {{ devKg(data.totals.deviation_kg) }} кг ·
            {{ devPct(data.totals.point_kg ? (data.totals.deviation_kg / data.totals.point_kg) * 100 : null) }}
          </div>
        </div>
      </div>

      <div class="mg-card q-pa-md q-mb-md">
        <div class="row items-baseline q-mb-xs">
          <div class="text-weight-medium">Після кожного відвантаження, ₴</div>
          <q-space />
          <div class="mg-sub">натисніть на стовпчик, щоб відкрити</div>
        </div>
        <DeviationChart v-if="data.timeline.length" :points="data.timeline" @pick="openShipment" />
        <div v-else class="empty">За період відвантажень немає</div>
      </div>

      <div class="cols">
        <div class="mg-card">
          <div class="card-h">
            <div class="text-weight-medium">Баланс приймальників</div>
            <div class="mg-sub">за всю історію на кінець періоду, з урахуванням погашень</div>
          </div>
          <div v-if="!data.receivers.length" class="empty">Поки порожньо</div>
          <div v-for="r in data.receivers" :key="r.receiver_name" class="rcv">
            <div class="rcv-row" @click="toggle(r.receiver_name)">
              <q-icon :name="expanded.includes(r.receiver_name) ? 'expand_less' : 'expand_more'" color="grey-6" />
              <div class="rcv-name">
                <div class="text-weight-medium">{{ r.receiver_name }}</div>
                <div class="mg-sub">{{ r.shipments }} відвант. ·
                  <span class="dev-pos">{{ devKg(r.surplus_kg) }}</span> /
                  <span class="dev-neg">{{ devKg(r.shortage_kg) }}</span> кг
                </div>
              </div>
              <div class="r">
                <div class="num text-weight-bold" :class="devClass(r.balance_amount)">{{ devMoney(r.balance_amount) }}</div>
                <div class="mg-sub num">{{ devKg(r.balance_kg) }} кг</div>
              </div>
            </div>
            <q-slide-transition>
              <div v-show="expanded.includes(r.receiver_name)" class="rcv-detail">
                <table class="tbl">
                  <thead>
                    <tr><th>Матеріал</th><th class="r">Відхил.</th><th class="r">Погаш.</th><th class="r">Баланс</th><th class="r">₴</th><th /></tr>
                  </thead>
                  <tbody>
                    <tr v-for="m in r.materials" :key="m.material_id">
                      <td>{{ m.material_name }}</td>
                      <td class="r num" :class="devClass(m.deviation_kg)">{{ devKg(m.deviation_kg) }}</td>
                      <td class="r num mg-muted">{{ m.settled_kg ? devKg(m.settled_kg) : '' }}</td>
                      <td class="r num" :class="devClass(m.balance_kg)">{{ devKg(m.balance_kg) }}</td>
                      <td class="r num" :class="devClass(m.balance_amount)">{{ devMoney(m.balance_amount) }}</td>
                      <td class="r">
                        <q-btn v-if="Math.abs(m.balance_kg) > 0.0005" flat dense no-caps size="sm" color="primary"
                          :label="m.balance_kg < 0 ? 'Заготовив' : 'Списати'"
                          @click.stop="openSettle(r, m.material_id, m.balance_kg)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <div class="row q-mt-sm">
                  <q-btn flat dense no-caps color="primary" icon="history" label="Історія приймальника"
                    @click="router.push(`/receivers/${encodeURIComponent(r.receiver_name)}`)" />
                </div>
              </div>
            </q-slide-transition>
          </div>
        </div>

        <div class="mg-card">
          <div class="card-h">
            <div class="text-weight-medium">По матеріалах</div>
            <div class="mg-sub">за обраний період</div>
          </div>
          <div v-if="!data.materials.length" class="empty">Поки порожньо</div>
          <table v-else class="tbl pad">
            <thead>
              <tr><th>Матеріал</th><th class="r">Пункт, кг</th><th class="r">Відхил., кг</th><th class="r">%</th><th class="r">₴</th></tr>
            </thead>
            <tbody>
              <tr v-for="m in data.materials" :key="m.material_id">
                <td>{{ m.material_name }}</td>
                <td class="r num">{{ kg(m.point_kg) }}</td>
                <td class="r num" :class="devClass(m.deviation_kg)">{{ devKg(m.deviation_kg) }}</td>
                <td class="r num" :class="devClass(m.deviation_kg)">{{ devPct(m.deviation_pct) }}</td>
                <td class="r num" :class="devClass(m.deviation_amount)">{{ devMoney(m.deviation_amount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
    <q-inner-loading :showing="loading && !data" />

    <ShipmentDialog v-model="shipOpen" :shipment-id="shipId" @saved="load" @deleted="load" />
    <SettlementDialog v-model="settle.open" :receiver="settle.receiver" :material-id="settle.materialId"
      :suggest-kg="settle.kg" @saved="load" />
  </q-page>
</template>

<style scoped>
.page { max-width: 1280px; margin: 0 auto; padding: 20px 16px 32px; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.kpi { padding: 14px 16px; }
.kpi-v { font-size: 24px; font-weight: 700; margin: 2px 0; }
.cols { display: grid; grid-template-columns: 1.1fr 1fr; gap: 12px; align-items: start; }
.card-h { padding: 14px 16px 10px; border-bottom: 1px solid var(--mg-border); }
.empty { padding: 24px 16px; text-align: center; color: var(--mg-fg-3); }
.rcv { border-bottom: 1px solid var(--mg-border); }
.rcv:last-child { border-bottom: 0; }
.rcv-row { display: flex; align-items: center; gap: 10px; padding: 10px 16px; cursor: pointer; }
.rcv-row:hover { background: var(--mg-bg-2); }
.rcv-name { flex: 1; min-width: 0; }
.rcv-detail { padding: 0 16px 12px 42px; }
.r { text-align: right; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th { font-weight: 600; color: var(--mg-fg-3); font-size: 12px; text-align: left; padding: 6px 6px; border-bottom: 1px solid var(--mg-border); }
.tbl th.r { text-align: right; }
.tbl td { padding: 6px; border-bottom: 1px solid var(--mg-border); }
.tbl tr:last-child td { border-bottom: 0; }
.tbl.pad { margin: 4px 0; }
.tbl.pad th:first-child, .tbl.pad td:first-child { padding-left: 16px; }
.tbl.pad th:last-child, .tbl.pad td:last-child { padding-right: 16px; }
@media (max-width: 900px) {
  .kpis { grid-template-columns: 1fr 1fr; }
  .cols { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .kpi-v { font-size: 19px; }
  .rcv-detail { padding-left: 16px; overflow-x: auto; }
}
</style>

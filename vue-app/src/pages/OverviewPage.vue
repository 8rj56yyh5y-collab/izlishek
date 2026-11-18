<script setup lang="ts">
// «Головна»: одна велика цифра за період, коротко хто в мінусі й де розходиться. Без таблиць.
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { cleanParams, http, type Point, type Submission, type Summary } from '@/api'
import { devClass, devKg, devMoney, devPct, kg } from '@/format'
import { lang, t } from '@/i18n'
import { periodKey, periodOptions, periodRange, setPeriod } from '@/period'
import MiniBars from '@/components/MiniBars.vue'
import ShipmentDialog from '@/components/ShipmentDialog.vue'

const router = useRouter()
const data = ref<Summary | null>(null)
const points = ref<Point[]>([])
const pointId = ref<number | null>(null)
const pendingN = ref(0)
const loading = ref(false)
const allMats = ref(false)

const params = computed(() => cleanParams({ ...periodRange.value, point_id: pointId.value }))

async function load() {
  loading.value = true
  try {
    data.value = (await http.get<Summary>('/summary', { params: params.value })).data
  } finally {
    loading.value = false
  }
}
onMounted(async () => {
  load()
  points.value = (await http.get<Point[]>('/points')).data
  pendingN.value = (await http.get<Submission[]>('/pending')).data.length
})
watch(params, load)

const accBy = computed(() => new Map((data.value?.accuracy ?? []).map((a) => [a.receiver_name, a])))
const trendIcon = { better: 'trending_down', worse: 'trending_up', same: 'trending_flat' } as const
const fmtPct = (v: number | null) => (v === null ? '—' : v.toLocaleString('uk-UA', { maximumFractionDigits: 1 }))
const mats = computed(() => {
  const list = [...(data.value?.materials ?? [])].filter((m) => Math.abs(m.deviation_kg) > 0.0005)
    .sort((a, b) => Math.abs(b.deviation_amount) - Math.abs(a.deviation_amount) || Math.abs(b.deviation_kg) - Math.abs(a.deviation_kg))
  return allMats.value ? list : list.slice(0, 5)
})
const matMax = computed(() => Math.max(1, ...(data.value?.materials ?? []).map((m) => Math.abs(m.deviation_kg))))
const pointOpts = computed(() => [{ label: t('common.allPoints'), value: null }, ...points.value.map((p) => ({ label: p.name, value: p.id }))])

const shipOpen = ref(false)
const shipId = ref<number | null>(null)
function openShipment(id: number) {
  shipId.value = id
  shipOpen.value = true
}
function exportXlsx() {
  const q = new URLSearchParams(params.value as Record<string, string>).toString()
  window.location.href = `/api/v1/surplus/export.xlsx?lang=${lang.value}${q ? '&' + q : ''}`
}
</script>

<template>
  <q-page class="page">
    <header class="top">
      <h1 class="mg-h">{{ t('home.title') }}</h1>
      <q-btn flat round icon="download" :aria-label="'Excel'" @click="exportXlsx"><q-tooltip>Excel</q-tooltip></q-btn>
    </header>

    <div class="chips">
      <button v-for="o in periodOptions" :key="o.k" type="button" class="chip" :class="{ on: periodKey === o.k }" @click="setPeriod(o.k)">
        {{ o.label }}
      </button>
      <q-select v-if="points.length > 1" v-model="pointId" :options="pointOpts" emit-value map-options dense borderless
        class="chip sel" options-dense />
    </div>

    <template v-if="data">
      <section class="hero" :class="devClass(data.totals.deviation_amount)">
        <div class="hero-k">{{ t('home.total') }}</div>
        <div class="hero-v num">{{ devMoney(data.totals.deviation_amount) }}</div>
        <div class="hero-row num">
          <span><b class="dev-pos">{{ devKg(data.totals.surplus_kg) }}</b> {{ t('home.plus') }}</span>
          <span><b class="dev-neg">{{ devKg(data.totals.shortage_kg) }}</b> {{ t('home.minus') }}</span>
          <span class="mg-muted">{{ t('home.count', { n: data.shipments }) }} · {{ devPct(data.totals.point_kg ? (data.totals.deviation_kg / data.totals.point_kg) * 100 : null) }}</span>
        </div>
        <MiniBars v-if="data.timeline.length > 1" :points="data.timeline" class="hero-bars" @pick="openShipment" />
      </section>

      <button v-if="pendingN" type="button" class="pending" @click="router.push('/reconcile')">
        <span class="dot" /> {{ t('home.pending', { n: pendingN }) }}
        <q-space /><q-icon name="arrow_forward" />
      </button>

      <div v-if="!data.shipments && !data.receivers.length" class="empty">
        <q-icon name="inventory_2" size="40px" />
        <div>{{ t('home.empty') }}</div>
      </div>

      <h2 v-if="data.receivers.length" class="sec">{{ t('home.receivers') }}</h2>
      <div class="rcv-grid">
        <button v-for="r in data.receivers" :key="r.receiver_name" type="button" class="rcv"
          @click="router.push(`/receivers/${encodeURIComponent(r.receiver_name)}`)">
          <div class="rcv-top">
            <div class="avatar">{{ r.receiver_name.slice(0, 1).toUpperCase() }}</div>
            <div class="rcv-name">
              <div class="text-weight-bold ellipsis">{{ r.receiver_name }}</div>
              <div v-if="accBy.get(r.receiver_name)?.abs_pct != null" class="acc">
                {{ t('ov.acc', { pct: fmtPct(accBy.get(r.receiver_name)!.abs_pct) }) }}
                <span v-if="accBy.get(r.receiver_name)!.trend" class="trend" :class="accBy.get(r.receiver_name)!.trend!">
                  <q-icon :name="trendIcon[accBy.get(r.receiver_name)!.trend!]" size="14px" />{{ t(`ov.${accBy.get(r.receiver_name)!.trend!}`) }}
                </span>
              </div>
            </div>
            <div class="rcv-bal">
              <div class="num" :class="devClass(r.balance_amount)">{{ devMoney(r.balance_amount) }}</div>
              <div class="mg-sub num">{{ devKg(r.balance_kg) }} {{ t('common.kg') }}</div>
            </div>
          </div>
          <div class="owe">
            <template v-if="r.materials.some((m) => m.balance_kg < -0.0005)">
              <span class="mg-sub">{{ t('home.toCollect') }}:</span>
              <span v-for="m in r.materials.filter((x) => x.balance_kg < -0.0005).sort((a, b) => a.balance_kg - b.balance_kg).slice(0, 3)"
                :key="m.material_id" class="tag num">{{ m.material_name }} {{ kg(-m.balance_kg) }}</span>
            </template>
            <span v-else class="mg-sub"><q-icon name="check_circle" color="positive" size="15px" /> {{ t('home.allClear') }}</span>
          </div>
        </button>
      </div>

      <template v-if="mats.length">
        <h2 class="sec">{{ t('home.materials') }}</h2>
        <section class="mats">
          <div v-for="m in mats" :key="m.material_id" class="mat">
            <div class="mat-top">
              <span class="ellipsis">{{ m.material_name }}</span>
              <span class="num" :class="devClass(m.deviation_kg)">{{ devKg(m.deviation_kg) }} {{ t('common.kg') }}</span>
            </div>
            <div class="track"><span :class="m.deviation_kg > 0 ? 'p' : 'n'" :style="{ width: `${Math.max(4, Math.abs(m.deviation_kg) / matMax * 100)}%` }" /></div>
            <div class="mat-bot mg-sub num">
              <span>{{ kg(m.point_kg) }} {{ t('common.kg') }} · {{ devPct(m.deviation_pct) }}</span>
              <span :class="devClass(m.deviation_amount)">{{ devMoney(m.deviation_amount) }}</span>
            </div>
          </div>
          <q-btn v-if="(data.materials.filter((x) => Math.abs(x.deviation_kg) > 0.0005).length) > 5" flat no-caps dense color="primary"
            :label="allMats ? t('home.showLess') : t('home.showAll')" class="q-mt-xs" @click="allMats = !allMats" />
        </section>
      </template>
    </template>
    <div v-else class="skel"><q-skeleton height="180px" class="q-mb-md" style="border-radius: 22px" /><q-skeleton height="96px" style="border-radius: 18px" /></div>

    <ShipmentDialog v-model="shipOpen" :shipment-id="shipId" @saved="load" @deleted="load" />
  </q-page>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 16px 16px 110px; }
.top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; margin-bottom: 14px; padding-bottom: 2px; }
.chip { flex: 0 0 auto; height: 36px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--mg-border); background: var(--mg-bg);
  color: var(--mg-fg-2); font: 600 14px 'Inter', sans-serif; cursor: pointer; transition: all 0.15s; }
.chip.on { background: var(--mg-fg); color: var(--mg-bg); border-color: var(--mg-fg); }
.chip.sel { padding: 0 6px 0 12px; display: flex; align-items: center; }
.chip.sel :deep(.q-field__control), .chip.sel :deep(.q-field__native) { min-height: 34px; height: 34px; }

.hero { padding: 20px; border-radius: 24px; background: var(--mg-bg); border: 1px solid var(--mg-border); box-shadow: var(--mg-shadow); }
.hero.dev-neg { background: radial-gradient(120% 140% at 0% 0%, var(--mg-negative-soft), transparent 60%), var(--mg-bg); }
.hero.dev-pos { background: radial-gradient(120% 140% at 0% 0%, var(--mg-positive-soft), transparent 60%), var(--mg-bg); }
.hero-k { font-size: 13px; font-weight: 600; color: var(--mg-fg-3); }
.hero-v { font-family: var(--mg-display); font-size: clamp(36px, 9vw, 52px); font-weight: 700; line-height: 1.1; margin: 4px 0 8px; }
.hero-row { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 14px; color: var(--mg-fg-2); }
.hero-bars { margin-top: 16px; }

.pending { display: flex; align-items: center; gap: 10px; width: 100%; margin-top: 12px; padding: 14px 16px; border-radius: 18px; cursor: pointer;
  font: 700 15px 'Inter', sans-serif; color: var(--mg-fg); background: var(--mg-primary-soft);
  border: 1px solid color-mix(in srgb, var(--mg-primary) 45%, transparent); }
.pending .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--mg-primary); box-shadow: 0 0 0 4px var(--mg-primary-soft); }

.sec { font-family: var(--mg-display); font-size: 17px; font-weight: 600; margin: 26px 0 10px; }
.rcv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 10px; }
.rcv { text-align: left; font: inherit; color: var(--mg-fg); cursor: pointer; padding: 14px 16px; border-radius: 20px;
  background: var(--mg-bg); border: 1px solid var(--mg-border); transition: transform 0.15s, border-color 0.15s; }
.rcv:hover { border-color: var(--mg-border-strong); }
.rcv:active { transform: scale(0.99); }
.rcv-top { display: flex; align-items: center; gap: 12px; }
.avatar { flex: 0 0 auto; width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; font-weight: 800; font-size: 18px;
  background: var(--mg-primary-soft); color: var(--mg-primary); }
.rcv-name { flex: 1; min-width: 0; }
.acc { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--mg-fg-3); margin-top: 2px; }
.trend { display: inline-flex; align-items: center; gap: 2px; font-weight: 700; padding: 0 6px; border-radius: 999px; font-size: 12px; }
.trend.better { color: var(--mg-positive); background: var(--mg-positive-soft); }
.trend.worse { color: var(--mg-negative); background: var(--mg-negative-soft); }
.trend.same { color: var(--mg-fg-2); background: var(--mg-bg-2); }
.rcv-bal { text-align: right; }
.rcv-bal > .num { font-family: var(--mg-display); font-size: 20px; font-weight: 700; }
.owe { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--mg-border); }
.tag { font-size: 12px; font-weight: 600; padding: 3px 9px; border-radius: 999px; background: var(--mg-negative-soft); color: var(--mg-negative); }

.mats { padding: 6px 16px 10px; border-radius: 20px; background: var(--mg-bg); border: 1px solid var(--mg-border); }
.mat { padding: 10px 0; border-bottom: 1px solid var(--mg-border); }
.mat:last-of-type { border-bottom: 0; }
.mat-top { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; }
.track { height: 6px; border-radius: 3px; background: var(--mg-bg-2); margin: 7px 0 5px; overflow: hidden; }
.track span { display: block; height: 100%; border-radius: 3px; }
.track .p { background: var(--mg-positive); }
.track .n { background: var(--mg-negative); }
.mat-bot { display: flex; justify-content: space-between; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 40px 16px; color: var(--mg-fg-3); text-align: center; }
</style>

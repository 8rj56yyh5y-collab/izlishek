<script setup lang="ts">
// «Історія»: збережені звірки, згруповані по місяцях. Тап — відкрити, виправити, видалити.
import { computed, onMounted, ref, watch } from 'vue'
import { cleanParams, http, type ShipmentListItem } from '@/api'
import { devClass, devKg, devMoney, kg } from '@/format'
import { lang, t } from '@/i18n'
import { periodKey, periodOptions, periodRange, setPeriod } from '@/period'
import ShipmentDialog from '@/components/ShipmentDialog.vue'

const items = ref<ShipmentListItem[]>([])
const loading = ref(false)
const open = ref(false)
const currentId = ref<number | null>(null)

async function load() {
  loading.value = true
  try {
    items.value = (await http.get<ShipmentListItem[]>('/shipments', { params: cleanParams(periodRange.value) })).data
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(periodRange, load)

const groups = computed(() => {
  const loc = lang.value === 'ru' ? 'ru-RU' : 'uk-UA'
  const out: { key: string; title: string; total: number; items: ShipmentListItem[] }[] = []
  for (const s of items.value) {
    const key = s.ship_date.slice(0, 7)
    let g = out.find((x) => x.key === key)
    if (!g) {
      const d = new Date(`${key}-01T00:00:00`)
      const title = d.toLocaleDateString(loc, { month: 'long', year: 'numeric' }).replace(' р.', '').replace(' г.', '')
      g = { key, title: title.charAt(0).toUpperCase() + title.slice(1), total: 0, items: [] }
      out.push(g)
    }
    g.items.push(s)
    g.total += s.totals.deviation_amount
  }
  return out
})
const day = (iso: string) => iso.slice(8, 10)
const wd = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(lang.value === 'ru' ? 'ru-RU' : 'uk-UA', { weekday: 'short' })

function edit(id: number) {
  currentId.value = id
  open.value = true
}
</script>

<template>
  <q-page class="page">
    <header class="top">
      <h1 class="mg-h">{{ t('sh.listTitle') }}</h1>
    </header>
    <div class="chips">
      <button v-for="o in periodOptions" :key="o.k" type="button" class="chip" :class="{ on: periodKey === o.k }" @click="setPeriod(o.k)">
        {{ o.label }}
      </button>
    </div>

    <div v-if="!items.length && !loading" class="empty">
      <q-icon name="history" size="40px" />
      <div>{{ t('hist.empty') }}</div>
    </div>

    <section v-for="g in groups" :key="g.key" class="grp">
      <div class="grp-h">
        <span>{{ g.title }}</span>
        <span class="num" :class="devClass(g.total)">{{ devMoney(g.total) }}</span>
      </div>
      <div class="list">
        <button v-for="s in g.items" :key="s.id" type="button" class="item" @click="edit(s.id)">
          <div class="date">
            <div class="d num">{{ day(s.ship_date) }}</div>
            <div class="w">{{ wd(s.ship_date) }}</div>
          </div>
          <div class="who">
            <div class="text-weight-bold ellipsis">{{ s.receiver_name }}</div>
            <div class="mg-sub ellipsis">{{ s.point_name }} · {{ s.lines_count }} {{ t('sh.items') }} · {{ kg(s.totals.point_kg) }} {{ t('common.kg') }}</div>
          </div>
          <div class="total">
            <div class="num v" :class="devClass(s.totals.deviation_amount)">{{ devMoney(s.totals.deviation_amount) }}</div>
            <div class="mg-sub num">{{ devKg(s.totals.deviation_kg) }} {{ t('common.kg') }}</div>
          </div>
        </button>
      </div>
    </section>

    <ShipmentDialog v-model="open" :shipment-id="currentId" @saved="load" @deleted="load" />
  </q-page>
</template>

<style scoped>
.page { max-width: 900px; margin: 0 auto; padding: 16px 16px 110px; }
.top { margin-bottom: 10px; }
.chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; margin-bottom: 8px; }
.chip { flex: 0 0 auto; height: 36px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--mg-border); background: var(--mg-bg);
  color: var(--mg-fg-2); font: 600 14px 'Inter', sans-serif; cursor: pointer; }
.chip.on { background: var(--mg-fg); color: var(--mg-bg); border-color: var(--mg-fg); }
.empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 48px 16px; color: var(--mg-fg-3); }
.grp { margin-top: 18px; }
.grp-h { display: flex; justify-content: space-between; padding: 0 4px 8px; font-weight: 700; color: var(--mg-fg-2); }
.list { border-radius: 20px; background: var(--mg-bg); border: 1px solid var(--mg-border); overflow: hidden; }
.item { display: flex; align-items: center; gap: 14px; width: 100%; padding: 12px 16px; border: 0; border-bottom: 1px solid var(--mg-border);
  background: transparent; color: var(--mg-fg); font: inherit; text-align: left; cursor: pointer; }
.item:last-child { border-bottom: 0; }
.item:active { background: var(--mg-bg-2); }
.date { flex: 0 0 auto; width: 44px; height: 46px; border-radius: 14px; background: var(--mg-bg-2); display: flex; flex-direction: column;
  align-items: center; justify-content: center; }
.date .d { font-family: var(--mg-display); font-weight: 700; font-size: 17px; line-height: 1; }
.date .w { font-size: 11px; color: var(--mg-fg-3); text-transform: uppercase; margin-top: 3px; }
.who { flex: 1; min-width: 0; }
.total { text-align: right; }
.total .v { font-family: var(--mg-display); font-weight: 700; font-size: 17px; }
</style>

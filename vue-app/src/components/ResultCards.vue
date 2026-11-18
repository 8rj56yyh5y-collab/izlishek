<script setup lang="ts">
// Результат звірки картками: «облік → склад» і крупно відхилення кольором. Тап — правка в шторці.
// Заміна таблиці: на телефоні читається з першого погляду, нічого не треба гортати вбік.
import { computed, ref } from 'vue'
import type { Material } from '@/api'
import { devClass, devKg, devMoney, devPct, kg } from '@/format'
import { t } from '@/i18n'
import { num, type Row } from '@/lines'
import Sheet from './Sheet.vue'

const rows = defineModel<Row[]>({ required: true })
const props = defineProps<{ materials: Material[] }>()

const matById = computed(() => new Map(props.materials.map((m) => [m.id, m])))
const priceOf = (r: Row) => r.price_per_kg ?? (r.material_id ? matById.value.get(r.material_id)?.price_per_kg ?? 0 : 0)
const show = (v: string) => (num(v) === null ? '—' : kg(num(v)!))
const nameOf = (r: Row) => (r.material_id ? matById.value.get(r.material_id)?.name : null)

function calc(r: Row) {
  const a = num(r.point_kg)
  const b = num(r.warehouse_kg)
  if (a === null || b === null) return null
  const dev = Math.round((b - a) * 1000) / 1000
  return { dev, pct: a ? (dev / a) * 100 : null, amount: dev * priceOf(r) }
}

const totals = computed(() => {
  let dev = 0, amount = 0, plus = 0, minus = 0, book = 0, wh = 0
  for (const r of rows.value) {
    const c = calc(r)
    if (!c) continue
    book += num(r.point_kg)!
    wh += num(r.warehouse_kg)!
    dev += c.dev
    amount += c.amount
    if (c.dev > 0) plus += c.dev
    else minus += c.dev
  }
  const r3 = (v: number) => Math.round(v * 1000) / 1000
  return { dev: r3(dev), amount, plus: r3(plus), minus: r3(minus), book: r3(book), wh: r3(wh) }
})
const noPrice = computed(() => rows.value.filter((r) => r.material_id && calc(r) && !priceOf(r)).map((r) => nameOf(r)))

// Порядок: спершу мінуси (найважливіше), потім плюси, потім неповні й невпізнані.
const ordered = computed(() => rows.value
  .map((r, i) => ({ r, i, c: calc(r) }))
  .sort((a, b) => {
    const ka = !a.r.material_id ? 3 : !a.c ? 2 : 0
    const kb = !b.r.material_id ? 3 : !b.c ? 2 : 0
    if (ka !== kb) return ka - kb
    return (a.c?.amount ?? 0) - (b.c?.amount ?? 0)
  }))

// ── шторка редагування ──
const editOpen = ref(false)
const editIdx = ref<number | null>(null)
const draft = ref<Row>({ material_id: null, point_kg: '', warehouse_kg: '', price_per_kg: null })
const draftCalc = computed(() => calc(draft.value))
const filterText = ref('')
const options = computed(() => {
  const used = new Set(rows.value.filter((_, i) => i !== editIdx.value).map((r) => r.material_id))
  return props.materials.filter((m) => m.is_active && (m.id === draft.value.material_id || !used.has(m.id)))
    .map((m) => ({ label: m.name, value: m.id }))
})

const filtered = computed(() => options.value.filter((o) => o.label.toLowerCase().includes(filterText.value.toLowerCase())))

function onFilter(val: string, update: (fn: () => void) => void) {
  update(() => { filterText.value = val })
}

function edit(i: number) {
  editIdx.value = i
  draft.value = { ...rows.value[i] }
  editOpen.value = true
}
function add() {
  editIdx.value = null
  draft.value = { material_id: null, point_kg: '', warehouse_kg: '', price_per_kg: null }
  editOpen.value = true
}
function commit() {
  if (editIdx.value === null) {
    if (draft.value.material_id || draft.value.point_kg || draft.value.warehouse_kg) rows.value.push({ ...draft.value })
  } else rows.value[editIdx.value] = { ...draft.value }
  editOpen.value = false
}
function remove() {
  if (editIdx.value !== null) rows.value.splice(editIdx.value, 1)
  editOpen.value = false
}
</script>

<template>
  <div>
    <section class="sum" :class="devClass(totals.amount)">
      <div class="sum-l">
        <div class="sum-k">{{ t('res.summary') }}</div>
        <div class="sum-v num">{{ devMoney(totals.amount) }}</div>
      </div>
      <div class="sum-r num">
        <div><span class="dev-pos">{{ devKg(totals.plus) }}</span> <span class="mg-muted">{{ t('home.plus') }}</span></div>
        <div><span class="dev-neg">{{ devKg(totals.minus) }}</span> <span class="mg-muted">{{ t('home.minus') }}</span></div>
        <div class="mg-muted">{{ kg(totals.book) }} → {{ kg(totals.wh) }} {{ t('common.kg') }}</div>
      </div>
    </section>
    <div v-if="noPrice.length" class="noprice">
      <q-icon name="info" size="16px" /> {{ t('lines.noPrice', { names: noPrice.join(', ') }) }}
    </div>

    <div class="cards">
      <button v-for="{ r, i, c } in ordered" :key="i" type="button" class="card"
        :class="[!r.material_id ? 'unk' : c ? (c.dev > 0.0005 ? 'pos' : c.dev < -0.0005 ? 'neg' : 'zero') : 'half']" @click="edit(i)">
        <div class="c-top">
          <span class="c-name">{{ nameOf(r) ?? (r.raw ? `«${r.raw}»` : t('lines.pickMaterial')) }}</span>
          <span v-if="c" class="c-dev num" :class="devClass(c.dev)">{{ devKg(c.dev) }} <small>{{ t('common.kg') }}</small></span>
        </div>
        <div class="c-bot num">
          <span>
            <span class="mg-muted">{{ t('res.book') }}</span> {{ show(r.point_kg) }}
            <q-icon name="arrow_forward" size="13px" class="mg-muted" />
            <span class="mg-muted">{{ t('res.wh') }}</span> {{ show(r.warehouse_kg) }}
          </span>
          <span v-if="c" :class="devClass(c.amount)">{{ devMoney(c.amount) }} · {{ devPct(c.pct) }}</span>
          <span v-else-if="!r.material_id" class="warn">{{ t('lines.pickMaterial') }}</span>
          <span v-else class="mg-muted">{{ r.point_kg ? t('res.noWh') : t('res.noBook') }}</span>
        </div>
      </button>
      <button type="button" class="card add" @click="add">
        <q-icon name="add" size="20px" /> {{ t('res.add') }}
      </button>
    </div>

    <Sheet v-model="editOpen" :title="t('res.edit')">
      <q-select v-model="draft.material_id" :options="filtered" emit-value map-options outlined use-input fill-input hide-selected
        input-debounce="0" :label="t('common.material')" class="q-mb-sm"
        @filter="onFilter" />
      <div v-if="!draft.material_id && draft.raw" class="warn q-mb-sm">{{ t('lines.seenAs', { raw: draft.raw }) }}</div>
      <div class="two">
        <q-input v-model="draft.point_kg" outlined inputmode="decimal" :label="t('lines.receiverKg')" input-class="num big-in" />
        <q-input v-model="draft.warehouse_kg" outlined inputmode="decimal" :label="t('lines.warehouseKg')" input-class="num big-in" />
      </div>
      <div v-if="draftCalc" class="preview num" :class="devClass(draftCalc.dev)">
        {{ devKg(draftCalc.dev) }} {{ t('common.kg') }} · {{ devMoney(draftCalc.amount) }}
      </div>
      <template #actions>
        <q-btn v-if="editIdx !== null" flat no-caps color="negative" icon="delete_outline" :label="t('res.delete')" @click="remove" />
        <q-btn unelevated no-caps color="primary" :label="t('step.done')" @click="commit" />
      </template>
    </Sheet>
  </div>
</template>

<style scoped>
.sum { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 20px; border-radius: 20px;
  background: var(--mg-bg); border: 1px solid var(--mg-border); box-shadow: var(--mg-shadow); }
.sum.dev-neg { background: linear-gradient(135deg, var(--mg-negative-soft), transparent 70%), var(--mg-bg); }
.sum.dev-pos { background: linear-gradient(135deg, var(--mg-positive-soft), transparent 70%), var(--mg-bg); }
.sum-k { font-size: 13px; color: var(--mg-fg-3); font-weight: 600; }
.sum-v { font-family: var(--mg-display); font-size: 34px; font-weight: 700; line-height: 1.15; }
.sum-r { text-align: right; font-size: 13px; line-height: 1.6; }
.noprice { margin-top: 8px; font-size: 13px; color: var(--mg-warning); }

.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px; margin-top: 12px; }
.card { text-align: left; font: inherit; color: var(--mg-fg); cursor: pointer; padding: 12px 14px 12px 16px; border-radius: 16px;
  background: var(--mg-bg); border: 1px solid var(--mg-border); position: relative; overflow: hidden;
  transition: transform 0.15s ease, border-color 0.15s; }
.card:active { transform: scale(0.985); }
.card::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: transparent; }
.card.pos::before { background: var(--mg-positive); }
.card.neg::before { background: var(--mg-negative); }
.card.unk::before { background: var(--mg-warning); }
.card.unk { background: linear-gradient(90deg, var(--mg-warning-soft), transparent 60%), var(--mg-bg); }
.card.half { opacity: 0.85; }
.c-top { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.c-name { font-weight: 600; font-size: 15px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.c-dev { font-family: var(--mg-display); font-size: 20px; font-weight: 700; }
.c-dev small { font-size: 12px; font-weight: 600; }
.c-bot { display: flex; justify-content: space-between; gap: 8px; margin-top: 4px; font-size: 13px; flex-wrap: wrap; }
.card.add { display: flex; align-items: center; justify-content: center; gap: 6px; color: var(--mg-primary); font-weight: 700;
  border-style: dashed; min-height: 64px; }
.warn { color: var(--mg-warning); font-size: 13px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.two :deep(.big-in) { font-size: 20px; font-weight: 600; }
.preview { margin-top: 12px; font-family: var(--mg-display); font-size: 22px; font-weight: 700; text-align: center; }
</style>

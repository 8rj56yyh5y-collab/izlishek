<script setup lang="ts">
import { computed } from 'vue'
import type { Material } from '@/api'
import { devClass, devKg, devMoney, devPct } from '@/format'
import { num, type Row } from '@/lines'
import { t } from '@/i18n'

const rows = defineModel<Row[]>({ required: true })
const props = defineProps<{ materials: Material[] }>()

const matById = computed(() => new Map(props.materials.map((m) => [m.id, m])))
const priceOf = (r: Row) => r.price_per_kg ?? (r.material_id ? matById.value.get(r.material_id)?.price_per_kg ?? 0 : 0)

function calc(r: Row) {
  const a = num(r.point_kg)
  const b = num(r.warehouse_kg)
  if (a === null || b === null) return null
  const dev = Math.round((b - a) * 1000) / 1000
  return { dev, pct: a ? (dev / a) * 100 : null, amount: dev * priceOf(r) }
}

const totals = computed(() => {
  let point = 0, wh = 0, dev = 0, amount = 0, surplus = 0, shortage = 0
  for (const r of rows.value) {
    const c = calc(r)
    if (!c) continue
    point += num(r.point_kg)!
    wh += num(r.warehouse_kg)!
    dev += c.dev
    amount += c.amount
    if (c.dev > 0) surplus += c.dev
    else shortage += c.dev
  }
  const r3 = (v: number) => Math.round(v * 1000) / 1000
  return { point: r3(point), wh: r3(wh), dev: r3(dev), amount, surplus: r3(surplus), shortage: r3(shortage) }
})

// Матеріали з вагою, але без ціни: гроші по них = 0, про це треба сказати прямо.
const noPrice = computed(() => rows.value
  .filter((r) => r.material_id && calc(r) && !priceOf(r))
  .map((r) => matById.value.get(r.material_id!)?.name ?? ''))

const usedIds = computed(() => new Set(rows.value.map((r) => r.material_id)))
const materialOptions = (current: number | null) =>
  props.materials
    .filter((m) => m.is_active && (m.id === current || !usedIds.value.has(m.id)))
    .map((m) => ({ label: m.name, value: m.id }))

function rowClass(r: Row) {
  const c = calc(r)
  if (!r.material_id) return 'row-unknown'
  if (!c) return num(r.point_kg) !== null || num(r.warehouse_kg) !== null ? 'row-half' : ''
  return c.dev > 0.0005 ? 'row-pos' : c.dev < -0.0005 ? 'row-neg' : ''
}

function fillAll() {
  for (const m of props.materials.filter((x) => x.is_active)) {
    if (!usedIds.value.has(m.id)) rows.value.push({ material_id: m.id, point_kg: '', warehouse_kg: '', price_per_kg: null })
  }
}
</script>

<template>
  <div>
    <div class="grid grid-head">
      <div>{{ t('common.material') }}</div>
      <div class="r">{{ t('lines.receiverKg') }}</div>
      <div class="r">{{ t('lines.warehouseKg') }}</div>
      <div class="r">{{ t('lines.deviation') }}</div>
      <div class="r gt-xs">₴</div>
      <div />
    </div>
    <div v-for="(r, i) in rows" :key="i" class="grid grid-row" :class="rowClass(r)">
      <div class="mat">
        <q-select
          v-model="r.material_id" :options="materialOptions(r.material_id)" emit-value map-options dense borderless
          :placeholder="r.raw ? t('lines.pickMaterial') : t('common.material')"
        />
        <div v-if="!r.material_id && r.raw" class="raw">{{ t('lines.seenAs', { raw: r.raw }) }}</div>
      </div>
      <q-input v-model="r.point_kg" dense outlined inputmode="decimal" input-class="text-right num" />
      <q-input v-model="r.warehouse_kg" dense outlined inputmode="decimal" input-class="text-right num" />
      <div class="r num">
        <template v-if="calc(r)">
          <span :class="devClass(calc(r)!.dev)">{{ devKg(calc(r)!.dev) }}</span>
          <div class="mg-sub">{{ devPct(calc(r)!.pct) }}</div>
        </template>
        <span v-else class="mg-muted">—</span>
      </div>
      <div class="r num gt-xs">
        <span v-if="calc(r)" :class="devClass(calc(r)!.amount)">{{ devMoney(calc(r)!.amount) }}</span>
      </div>
      <q-btn flat round dense size="sm" icon="close" color="grey-6" @click="rows.splice(i, 1)" />
    </div>
    <div class="row q-gutter-sm q-mt-sm">
      <q-btn flat no-caps dense icon="add" :label="t('lines.addRow')" color="primary"
        @click="rows.push({ material_id: null, point_kg: '', warehouse_kg: '', price_per_kg: null })" />
      <q-btn flat no-caps dense icon="playlist_add" :label="t('lines.allMaterials')" color="primary" @click="fillAll" />
    </div>

    <div class="legend mg-sub q-mt-sm">
      <span><i class="sw sw-pos" /> {{ t('lines.legendPlus') }}</span>
      <span><i class="sw sw-neg" /> {{ t('lines.legendMinus') }}</span>
      <span><i class="sw sw-unk" /> {{ t('lines.legendUnknown') }}</span>
    </div>

    <div class="totals q-mt-md">
      <div><div class="mg-sub">{{ t('common.receiver') }}</div><div class="num big">{{ devKg(totals.point).replace('+', '') }} {{ t('common.kg') }}</div></div>
      <div><div class="mg-sub">{{ t('common.warehouse') }}</div><div class="num big">{{ devKg(totals.wh).replace('+', '') }} {{ t('common.kg') }}</div></div>
      <div><div class="mg-sub">{{ t('lines.plus') }}</div><div class="num big dev-pos">{{ devKg(totals.surplus) }} {{ t('common.kg') }}</div></div>
      <div><div class="mg-sub">{{ t('lines.minus') }}</div><div class="num big dev-neg">{{ devKg(totals.shortage) }} {{ t('common.kg') }}</div></div>
      <div>
        <div class="mg-sub">{{ t('lines.total') }}</div>
        <div class="num big" :class="devClass(totals.amount)">{{ devMoney(totals.amount) }}</div>
        <div class="mg-sub num">{{ devKg(totals.dev) }} {{ t('common.kg') }}</div>
      </div>
    </div>
    <div v-if="noPrice.length" class="noprice mg-sub">
      <q-icon name="info" size="16px" /> {{ t('lines.noPrice', { names: noPrice.join(', ') }) }}
    </div>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: minmax(150px, 1.6fr) 120px 120px 100px 100px 32px; gap: 8px; align-items: center; }
.grid-head { font-size: 12px; color: var(--mg-fg-3); font-weight: 600; padding: 0 8px 4px; border-bottom: 1px solid var(--mg-border); }
.grid-row { padding: 4px 8px; border-bottom: 1px solid var(--mg-border); border-left: 4px solid transparent; }
.row-pos { background: var(--mg-positive-soft); border-left-color: var(--mg-positive); }
.row-neg { background: var(--mg-negative-soft); border-left-color: var(--mg-negative); }
.row-unknown { background: var(--mg-warning-soft); border-left-color: var(--mg-warning); }
.row-half { border-left-color: var(--mg-border-strong); }
.raw { font-size: 12px; color: var(--mg-warning); margin-top: -4px; }
.r { text-align: right; }
.mat :deep(.q-field__native) { font-weight: 500; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; vertical-align: -1px; margin-right: 4px; }
.sw-pos { background: var(--mg-positive); }
.sw-neg { background: var(--mg-negative); }
.sw-unk { background: var(--mg-warning); }
.noprice { margin-top: 8px; color: var(--mg-warning); }
.totals { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; background: var(--mg-bg-2); padding: 12px 16px; border-radius: var(--mg-radius-md); }
.big { font-size: 17px; font-weight: 600; }
@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr 1fr 72px 28px; gap: 4px 6px; }
  .grid-head > div:first-child { display: none; }
  .grid-row .mat { grid-column: 1 / -1; }
  .grid-row { padding: 4px 6px; }
  .totals { grid-template-columns: 1fr 1fr; }
}
</style>

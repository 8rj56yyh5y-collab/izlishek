<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type Material, type Point, type Shipment } from '@/api'
import { devClass, devKg, devMoney, devPct, todayIso } from '@/format'

const props = defineProps<{ shipmentId: number | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: []; deleted: [] }>()
const $q = useQuasar()

interface Row { material_id: number | null; point_kg: string; warehouse_kg: string; price_per_kg: number | null }

const points = ref<Point[]>([])
const materials = ref<Material[]>([])
const form = ref({ ship_date: todayIso(), point_id: null as number | null, receiver_name: '', destination: 'ДМС', note: '' })
const rows = ref<Row[]>([])
const saving = ref(false)
const loading = ref(false)

const num = (s: string) => {
  const v = parseFloat(String(s).replace(',', '.').replace(/\s/g, ''))
  return Number.isFinite(v) ? v : null
}
const matById = computed(() => new Map(materials.value.map((m) => [m.id, m])))
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

const usedIds = computed(() => new Set(rows.value.map((r) => r.material_id)))
const materialOptions = (current: number | null) =>
  materials.value
    .filter((m) => m.is_active && (m.id === current || !usedIds.value.has(m.id)))
    .map((m) => ({ label: m.name, value: m.id }))

const pointOptions = computed(() => points.value.filter((p) => p.is_active || p.id === form.value.point_id)
  .map((p) => ({ label: p.name, value: p.id, receiver: p.receiver_name })))

function onPoint(id: number) {
  form.value.point_id = id
  form.value.receiver_name = points.value.find((p) => p.id === id)?.receiver_name ?? ''
}

function fillAll() {
  for (const m of materials.value.filter((x) => x.is_active)) {
    if (!usedIds.value.has(m.id)) rows.value.push({ material_id: m.id, point_kg: '', warehouse_kg: '', price_per_kg: null })
  }
  rows.value = rows.value.filter((r) => r.material_id !== null)
}

async function load() {
  loading.value = true
  try {
    const [p, m] = await Promise.all([http.get<Point[]>('/points'), http.get<Material[]>('/materials')])
    points.value = p.data
    materials.value = m.data
    if (props.shipmentId) {
      const sh = (await http.get<Shipment>(`/shipments/${props.shipmentId}`)).data
      form.value = { ship_date: sh.ship_date, point_id: sh.point_id, receiver_name: sh.receiver_name, destination: sh.destination, note: sh.note ?? '' }
      rows.value = sh.lines.map((l) => ({
        material_id: l.material_id, point_kg: String(l.point_kg), warehouse_kg: String(l.warehouse_kg), price_per_kg: l.price_per_kg,
      }))
    } else {
      const first = points.value.find((x) => x.is_active)
      form.value = { ship_date: todayIso(), point_id: null, receiver_name: '', destination: 'ДМС', note: '' }
      if (first) onPoint(first.id)
      rows.value = []
      fillAll()
    }
  } finally {
    loading.value = false
  }
}
watch(open, (v) => v && load())

async function save() {
  const lines = rows.value
    .filter((r) => r.material_id && (r.point_kg !== '' || r.warehouse_kg !== ''))
    .map((r) => ({
      material_id: r.material_id,
      point_kg: num(r.point_kg) ?? 0,
      warehouse_kg: num(r.warehouse_kg) ?? 0,
      price_per_kg: r.price_per_kg,
    }))
  if (!form.value.point_id) return $q.notify({ type: 'warning', message: 'Оберіть пункт' })
  if (!lines.length) return $q.notify({ type: 'warning', message: 'Внесіть вагу хоча б по одному матеріалу' })
  saving.value = true
  try {
    const body = { ...form.value, note: form.value.note || null, lines }
    if (props.shipmentId) await http.put(`/shipments/${props.shipmentId}`, body)
    else await http.post('/shipments', body)
    $q.notify({ type: 'positive', message: 'Відвантаження збережено' })
    open.value = false
    emit('saved')
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    saving.value = false
  }
}

function remove() {
  $q.dialog({ title: 'Видалити відвантаження?', message: 'Відхилення зникнуть з балансу приймальника.', cancel: true, ok: { label: 'Видалити', color: 'negative' } })
    .onOk(async () => {
      await http.delete(`/shipments/${props.shipmentId}`)
      open.value = false
      emit('deleted')
    })
}
</script>

<template>
  <q-dialog v-model="open" :maximized="$q.screen.lt.sm" persistent>
    <q-card class="dlg">
      <q-card-section class="row items-center q-pb-sm">
        <div class="mg-h">{{ shipmentId ? 'Відвантаження' : 'Нове відвантаження' }}</div>
        <q-space />
        <q-btn flat round dense icon="close" @click="open = false" />
      </q-card-section>

      <q-inner-loading :showing="loading" />

      <q-card-section class="q-pt-none">
        <div class="head">
          <q-input v-model="form.ship_date" type="date" dense outlined label="Дата" />
          <q-select
            :model-value="form.point_id" :options="pointOptions" emit-value map-options dense outlined label="Пункт"
            @update:model-value="onPoint"
          />
          <q-input v-model="form.receiver_name" dense outlined label="Приймальник" hint="Хто відповідає за плюс/мінус" />
          <q-input v-model="form.destination" dense outlined label="Склад-отримувач" />
        </div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <div class="grid grid-head">
          <div>Матеріал</div>
          <div class="r">Пункт («Я»), кг</div>
          <div class="r">Склад, кг</div>
          <div class="r">Відхилення</div>
          <div class="r gt-xs">₴</div>
          <div />
        </div>
        <div v-for="(r, i) in rows" :key="i" class="grid grid-row">
          <q-select
            v-model="r.material_id" :options="materialOptions(r.material_id)" emit-value map-options dense borderless
            placeholder="Матеріал" class="mat"
          />
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
          <q-btn flat no-caps dense icon="add" label="Рядок" color="primary"
            @click="rows.push({ material_id: null, point_kg: '', warehouse_kg: '', price_per_kg: null })" />
          <q-btn flat no-caps dense icon="playlist_add" label="Усі матеріали" color="primary" @click="fillAll" />
        </div>
      </q-card-section>

      <q-card-section class="totals">
        <div><div class="mg-sub">Пункт</div><div class="num big">{{ devKg(totals.point).replace('+', '') }} кг</div></div>
        <div><div class="mg-sub">Склад</div><div class="num big">{{ devKg(totals.wh).replace('+', '') }} кг</div></div>
        <div><div class="mg-sub">Надлишок</div><div class="num big dev-pos">{{ devKg(totals.surplus) }} кг</div></div>
        <div><div class="mg-sub">Недостача</div><div class="num big dev-neg">{{ devKg(totals.shortage) }} кг</div></div>
        <div>
          <div class="mg-sub">Разом для приймальника</div>
          <div class="num big" :class="devClass(totals.amount)">{{ devMoney(totals.amount) }}</div>
          <div class="mg-sub num">{{ devKg(totals.dev) }} кг</div>
        </div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-input v-model="form.note" dense outlined autogrow label="Примітка" />
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md">
        <q-btn v-if="shipmentId" flat no-caps color="negative" icon="delete" label="Видалити" @click="remove" />
        <q-space />
        <q-btn flat no-caps label="Скасувати" @click="open = false" />
        <q-btn unelevated no-caps color="primary" label="Зберегти" :loading="saving" @click="save" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.dlg { width: 860px; max-width: 96vw; border-radius: var(--mg-radius-lg); }
.head { display: grid; grid-template-columns: 150px 1fr 1fr 140px; gap: 8px; }
.grid { display: grid; grid-template-columns: minmax(150px, 1.6fr) 120px 120px 100px 100px 32px; gap: 8px; align-items: center; }
.grid-head { font-size: 12px; color: var(--mg-fg-3); font-weight: 600; padding: 0 0 4px; border-bottom: 1px solid var(--mg-border); }
.grid-row { padding: 4px 0; border-bottom: 1px solid var(--mg-border); }
.r { text-align: right; }
.mat :deep(.q-field__native) { font-weight: 500; }
.totals { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; background: var(--mg-bg-2); margin: 0 16px; border-radius: var(--mg-radius-md); }
.big { font-size: 17px; font-weight: 600; }
@media (max-width: 600px) {
  .dlg { border-radius: 0; }
  .head { grid-template-columns: 1fr 1fr; }
  .grid { grid-template-columns: 1fr 1fr 72px 28px; gap: 4px 6px; }
  .grid-head > div:first-child { display: none; }
  .grid-row .mat { grid-column: 1 / -1; }
  .totals { grid-template-columns: 1fr 1fr; }
}
</style>

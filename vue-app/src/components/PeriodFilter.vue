<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { http, type Period, type Point } from '@/api'

const model = defineModel<Period>({ required: true })
const points = ref<Point[]>([])

onMounted(async () => {
  points.value = (await http.get<Point[]>('/points')).data
})

const iso = (d: Date) => d.toLocaleDateString('sv-SE')
const presets = computed(() => {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth()
  return [
    { key: 'month', label: 'Цей місяць', from: iso(new Date(y, m, 1)), to: iso(new Date(y, m + 1, 0)) },
    { key: 'prev', label: 'Минулий', from: iso(new Date(y, m - 1, 1)), to: iso(new Date(y, m, 0)) },
    { key: 'year', label: 'Рік', from: `${y}-01-01`, to: `${y}-12-31` },
    { key: 'all', label: 'Усе', from: null, to: null },
  ]
})
const active = computed(
  () => presets.value.find((p) => p.from === (model.value.date_from ?? null) && p.to === (model.value.date_to ?? null))?.key,
)
function pick(p: { from: string | null; to: string | null }) {
  model.value = { ...model.value, date_from: p.from, date_to: p.to }
}
const pointOptions = computed(() => [
  { label: 'Усі пункти', value: null },
  ...points.value.map((p) => ({ label: `${p.name} · ${p.receiver_name}`, value: p.id })),
])
</script>

<template>
  <div class="filters">
    <q-btn-toggle
      :model-value="active"
      no-caps unelevated dense toggle-color="primary" color="white" text-color="grey-9"
      class="toggle"
      :options="presets.map((p) => ({ label: p.label, value: p.key }))"
      @update:model-value="(k: string) => pick(presets.find((p) => p.key === k)!)"
    />
    <q-input
      :model-value="model.date_from ?? ''" type="date" dense outlined label="З" class="date"
      @update:model-value="(v) => (model = { ...model, date_from: (v as string) || null })"
    />
    <q-input
      :model-value="model.date_to ?? ''" type="date" dense outlined label="По" class="date"
      @update:model-value="(v) => (model = { ...model, date_to: (v as string) || null })"
    />
    <q-select
      :model-value="model.point_id ?? null" :options="pointOptions" emit-value map-options dense outlined
      label="Пункт" class="point"
      @update:model-value="(v) => (model = { ...model, point_id: v })"
    />
  </div>
</template>

<style scoped>
.filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.toggle { border: 1px solid var(--mg-border-strong); border-radius: var(--mg-radius-md); }
.date { width: 150px; }
.point { min-width: 220px; }
@media (max-width: 600px) {
  .date { flex: 1 1 130px; }
  .point { flex: 1 1 100%; }
}
</style>

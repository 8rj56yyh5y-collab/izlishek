<script setup lang="ts">
import { t } from '@/i18n'
import { onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type Material, type Point } from '@/api'

const $q = useQuasar()
const points = ref<Point[]>([])
const materials = ref<Material[]>([])

async function load() {
  const [p, m] = await Promise.all([http.get<Point[]>('/points'), http.get<Material[]>('/materials')])
  points.value = p.data
  materials.value = m.data
}
onMounted(load)

async function savePoint(p: Partial<Point>) {
  try {
    const body = { name: p.name, receiver_name: p.receiver_name, is_active: p.is_active ?? true }
    if (p.id) await http.put(`/points/${p.id}`, body)
    else await http.post('/points', body)
    $q.notify({ type: 'positive', message: t('common.saved'), timeout: 900 })
    load()
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  }
}
async function saveMaterial(m: Partial<Material>) {
  try {
    const body = { name: m.name, aliases: m.aliases ?? null, group: m.group ?? 'color', price_per_kg: m.price_per_kg ?? 0, sort: m.sort ?? 100, is_active: m.is_active ?? true }
    if (m.id) await http.put(`/materials/${m.id}`, body)
    else await http.post('/materials', body)
    $q.notify({ type: 'positive', message: t('common.saved'), timeout: 900 })
    load()
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  }
}

const newPoint = ref({ name: '', receiver_name: '' })
const newMat = ref({ name: '', price_per_kg: '' })
function addPoint() {
  if (!newPoint.value.name || !newPoint.value.receiver_name) return
  savePoint({ ...newPoint.value }).then(() => (newPoint.value = { name: '', receiver_name: '' }))
}
function addMat() {
  if (!newMat.value.name) return
  saveMaterial({ name: newMat.value.name, price_per_kg: parseFloat(newMat.value.price_per_kg.replace(',', '.')) || 0, sort: (materials.value.length + 1) * 10 })
    .then(() => (newMat.value = { name: '', price_per_kg: '' }))
}
</script>

<template>
  <q-page class="page">
    <h1 class="mg-h q-mb-md">{{ t('dir.title') }}</h1>
    <div class="cols">
      <div class="mg-card">
        <div class="card-h">
          <div class="text-weight-medium">{{ t('dir.points') }}</div>
          <div class="mg-sub">{{ t('dir.pointsSub') }}</div>
        </div>
        <div v-for="p in points" :key="p.id" class="line">
          <q-input v-model="p.name" dense borderless class="col" @change="savePoint(p)" />
          <q-input v-model="p.receiver_name" dense borderless class="col" @change="savePoint(p)" />
          <q-toggle v-model="p.is_active" dense @update:model-value="savePoint(p)">
            <q-tooltip>{{ t('dir.active') }}</q-tooltip>
          </q-toggle>
        </div>
        <div class="line add">
          <q-input v-model="newPoint.name" dense outlined :placeholder="t('dir.newPoint')" class="col" />
          <q-input v-model="newPoint.receiver_name" dense outlined :placeholder="t('common.receiver')" class="col" @keyup.enter="addPoint" />
          <q-btn flat round dense icon="add" color="primary" @click="addPoint" />
        </div>
      </div>

      <div class="mg-card">
        <div class="card-h">
          <div class="text-weight-medium">{{ t('dir.materials') }}</div>
          <div class="mg-sub">{{ t('dir.materialsSub') }}</div>
        </div>
        <div v-for="m in materials" :key="m.id" class="line">
          <div class="col">
            <q-input v-model="m.name" dense borderless @change="saveMaterial(m)" />
            <q-input v-model="m.aliases" dense borderless :placeholder="t('dir.aliases')" class="alias"
              @change="saveMaterial(m)">
              <q-tooltip>{{ t('dir.aliasesTip') }}</q-tooltip>
            </q-input>
          </div>
          <q-input v-model.number="m.price_per_kg" type="number" dense outlined suffix="₴" class="price" :class="{ noprice: !m.price_per_kg }"
            input-class="text-right num" @change="saveMaterial(m)" />
          <q-toggle v-model="m.is_active" dense @update:model-value="saveMaterial(m)">
            <q-tooltip>{{ t('dir.showNew') }}</q-tooltip>
          </q-toggle>
        </div>
        <div class="line add">
          <q-input v-model="newMat.name" dense outlined :placeholder="t('dir.newMaterial')" class="col" />
          <q-input v-model="newMat.price_per_kg" dense outlined :placeholder="t('dir.price')" suffix="₴" class="price"
            inputmode="decimal" @keyup.enter="addMat" />
          <q-btn flat round dense icon="add" color="primary" @click="addMat" />
        </div>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.page { max-width: 1080px; margin: 0 auto; padding: 20px 16px 32px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
.card-h { padding: 14px 16px 10px; border-bottom: 1px solid var(--mg-border); }
.line { display: flex; align-items: center; gap: 8px; padding: 2px 16px; border-bottom: 1px solid var(--mg-border); }
.line.add { padding: 10px 16px; border-bottom: 0; }
.price { width: 110px; }
.alias { margin-top: -10px; }
.noprice :deep(.q-field__control) { box-shadow: inset 0 0 0 1px var(--mg-warning); }
.alias :deep(input) { font-size: 12px; color: var(--mg-fg-3); }
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }
</style>

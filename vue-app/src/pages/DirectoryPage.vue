<script setup lang="ts">
import { t } from '@/i18n'
import { onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import axios from 'axios'
import { apiError, http, type Material, type Point } from '@/api'

const $q = useQuasar()
const points = ref<Point[]>([])
const materials = ref<Material[]>([])

// «Версія приймальника»: перемикач і PIN кожного пункту
const receiverMode = ref(false)
const passwordOn = ref(true)
const pins = ref<Record<number, string>>({})
const quotes = ref('')

async function load() {
  const [p, m, s, st] = await Promise.all([
    http.get<Point[]>('/points'), http.get<Material[]>('/materials'),
    http.get<{ receiver_mode: boolean; quotes: string }>('/settings'), axios.get<{ required: boolean }>('/api/v1/auth/status'),
  ])
  points.value = p.data
  materials.value = m.data
  receiverMode.value = s.data.receiver_mode
  quotes.value = s.data.quotes ?? ''
  passwordOn.value = st.data.required
}

async function setReceiverMode(v: boolean) {
  receiverMode.value = v
  await http.put('/settings', { receiver_mode: v })
  $q.notify({ type: 'positive', message: t('common.saved'), timeout: 900 })
}

async function saveQuotes() {
  await http.put('/settings', { receiver_mode: receiverMode.value, quotes: quotes.value })
  $q.notify({ type: 'positive', message: t('common.saved'), timeout: 900 })
}

async function savePin(p: Point, remove = false) {
  const pin = remove ? null : (pins.value[p.id] ?? '').trim()
  if (!remove && !/^\d{4,8}$/.test(pin ?? '')) return $q.notify({ type: 'warning', message: t('dir.pinBad') })
  try {
    await http.put(`/points/${p.id}/pin`, { pin })
    pins.value[p.id] = ''
    $q.notify({ type: 'positive', message: t('common.saved'), timeout: 900 })
    load()
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  }
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
      <div class="left">
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

      <div class="mg-card rcv">
        <div class="card-h row items-center no-wrap">
          <div class="col">
            <div class="text-weight-medium">{{ t('dir.rcvMode') }}</div>
            <div class="mg-sub">{{ t('dir.rcvModeSub') }}</div>
          </div>
          <q-toggle :model-value="receiverMode" color="primary" @update:model-value="setReceiverMode" />
        </div>
        <template v-if="receiverMode">
          <div v-if="!passwordOn" class="warn"><q-icon name="warning" size="18px" /> {{ t('dir.rcvNeedsPassword') }}</div>
          <div v-for="p in points.filter((x) => x.is_active)" :key="p.id" class="line pinline">
            <div class="col">
              <div class="text-weight-medium">{{ p.name }} · {{ p.receiver_name }}</div>
              <div class="mg-sub" :class="{ ok: p.has_pin }">
                <q-icon :name="p.has_pin ? 'check_circle' : 'radio_button_unchecked'" size="14px" />
                {{ p.has_pin ? t('dir.pinSet') : t('dir.pinNone') }}
              </div>
            </div>
            <q-input v-model="pins[p.id]" dense outlined type="password" inputmode="numeric" maxlength="8"
              :placeholder="t('dir.pin')" class="pin" @keyup.enter="savePin(p)" />
            <q-btn unelevated dense no-caps color="primary" :label="t('dir.pinSave')" @click="savePin(p)" />
            <q-btn v-if="p.has_pin" flat round dense icon="key_off" @click="savePin(p, true)">
              <q-tooltip>{{ t('dir.pinRemove') }}</q-tooltip>
            </q-btn>
          </div>
        </template>
      </div>

      <div class="mg-card">
        <div class="card-h">
          <div class="text-weight-medium">{{ t('dir.quotes') }}</div>
          <div class="mg-sub">{{ t('dir.quotesSub') }}</div>
        </div>
        <div class="q-pa-md">
          <q-input v-model="quotes" type="textarea" outlined dense autogrow input-style="min-height: 120px"
            :placeholder="t('dir.quotesPh')" />
          <q-btn unelevated no-caps color="primary" :label="t('common.save')" class="q-mt-sm" @click="saveQuotes" />
        </div>
      </div>
      </div>

      <div class="mg-card mats">
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
.page { max-width: 1080px; margin: 0 auto; padding: 24px 16px 32px; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
.left { display: flex; flex-direction: column; gap: 12px; }
.pinline { padding: 8px 16px; flex-wrap: wrap; }
.pin { width: 150px; }
.ok { color: var(--mg-positive); }
.warn { display: flex; gap: 8px; align-items: center; padding: 10px 16px; color: var(--mg-warning); background: var(--mg-warning-soft); }
.card-h { padding: 14px 16px 10px; border-bottom: 1px solid var(--mg-border); }
.line { display: flex; align-items: center; gap: 8px; padding: 2px 16px; border-bottom: 1px solid var(--mg-border); }
.line.add { padding: 10px 16px; border-bottom: 0; }
.price { width: 110px; }
.alias { margin-top: -10px; }
.noprice :deep(.q-field__control) { box-shadow: inset 0 0 0 1px var(--mg-warning); }
.alias :deep(input) { font-size: 12px; color: var(--mg-fg-3); }
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }
</style>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type Material, type Point, type Shipment } from '@/api'
import { todayIso } from '@/format'
import { t } from '@/i18n'
import LinesEditor from './LinesEditor.vue'
import { linesPayload, type Row } from '@/lines'

const props = defineProps<{ shipmentId: number | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: []; deleted: [] }>()
const $q = useQuasar()

const points = ref<Point[]>([])
const materials = ref<Material[]>([])
const form = ref({ ship_date: todayIso(), point_id: null as number | null, receiver_name: '', destination: 'ДМС', note: '' })
const rows = ref<Row[]>([])
const saving = ref(false)
const loading = ref(false)

const pointOptions = computed(() => points.value.filter((p) => p.is_active || p.id === form.value.point_id)
  .map((p) => ({ label: p.name, value: p.id })))

function onPoint(id: number) {
  form.value.point_id = id
  form.value.receiver_name = points.value.find((p) => p.id === id)?.receiver_name ?? ''
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
      rows.value = materials.value.filter((x) => x.is_active)
        .map((x) => ({ material_id: x.id, point_kg: '', warehouse_kg: '', price_per_kg: null }))
    }
  } finally {
    loading.value = false
  }
}
watch(open, (v) => v && load())

async function save() {
  const res = linesPayload(rows.value)
  if (!form.value.point_id) return $q.notify({ type: 'warning', message: t('lines.errPoint') })
  if (res.error) return $q.notify({ type: 'warning', message: res.error })
  saving.value = true
  try {
    const body = { ...form.value, note: form.value.note || null, lines: res.lines }
    if (props.shipmentId) await http.put(`/shipments/${props.shipmentId}`, body)
    else await http.post('/shipments', body)
    $q.notify({ type: 'positive', message: t('sh.saved') })
    open.value = false
    emit('saved')
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    saving.value = false
  }
}

function remove() {
  $q.dialog({ title: t('sh.deleteQ'), message: t('sh.deleteMsg'), cancel: { label: t('common.cancel'), flat: true }, ok: { label: t('common.delete'), color: 'negative' } })
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
        <div class="mg-h">{{ shipmentId ? t('sh.title') : t('sh.newTitle') }}</div>
        <q-space />
        <q-btn flat round dense icon="close" @click="open = false" />
      </q-card-section>

      <q-inner-loading :showing="loading" />

      <q-card-section class="q-pt-none">
        <div class="head">
          <q-input v-model="form.ship_date" type="date" dense outlined :label="t('common.date')" />
          <q-select :model-value="form.point_id" :options="pointOptions" emit-value map-options dense outlined :label="t('common.point')"
            @update:model-value="onPoint" />
          <q-input v-model="form.receiver_name" dense outlined :label="t('common.receiver')" />
          <q-input v-model="form.destination" dense outlined :label="t('sh.dest')" />
        </div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <LinesEditor v-model="rows" :materials="materials" />
      </q-card-section>

      <q-card-section class="q-pt-none">
        <q-input v-model="form.note" dense outlined autogrow :label="t('common.note')" />
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md">
        <q-btn v-if="shipmentId" flat no-caps color="negative" icon="delete" :label="t('common.delete')" @click="remove" />
        <q-space />
        <q-btn flat no-caps :label="t('common.cancel')" @click="open = false" />
        <q-btn unelevated no-caps color="primary" :label="t('common.save')" :loading="saving" @click="save" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped>
.dlg { width: 880px; max-width: 96vw; border-radius: var(--mg-radius-lg); }
.head { display: grid; grid-template-columns: 150px 1fr 1fr 140px; gap: 8px; }
@media (max-width: 600px) {
  .dlg { border-radius: 0; }
  .head { grid-template-columns: 1fr 1fr; }
}
</style>

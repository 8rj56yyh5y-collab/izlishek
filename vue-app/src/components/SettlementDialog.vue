<script setup lang="ts">
import { ref, watch } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type Material } from '@/api'
import { todayIso } from '@/format'
import { t } from '@/i18n'
import { seg } from '@/theme'

const props = defineProps<{ receiver: string; materialId?: number | null; suggestKg?: number | null }>()
const open = defineModel<boolean>({ required: true })
const emit = defineEmits<{ saved: [] }>()
const $q = useQuasar()

const materials = ref<Material[]>([])
const kind = ref<'cover' | 'writeoff'>('cover')
const form = ref({ settle_date: todayIso(), material_id: null as number | null, kg: '', note: '' })
const saving = ref(false)

watch(open, async (v) => {
  if (!v) return
  materials.value = (await http.get<Material[]>('/materials')).data
  const s = props.suggestKg ?? 0
  kind.value = s < 0 ? 'writeoff' : 'cover'
  form.value = { settle_date: todayIso(), material_id: props.materialId ?? null, kg: s ? String(Math.abs(s)) : '', note: '' }
})

async function save() {
  const v = parseFloat(form.value.kg.replace(',', '.'))
  if (!form.value.material_id || !Number.isFinite(v) || v <= 0) {
    return $q.notify({ type: 'warning', message: t('st.need') })
  }
  saving.value = true
  try {
    await http.post('/settlements', {
      settle_date: form.value.settle_date,
      receiver_name: props.receiver,
      material_id: form.value.material_id,
      kg: kind.value === 'cover' ? v : -v,
      note: form.value.note || null,
    })
    $q.notify({ type: 'positive', message: t('st.saved') })
    open.value = false
    emit('saved')
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <q-dialog v-model="open">
    <q-card style="width: 440px; max-width: 96vw; border-radius: 12px">
      <q-card-section>
        <div class="mg-h">{{ t('st.title') }}</div>
        <div class="mg-sub">{{ receiver }}</div>
      </q-card-section>
      <q-card-section class="q-pt-none q-gutter-sm">
        <q-btn-toggle
          v-model="kind" spread no-caps unelevated toggle-color="primary" :color="seg.color" :text-color="seg.text"
          :options="[{ label: t('st.cover'), value: 'cover' }, { label: t('st.writeoff'), value: 'writeoff' }]"
        />
        <q-select v-model="form.material_id" :options="materials.map((m) => ({ label: m.name, value: m.id }))"
          emit-value map-options dense outlined :label="t('common.material')" />
        <div class="row q-col-gutter-sm">
          <div class="col-6"><q-input v-model="form.kg" dense outlined inputmode="decimal" :label="t('st.kg')" input-class="num" /></div>
          <div class="col-6"><q-input v-model="form.settle_date" type="date" dense outlined :label="t('common.date')" /></div>
        </div>
        <q-input v-model="form.note" dense outlined :label="t('common.note')" />
        <div class="mg-sub">
          {{ kind === 'cover' ? t('st.coverHint') : t('st.writeoffHint') }}
        </div>
      </q-card-section>
      <q-card-actions align="right" class="q-pa-md">
        <q-btn flat no-caps :label="t('common.cancel')" v-close-popup />
        <q-btn unelevated no-caps color="primary" :label="t('st.record')" :loading="saving" @click="save" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

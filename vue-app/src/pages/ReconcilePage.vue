<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useQuasar } from 'quasar'
import { useRouter } from 'vue-router'
import { apiError, http, type Material, type Point, type RecognizeOut } from '@/api'
import { todayIso } from '@/format'
import { shrinkImage } from '@/image'
import { linesPayload, mergeRecognized, type Column, type Row } from '@/lines'
import LinesEditor from '@/components/LinesEditor.vue'

const $q = useQuasar()
const router = useRouter()

const points = ref<Point[]>([])
const materials = ref<Material[]>([])
const form = ref({ ship_date: todayIso(), point_id: null as number | null, receiver_name: '', destination: 'ДМС' })
const dateTouched = ref(false)
const rows = ref<Row[]>([])
const saving = ref(false)

interface Slot {
  column: Column
  mode: 'photo' | 'text'
  text: string
  previews: string[]
  busy: boolean
  result: string
}
const slots = reactive<Slot[]>([
  { column: 'point', mode: 'photo', text: '', previews: [], busy: false, result: '' },
  { column: 'warehouse', mode: 'photo', text: '', previews: [], busy: false, result: '' },
])
const active = ref(0)
const fileInputs = ref<HTMLInputElement[]>([])

const colLabel = (c: Column) => (c === 'point' ? 'Приймальник («Я»)' : 'Склад (що прийняв)')
function setColumn(i: number, c: Column) {
  slots[i].column = c
  slots[1 - i].column = c === 'point' ? 'warehouse' : 'point'
}

onMounted(async () => {
  const [p, m] = await Promise.all([http.get<Point[]>('/points'), http.get<Material[]>('/materials')])
  points.value = p.data
  materials.value = m.data
  const first = points.value.find((x) => x.is_active)
  if (first) onPoint(first.id)
  window.addEventListener('paste', onPaste)
})
onBeforeUnmount(() => window.removeEventListener('paste', onPaste))

const pointOptions = computed(() => points.value.filter((p) => p.is_active).map((p) => ({ label: p.name, value: p.id })))
function onPoint(id: number) {
  form.value.point_id = id
  form.value.receiver_name = points.value.find((p) => p.id === id)?.receiver_name ?? ''
}

function applyResult(i: number, out: RecognizeOut) {
  const s = slots[i]
  const { filled, unknown } = mergeRecognized(rows.value, out.items, s.column)
  if (out.date && !dateTouched.value) form.value.ship_date = out.date
  const two = out.items.some((it) => it.kg2 !== null)
  s.result = filled
    ? `Розпізнано ${filled} ${filled === 1 ? 'рядок' : filled < 5 ? 'рядки' : 'рядків'}` +
      (two ? ' · знайдено дві колонки — заповнено обидві' : '') +
      (unknown ? ` · ${unknown} без матеріалу (жовті)` : '')
    : 'Нічого не знайдено — спробуйте інше фото або текст'
  if (filled && i === 0) active.value = 1
}

async function sendPhotos(i: number, files: File[]) {
  const s = slots[i]
  if (!files.length) return
  s.busy = true
  s.result = ''
  s.previews.forEach((u) => URL.revokeObjectURL(u))
  s.previews = files.map((f) => URL.createObjectURL(f))
  try {
    const fd = new FormData()
    for (const f of files.slice(0, 5)) fd.append('files', await shrinkImage(f), f.name || 'photo.jpg')
    const out = (await http.post<RecognizeOut>('/recognize', fd)).data
    applyResult(i, out)
  } catch (e) {
    s.result = ''
    $q.notify({ type: 'negative', message: apiError(e), timeout: 6000 })
  } finally {
    s.busy = false
  }
}

async function sendText(i: number) {
  const s = slots[i]
  if (!s.text.trim()) return
  s.busy = true
  try {
    const fd = new FormData()
    fd.append('text', s.text)
    applyResult(i, (await http.post<RecognizeOut>('/recognize', fd)).data)
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    s.busy = false
  }
}

function onFiles(i: number, ev: Event) {
  const input = ev.target as HTMLInputElement
  sendPhotos(i, Array.from(input.files ?? []))
  input.value = ''
}

function onDrop(i: number, ev: DragEvent) {
  active.value = i
  sendPhotos(i, Array.from(ev.dataTransfer?.files ?? []).filter((f) => f.type.startsWith('image/')))
}

// Скрін із буфера (Ctrl+V) — в активний слот. Текст у полі вставляється як звичайно.
function onPaste(ev: ClipboardEvent) {
  const imgs = Array.from(ev.clipboardData?.files ?? []).filter((f) => f.type.startsWith('image/'))
  if (!imgs.length) return
  ev.preventDefault()
  slots[active.value].mode = 'photo'
  sendPhotos(active.value, imgs)
}

function reset() {
  rows.value = []
  dateTouched.value = false
  form.value.ship_date = todayIso()
  for (const s of slots) {
    s.text = ''
    s.result = ''
    s.previews.forEach((u) => URL.revokeObjectURL(u))
    s.previews = []
  }
  active.value = 0
}

async function save() {
  const res = linesPayload(rows.value)
  if (!form.value.point_id) return $q.notify({ type: 'warning', message: 'Оберіть пункт' })
  if (res.error) return $q.notify({ type: 'warning', message: res.error })
  saving.value = true
  try {
    await http.post('/shipments', { ...form.value, lines: res.lines })
    $q.notify({
      type: 'positive', message: 'Звірку збережено',
      actions: [{ label: 'До огляду', color: 'white', handler: () => router.push('/') }],
    })
    reset()
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <q-page class="page">
    <div class="q-mb-md">
      <h1 class="mg-h">Звірка відвантаження</h1>
      <div class="mg-sub">Додайте два фото або тексти — що здав приймальник і що прийняв склад. Відхилення порахуються самі.</div>
    </div>

    <div class="mg-card q-pa-md q-mb-md head">
      <q-input v-model="form.ship_date" type="date" dense outlined label="Дата" @update:model-value="dateTouched = true" />
      <q-select :model-value="form.point_id" :options="pointOptions" emit-value map-options dense outlined label="Пункт"
        @update:model-value="onPoint" />
      <q-input v-model="form.receiver_name" dense outlined label="Приймальник" />
      <q-input v-model="form.destination" dense outlined label="Склад" />
    </div>

    <div class="slots q-mb-md">
      <div v-for="(s, i) in slots" :key="i" class="mg-card slot" :class="{ active: active === i }"
        @click="active = i" @dragover.prevent @drop.prevent="onDrop(i, $event)">
        <div class="slot-h">
          <span class="step">{{ i + 1 }}</span>
          <span class="text-weight-medium">Куди ставимо?</span>
        </div>
        <q-btn-toggle :model-value="s.column" spread no-caps unelevated toggle-color="primary" color="grey-2" text-color="grey-9"
          class="q-mb-sm" :options="[{ label: 'Приймальник', value: 'point' }, { label: 'Склад', value: 'warehouse' }]"
          @update:model-value="(v: Column) => setColumn(i, v)" />
        <q-tabs v-model="s.mode" dense no-caps align="left" active-color="primary" indicator-color="primary" class="q-mb-sm">
          <q-tab name="photo" icon="photo_camera" label="Фото / скрін" />
          <q-tab name="text" icon="notes" label="Текст" />
        </q-tabs>

        <template v-if="s.mode === 'photo'">
          <label class="drop" :class="{ busy: s.busy }">
            <input :ref="(el) => (fileInputs[i] = el as HTMLInputElement)" type="file" accept="image/*" multiple hidden
              @change="onFiles(i, $event)" />
            <div v-if="s.previews.length" class="thumbs">
              <img v-for="u in s.previews" :key="u" :src="u" alt="" />
            </div>
            <template v-else>
              <q-icon name="add_a_photo" size="32px" color="primary" />
              <div class="text-weight-medium">Сфотографувати або вибрати</div>
              <div class="mg-sub gt-xs">або перетягніть сюди / Ctrl+V скрін</div>
            </template>
            <q-inner-loading :showing="s.busy" label="Розпізнаю…" label-class="text-primary" />
          </label>
        </template>
        <template v-else>
          <q-input v-model="s.text" type="textarea" outlined dense autogrow input-style="min-height: 120px"
            :placeholder="'AL 71,9\nCu 37,85\nЛатунь 34,45\nAL банка 12'" />
          <q-btn unelevated no-caps color="primary" label="Розпізнати" class="q-mt-sm full-width" :loading="s.busy"
            @click.stop="sendText(i)" />
        </template>
        <div v-if="s.result" class="result">
          <q-icon name="check_circle" color="positive" size="18px" /> {{ s.result }}
          <span class="mg-muted"> → {{ colLabel(s.column) }}</span>
        </div>
      </div>
    </div>

    <div class="mg-card q-pa-md">
      <div v-if="!rows.length" class="empty">
        <q-icon name="table_rows" size="28px" color="grey-5" />
        <div>Тут зʼявиться таблиця після розпізнавання.</div>
        <q-btn flat no-caps color="primary" label="Або заповнити вручну"
          @click="rows = materials.filter((m) => m.is_active).map((m) => ({ material_id: m.id, point_kg: '', warehouse_kg: '', price_per_kg: null }))" />
      </div>
      <LinesEditor v-else v-model="rows" :materials="materials" />
    </div>

    <div v-if="rows.length" class="savebar">
      <q-btn flat no-caps label="Очистити" @click="reset" />
      <q-btn unelevated no-caps color="primary" icon="save" label="Зберегти звірку" :loading="saving" @click="save" />
    </div>
  </q-page>
</template>

<style scoped>
.page { max-width: 1080px; margin: 0 auto; padding: 20px 16px 96px; }
.head { display: grid; grid-template-columns: 150px 1fr 1fr 140px; gap: 8px; }
.slots { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.slot { padding: 14px 16px; transition: border-color 0.15s; }
.slot.active { border-color: var(--mg-primary); box-shadow: 0 0 0 1px var(--mg-primary); }
.slot-h { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.step { width: 22px; height: 22px; border-radius: 50%; background: var(--mg-primary); color: #fff; font-size: 12px; font-weight: 700; display: grid; place-items: center; }
.drop { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; min-height: 150px; border: 2px dashed var(--mg-border-strong); border-radius: var(--mg-radius-md); cursor: pointer; text-align: center; padding: 12px; background: var(--mg-bg-2); }
.drop:hover { border-color: var(--mg-primary); }
.thumbs { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
.thumbs img { height: 120px; max-width: 100%; object-fit: cover; border-radius: 6px; }
.result { margin-top: 8px; font-size: 13px; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 20px; color: var(--mg-fg-3); text-align: center; }
.savebar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 10; display: flex; justify-content: flex-end; gap: 8px; padding: 10px 16px; background: var(--mg-bg); border-top: 1px solid var(--mg-border); }
@media (max-width: 700px) {
  .head { grid-template-columns: 1fr 1fr; }
  .slots { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .savebar { bottom: calc(58px + env(safe-area-inset-bottom)); }
  .savebar .q-btn:last-child { flex: 1; }
}
</style>

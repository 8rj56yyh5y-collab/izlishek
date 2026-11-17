<script setup lang="ts">
// Один вхід для колонки: Фото / Файл / Текст / Список → рядки «матеріал–вага».
// Спільний для «Звірки» (по одному на колонку) і версії приймальника.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type Material, type RecognizeOut } from '@/api'
import { t } from '@/i18n'
import { shrinkImage } from '@/image'

const props = defineProps<{ materials: Material[]; active?: boolean }>()
const emit = defineEmits<{ result: [out: RecognizeOut] }>()
const $q = useQuasar()

type Mode = 'photo' | 'file' | 'text' | 'list'
const mode = ref<Mode>('photo')
const text = ref('')
const busy = ref(false)
const previews = ref<string[]>([])
const fileNames = ref<string[]>([])
const search = ref('')
const listKg = ref<Record<number, string>>({})

const modes = computed(() => [
  { v: 'photo' as Mode, icon: 'photo_camera', label: t('rec.photo') },
  { v: 'file' as Mode, icon: 'upload_file', label: t('rec.file') },
  { v: 'text' as Mode, icon: 'notes', label: t('rec.text') },
  { v: 'list' as Mode, icon: 'format_list_numbered', label: t('rec.list') },
])

async function send(fd: FormData) {
  busy.value = true
  try {
    emit('result', (await http.post<RecognizeOut>('/recognize', fd)).data)
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e), timeout: 6000 })
  } finally {
    busy.value = false
  }
}

async function sendFiles(files: File[]) {
  if (!files.length) return
  previews.value.forEach((u) => URL.revokeObjectURL(u))
  previews.value = files.filter((f) => f.type.startsWith('image/')).map((f) => URL.createObjectURL(f))
  fileNames.value = files.filter((f) => !f.type.startsWith('image/')).map((f) => f.name)
  const fd = new FormData()
  for (const f of files.slice(0, 5)) fd.append('files', f.type.startsWith('image/') ? await shrinkImage(f) : f, f.name || 'photo.jpg')
  await send(fd)
}

function onFiles(ev: Event) {
  const input = ev.target as HTMLInputElement
  sendFiles(Array.from(input.files ?? []))
  input.value = ''
}

function onDrop(ev: DragEvent) {
  const files = Array.from(ev.dataTransfer?.files ?? [])
  if (files.length) {
    mode.value = files.every((f) => f.type.startsWith('image/')) ? 'photo' : 'file'
    sendFiles(files)
  }
}

function sendText() {
  if (!text.value.trim()) return
  const fd = new FormData()
  fd.append('text', text.value)
  send(fd)
}

// «Список»: усі позиції, біля кожної — поле ваги. Без сервера: одразу віддаємо результат.
const shown = computed(() => {
  const q = search.value.trim().toLowerCase()
  return props.materials.filter((m) => m.is_active && (!q || m.name.toLowerCase().includes(q) || (m.aliases ?? '').toLowerCase().includes(q)))
})
const listFilled = computed(() => Object.values(listKg.value).filter((v) => v && v.trim()).length)
function addList() {
  const items = Object.entries(listKg.value)
    .map(([id, v]) => ({ id: Number(id), kg: parseFloat(String(v).replace(',', '.')) }))
    .filter((x) => Number.isFinite(x.kg))
    .map((x) => ({ raw: props.materials.find((m) => m.id === x.id)?.name ?? '', material_id: x.id,
      material_name: props.materials.find((m) => m.id === x.id)?.name ?? null, kg: x.kg, kg2: null }))
  if (!items.length) return
  emit('result', { source: 'text', date: null, items })
  listKg.value = {}
  search.value = ''
}

// Скрін із буфера (Ctrl+V) — лише в активний блок, щоб два блоки не ловили одне й те саме.
function onPaste(ev: ClipboardEvent) {
  if (props.active === false) return
  const files = Array.from(ev.clipboardData?.files ?? [])
  if (!files.length) return
  ev.preventDefault()
  mode.value = files.every((f) => f.type.startsWith('image/')) ? 'photo' : 'file'
  sendFiles(files)
}
onMounted(() => window.addEventListener('paste', onPaste))
onBeforeUnmount(() => window.removeEventListener('paste', onPaste))

function reset() {
  previews.value.forEach((u) => URL.revokeObjectURL(u))
  previews.value = []
  fileNames.value = []
  text.value = ''
  listKg.value = {}
}
defineExpose({ reset })
</script>

<template>
  <div @dragover.prevent @drop.prevent="onDrop">
    <div class="modes">
      <button v-for="m in modes" :key="m.v" type="button" :class="{ on: mode === m.v }" @click.stop="mode = m.v">
        <q-icon :name="m.icon" size="18px" /><span>{{ m.label }}</span>
      </button>
    </div>

    <label v-if="mode === 'photo' || mode === 'file'" class="drop">
      <input v-if="mode === 'photo'" type="file" accept="image/*" multiple hidden @change="onFiles" />
      <input v-else type="file" multiple hidden
        accept=".xlsx,.xlsm,.csv,.txt,.pdf,image/*,application/pdf,text/csv,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        @change="onFiles" />
      <div v-if="previews.length && mode === 'photo'" class="thumbs"><img v-for="u in previews" :key="u" :src="u" alt="" /></div>
      <div v-else-if="fileNames.length && mode === 'file'" class="files">
        <span v-for="n in fileNames" :key="n" class="fname"><q-icon name="description" size="16px" /> {{ n }}</span>
      </div>
      <template v-else>
        <span class="ico"><q-icon :name="mode === 'photo' ? 'add_a_photo' : 'upload_file'" size="26px" /></span>
        <div class="text-weight-medium">{{ mode === 'photo' ? t('rec.shoot') : t('rec.pickFile') }}</div>
        <div class="mg-sub">{{ mode === 'photo' ? t('rec.dropHint') : t('rec.fileHint') }}</div>
      </template>
      <q-inner-loading :showing="busy" :label="t('rec.busy')" label-class="text-primary" />
    </label>

    <template v-else-if="mode === 'text'">
      <q-input v-model="text" type="textarea" outlined dense autogrow input-style="min-height: 110px"
        :placeholder="t('rec.textPh')" @keydown.ctrl.enter="sendText" @keydown.meta.enter="sendText" />
      <div class="mg-sub q-mt-xs">{{ t('rec.textHint') }}</div>
      <q-btn unelevated no-caps color="primary" :label="t('rec.recognize')" class="q-mt-sm full-width" :loading="busy" @click.stop="sendText" />
    </template>

    <template v-else>
      <q-input v-model="search" dense outlined clearable :placeholder="t('rec.search')" class="q-mb-sm">
        <template #prepend><q-icon name="search" size="18px" /></template>
      </q-input>
      <div class="plist">
        <div v-for="m in shown" :key="m.id" class="prow" :class="{ filled: (listKg[m.id] ?? '').trim() }">
          <span class="pname">{{ m.name }}</span>
          <input v-model="listKg[m.id]" class="pkg num" inputmode="decimal" placeholder="0" :aria-label="m.name"
            @keydown.enter="addList" />
          <span class="mg-sub">{{ t('common.kg') }}</span>
        </div>
      </div>
      <q-btn unelevated no-caps color="primary" icon="add" :disable="!listFilled"
        :label="listFilled ? t('rec.addN', { n: listFilled }) : t('rec.add')" class="q-mt-sm full-width" @click.stop="addList" />
    </template>
  </div>
</template>

<style scoped>
.modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; padding: 4px; margin-bottom: 10px;
  border-radius: 12px; background: var(--mg-bg-2); border: 1px solid var(--mg-border); }
.modes button { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 6px 2px; border: 0; border-radius: 9px;
  background: transparent; color: var(--mg-fg-2); font: 600 12px 'Inter', sans-serif; cursor: pointer; transition: background 0.2s, color 0.2s; }
.modes button:hover { color: var(--mg-fg); }
.modes button.on { background: var(--mg-bg); color: var(--mg-fg); box-shadow: var(--mg-shadow); }
.modes button.on .q-icon { color: var(--mg-primary); }

.drop { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; min-height: 150px;
  border: 1.5px dashed var(--mg-border-strong); border-radius: var(--mg-radius-lg); cursor: pointer; text-align: center; padding: 14px;
  background: var(--mg-bg-2); transition: border-color 0.2s, background 0.2s; }
.drop:hover { border-color: var(--mg-primary); background: var(--mg-primary-soft); }
.ico { width: 52px; height: 52px; border-radius: 16px; display: grid; place-items: center; background: var(--mg-primary); color: var(--mg-on-primary); }
.thumbs { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
.thumbs img { height: 110px; max-width: 100%; object-fit: cover; border-radius: 10px; }
.files { display: flex; flex-direction: column; gap: 6px; }
.fname { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }

.plist { max-height: 300px; overflow-y: auto; border: 1px solid var(--mg-border); border-radius: var(--mg-radius-md); }
.prow { display: flex; align-items: center; gap: 8px; padding: 4px 10px; border-bottom: 1px solid var(--mg-border); }
.prow:last-child { border-bottom: 0; }
.prow.filled { background: var(--mg-primary-soft); }
.pname { flex: 1; min-width: 0; font-size: 14px; }
.pkg { width: 84px; height: 32px; padding: 0 8px; text-align: right; font: 600 14px 'Inter', sans-serif; color: var(--mg-fg);
  background: var(--mg-bg); border: 1px solid var(--mg-border-strong); border-radius: 8px; outline: 0; }
.pkg:focus { border-color: var(--mg-primary); box-shadow: 0 0 0 3px var(--mg-primary-soft); }
</style>

<script setup lang="ts">
// Один вхід «фото / скрін / текст» → рядки «матеріал–вага». Використовує версія приймальника.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type RecognizeOut } from '@/api'
import { t } from '@/i18n'
import { shrinkImage } from '@/image'

const emit = defineEmits<{ result: [out: RecognizeOut] }>()
const $q = useQuasar()
const mode = ref<'photo' | 'text'>('photo')
const text = ref('')
const busy = ref(false)
const previews = ref<string[]>([])

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

async function photos(files: File[]) {
  if (!files.length) return
  previews.value.forEach((u) => URL.revokeObjectURL(u))
  previews.value = files.map((f) => URL.createObjectURL(f))
  const fd = new FormData()
  for (const f of files.slice(0, 5)) fd.append('files', await shrinkImage(f), f.name || 'photo.jpg')
  await send(fd)
}

function onFiles(ev: Event) {
  const input = ev.target as HTMLInputElement
  photos(Array.from(input.files ?? []))
  input.value = ''
}

function sendText() {
  if (!text.value.trim()) return
  const fd = new FormData()
  fd.append('text', text.value)
  send(fd)
}

function onPaste(ev: ClipboardEvent) {
  const imgs = Array.from(ev.clipboardData?.files ?? []).filter((f) => f.type.startsWith('image/'))
  if (!imgs.length) return
  ev.preventDefault()
  mode.value = 'photo'
  photos(imgs)
}
onMounted(() => window.addEventListener('paste', onPaste))
onBeforeUnmount(() => window.removeEventListener('paste', onPaste))
</script>

<template>
  <div>
    <q-tabs v-model="mode" dense no-caps align="left" active-color="primary" indicator-color="primary" class="q-mb-sm">
      <q-tab name="photo" icon="photo_camera" :label="t('rec.photo')" />
      <q-tab name="text" icon="notes" :label="t('rec.text')" />
    </q-tabs>
    <label v-if="mode === 'photo'" class="drop">
      <input type="file" accept="image/*" multiple hidden @change="onFiles" />
      <div v-if="previews.length" class="thumbs"><img v-for="u in previews" :key="u" :src="u" alt="" /></div>
      <template v-else>
        <span class="ico"><q-icon name="add_a_photo" size="26px" /></span>
        <div class="text-weight-medium">{{ t('rec.shoot') }}</div>
        <div class="mg-sub gt-xs">{{ t('rec.dropHint') }}</div>
      </template>
      <q-inner-loading :showing="busy" :label="t('rec.busy')" label-class="text-primary" />
    </label>
    <template v-else>
      <q-input v-model="text" type="textarea" outlined dense autogrow input-style="min-height: 110px"
        :placeholder="'АЛ электротех 71,9\nМедь микс 37,85\nБанка 12'" />
      <q-btn unelevated no-caps color="primary" :label="t('rec.recognize')" class="q-mt-sm full-width" :loading="busy" @click="sendText" />
    </template>
  </div>
</template>

<style scoped>
.drop { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; min-height: 150px;
  border: 1.5px dashed var(--mg-border-strong); border-radius: var(--mg-radius-lg); cursor: pointer; text-align: center; padding: 14px;
  background: var(--mg-bg-2); transition: border-color 0.2s, background 0.2s; }
.drop:hover { border-color: var(--mg-primary); background: var(--mg-primary-soft); }
.ico { width: 52px; height: 52px; border-radius: 16px; display: grid; place-items: center; background: var(--mg-primary); color: var(--mg-on-primary); }
.thumbs { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
.thumbs img { height: 110px; max-width: 100%; object-fit: cover; border-radius: 10px; }
</style>

<script setup lang="ts">
// Звірка: на телефоні — три кроки (За обліком → Склад → Результат), на компʼютері — усе на одному екрані.
import { computed, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, type Material, type Point, type RecognizeOut, type Submission } from '@/api'
import { dateUa, todayIso } from '@/format'
import { t } from '@/i18n'
import { linesPayload, mergeRecognized, num, type Column, type Row } from '@/lines'
import { summaryText, useShare } from '@/share'
import RecognizeInput from '@/components/RecognizeInput.vue'
import ResultCards from '@/components/ResultCards.vue'
import Sheet from '@/components/Sheet.vue'

const $q = useQuasar()
const share = useShare()

const points = ref<Point[]>([])
const materials = ref<Material[]>([])
const form = ref({ ship_date: todayIso(), point_id: null as number | null, receiver_name: '', destination: 'ДМС' })
const dateTouched = ref(false)
const rows = ref<Row[]>([])
const saving = ref(false)

const desk = computed(() => $q.screen.gt.sm)
const step = ref(0) // 0 — облік, 1 — склад, 2 — результат (лише на телефоні)
const cols: Column[] = ['point', 'warehouse']
const res = ref<({ filled: number; two: boolean; unknown: number } | null)[]>([null, null])
const inputs = ref<(InstanceType<typeof RecognizeInput> | null)[]>([])

const hasBook = computed(() => rows.value.some((r) => num(r.point_kg) !== null))
const hasWh = computed(() => rows.value.some((r) => num(r.warehouse_kg) !== null))
const steps = computed(() => [
  { label: t('step.book'), done: hasBook.value },
  { label: t('step.wh'), done: hasWh.value },
  { label: t('step.result'), done: false },
])

// ── контекст: пункт, приймальник, дата ──
const ctxOpen = ref(false)
const pointOptions = computed(() => points.value.filter((p) => p.is_active).map((p) => ({ label: p.name, value: p.id })))
const pointName = computed(() => points.value.find((p) => p.id === form.value.point_id)?.name ?? '—')
function onPoint(id: number) {
  form.value.point_id = id
  form.value.receiver_name = points.value.find((p) => p.id === id)?.receiver_name ?? ''
  try { localStorage.setItem('bt_point', String(id)) } catch { /* ignore */ }
}

// ── здачі приймальників, що чекають ваги складу ──
const pending = ref<Submission[]>([])
const pendingId = ref<number | null>(null)
const pendingSub = computed(() => pending.value.find((x) => x.id === pendingId.value) ?? null)
async function loadPending() {
  pending.value = (await http.get<Submission[]>('/pending')).data
}
function openPending(s: Submission) {
  reset()
  pendingId.value = s.id
  form.value = { ...form.value, point_id: s.point_id, receiver_name: s.receiver_name, ship_date: s.ship_date }
  dateTouched.value = true
  rows.value = s.lines.map((l) => ({ material_id: l.material_id, point_kg: String(l.point_kg), warehouse_kg: '', price_per_kg: null }))
  step.value = 1
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(async () => {
  const [p, m] = await Promise.all([http.get<Point[]>('/points'), http.get<Material[]>('/materials')])
  points.value = p.data
  materials.value = m.data
  loadPending()
  let last: number | null = null
  try { last = Number(localStorage.getItem('bt_point')) || null } catch { /* ignore */ }
  const first = points.value.find((x) => x.is_active && x.id === last) ?? points.value.find((x) => x.is_active)
  if (first) onPoint(first.id)
})

function resultText(r: { filled: number; two: boolean; unknown: number }) {
  if (!r.filled) return t('rec.nothing')
  return t('rec.found', { n: r.filled }) + (r.two ? ' · ' + t('rec.twoCols') : '') +
    (r.unknown ? ' · ' + t('rec.unknown', { n: r.unknown }) : '')
}

function applyResult(i: number, out: RecognizeOut) {
  const { filled, unknown } = mergeRecognized(rows.value, out.items, cols[i])
  if (out.date && !dateTouched.value) form.value.ship_date = out.date
  const two = out.items.some((it) => it.kg2 !== null)
  res.value[i] = { filled, two, unknown }
  // на телефоні — сам переходимо далі: дві колонки одразу → до результату
  if (!desk.value && filled) window.setTimeout(() => { step.value = two ? 2 : Math.min(i + 1, 2) }, 650)
}

function reset() {
  pendingId.value = null
  rows.value = []
  dateTouched.value = false
  form.value.ship_date = todayIso()
  res.value = [null, null]
  inputs.value.forEach((x) => x?.reset())
  step.value = 0
}

async function learnAliases(rs: Row[]) {
  const items = rs.filter((r) => r.raw && r.material_id).map((r) => ({ material_id: r.material_id, alias: r.raw }))
  if (!items.length) return 0
  try { await http.post('/materials/learn', items) } catch { /* не критично */ }
  return items.length
}

const currentText = () => summaryText(rows.value, materials.value,
  { date: form.value.ship_date, point: pointName.value, who: form.value.receiver_name })

// ── після збереження: шторка «готово» з «Поділитися» ──
const doneOpen = ref(false)
const doneText = ref('')
const learnedN = ref(0)

async function save() {
  const out = linesPayload(rows.value)
  if (!form.value.point_id) return $q.notify({ type: 'warning', message: t('lines.errPoint') })
  if (rows.value.some((r) => !r.material_id && (r.point_kg || r.warehouse_kg))) {
    // невпізнані рядки: або вибрати матеріал, або одним дотиком не враховувати
    return $q.notify({ type: 'warning', message: t('lines.errUnknown'), timeout: 7000,
      actions: [{ label: t('res.skipUnknown'), color: 'dark', handler: () => { rows.value = rows.value.filter((r) => r.material_id); save() } }] })
  }
  if (out.error) return $q.notify({ type: 'warning', message: out.error })
  saving.value = true
  try {
    learnedN.value = await learnAliases(rows.value)
    if (pendingId.value) await http.put(`/shipments/${pendingId.value}`, { ...form.value, lines: out.lines })
    else await http.post('/shipments', { ...form.value, lines: out.lines })
    doneText.value = currentText()
    loadPending()
    reset()
    doneOpen.value = true
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <q-page class="page">
    <header class="top">
      <h1 class="mg-h">{{ t('nav.new') }}</h1>
      <button type="button" class="ctx" @click="ctxOpen = true">
        <q-icon name="storefront" size="18px" />
        <span class="ctx-t">{{ pointName }} · {{ form.receiver_name || '—' }} · {{ dateUa(form.ship_date).slice(0, 5) }}</span>
        <q-icon name="expand_more" size="18px" />
      </button>
    </header>

    <div v-if="pendingSub" class="banner">
      <q-icon name="assignment_ind" size="20px" />
      <span>{{ t('pend.banner', { who: pendingSub.receiver_name, date: dateUa(pendingSub.ship_date) }) }}</span>
      <q-space />
      <q-btn flat dense no-caps :label="t('pend.cancel')" @click="reset" />
    </div>
    <div v-else-if="pending.length" class="pend">
      <div class="pend-h"><span class="dot" />{{ t('pend.title') }} · {{ pending.length }}</div>
      <div class="pend-list">
        <button v-for="s in pending" :key="s.id" type="button" class="pend-item" @click="openPending(s)">
          <div class="text-weight-bold">{{ s.receiver_name }}</div>
          <div class="mg-sub">{{ dateUa(s.ship_date) }} · {{ s.lines.length }} {{ t('sh.items') }}</div>
          <span class="go">{{ t('pend.open') }} <q-icon name="arrow_forward" size="15px" /></span>
        </button>
      </div>
    </div>

    <nav v-if="!desk" class="steps">
      <button v-for="(s, i) in steps" :key="i" type="button" class="st" :class="{ on: step === i, done: s.done }" @click="step = i">
        <span class="st-n"><q-icon v-if="s.done && step !== i" name="check" size="14px" /><template v-else>{{ i + 1 }}</template></span>
        <span class="st-l">{{ s.label }}</span>
      </button>
    </nav>

    <div class="inputs" :class="{ desk }">
      <section v-for="i in [0, 1]" v-show="desk || step === i" :key="i" class="mg-card in-card">
        <div class="in-h">
          <span class="in-n" :class="{ done: i === 0 ? hasBook : hasWh }">
            <q-icon v-if="i === 0 ? hasBook : hasWh" name="check" size="15px" /><template v-else>{{ i + 1 }}</template>
          </span>
          <div>
            <div class="in-t">{{ i === 0 ? t('step.book') : t('rec.colWarehouseLong') }}</div>
            <div class="mg-sub">{{ i === 0 ? t('step.bookHint') : t('step.whHint') }}</div>
          </div>
        </div>
        <RecognizeInput :ref="(el) => (inputs[i] = el as InstanceType<typeof RecognizeInput> | null)" :materials="materials"
          :active="desk ? undefined : step === i" @result="(o) => applyResult(i, o)" />
        <div v-if="res[i]" class="result">
          <q-icon :name="res[i]!.filled ? 'check_circle' : 'error_outline'" :color="res[i]!.filled ? 'positive' : 'warning'" size="18px" />
          {{ resultText(res[i]!) }}
        </div>
      </section>
    </div>

    <section v-show="desk || step === 2" class="results">
      <div v-if="!rows.length" class="empty">
        <q-icon name="fact_check" size="34px" />
        <div>{{ t('res.empty') }}</div>
        <q-btn flat no-caps color="primary" :label="t('rec.manual')"
          @click="rows = materials.filter((m) => m.is_active).map((m) => ({ material_id: m.id, point_kg: '', warehouse_kg: '', price_per_kg: null }))" />
      </div>
      <ResultCards v-else v-model="rows" :materials="materials" />
    </section>

    <Teleport to="body"><div v-if="$route.path === '/reconcile'" class="bt-savebar">
      <template v-if="!desk && step < 2">
        <q-btn v-if="step > 0" flat no-caps icon="arrow_back" :label="t('step.back')" @click="step--" />
        <q-space v-else />
        <q-btn unelevated no-caps no-wrap color="primary" icon-right="arrow_forward" :label="t('step.next')" class="grow" @click="step++" />
      </template>
      <template v-else>
        <q-btn v-if="rows.length" flat no-caps icon="restart_alt" :label="desk ? t('rec.clear') : ''" @click="reset" />
        <q-space />
        <q-btn v-if="rows.length" outline no-caps color="primary" icon="ios_share" :label="desk ? t('share.btn') : ''"
          @click="share(currentText())" />
        <q-btn unelevated no-caps color="primary" icon="check" :label="t('rec.save')" :loading="saving" :disable="!rows.length"
          class="grow-m" no-wrap @click="save" />
      </template>
    </div></Teleport>

    <Sheet v-model="ctxOpen" :title="t('ctx.title')">
      <div class="ctx-form">
        <q-select :model-value="form.point_id" :options="pointOptions" emit-value map-options outlined :label="t('common.point')"
          @update:model-value="onPoint" />
        <q-input v-model="form.receiver_name" outlined :label="t('common.receiver')" />
        <q-input v-model="form.ship_date" type="date" outlined :label="t('common.date')" @update:model-value="dateTouched = true" />
        <q-input v-model="form.destination" outlined :label="t('common.warehouse')" />
      </div>
      <template #actions>
        <q-btn unelevated no-caps color="primary" :label="t('step.done')" @click="ctxOpen = false" />
      </template>
    </Sheet>

    <Sheet v-model="doneOpen">
      <div class="done">
        <div class="done-ico"><q-icon name="check" size="34px" /></div>
        <div class="done-t">{{ t('done.title') }}</div>
        <div class="mg-sub">{{ t('done.sub') }}</div>
        <div v-if="learnedN" class="mg-sub q-mt-xs">{{ t('rec.learned', { n: learnedN }) }}</div>
        <pre class="done-text">{{ doneText }}</pre>
      </div>
      <template #actions>
        <q-btn outline no-caps color="primary" icon="ios_share" :label="t('share.btn')" @click="share(doneText)" />
        <q-btn unelevated no-caps color="primary" :label="t('done.new')" @click="doneOpen = false" />
      </template>
    </Sheet>
  </q-page>
</template>

<style scoped>
.page { max-width: 1100px; margin: 0 auto; padding: 16px 16px 170px; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.ctx { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; padding: 8px 12px; border-radius: 999px; font: 600 14px 'Inter', sans-serif;
  color: var(--mg-fg); background: var(--mg-bg); border: 1px solid var(--mg-border); cursor: pointer; }
.ctx .q-icon:first-child { color: var(--mg-primary); }
.ctx-t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.banner { display: flex; align-items: center; gap: 10px; padding: 10px 14px; margin-bottom: 12px; border-radius: 16px; font-weight: 600;
  background: var(--mg-primary-soft); border: 1px solid color-mix(in srgb, var(--mg-primary) 45%, transparent); }
.pend { margin-bottom: 14px; }
.pend-h { display: flex; align-items: center; gap: 8px; font-weight: 700; margin-bottom: 8px; }
.pend-h .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--mg-primary); box-shadow: 0 0 0 4px var(--mg-primary-soft); }
.pend-list { display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
.pend-item { flex: 0 0 auto; min-width: 180px; text-align: left; padding: 12px 14px; border-radius: 16px; border: 1px solid var(--mg-border);
  background: var(--mg-bg); color: var(--mg-fg); font: inherit; cursor: pointer; }
.pend-item .go { display: inline-flex; align-items: center; gap: 4px; margin-top: 6px; color: var(--mg-primary); font-weight: 700; font-size: 13px; }

.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 12px; }
.st { display: flex; align-items: center; justify-content: center; gap: 6px; height: 42px; border-radius: 14px; border: 1px solid var(--mg-border);
  background: var(--mg-bg); color: var(--mg-fg-2); font: 600 13px 'Inter', sans-serif; cursor: pointer; transition: all 0.2s; }
.st-n { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; background: var(--mg-bg-2); }
.st.done .st-n { background: var(--mg-positive); color: #fff; }
.st.on { background: var(--mg-primary); border-color: var(--mg-primary); color: var(--mg-on-primary); }
.st.on .st-n { background: color-mix(in srgb, var(--mg-on-primary) 18%, transparent); color: var(--mg-on-primary); }

.inputs.desk { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.in-card { padding: 16px; animation: mg-page-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both; }
.in-h { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
.in-n { flex: 0 0 auto; width: 30px; height: 30px; border-radius: 10px; display: grid; place-items: center; font-weight: 800;
  background: var(--mg-primary); color: var(--mg-on-primary); }
.in-n.done { background: var(--mg-positive); color: #fff; }
.in-t { font-family: var(--mg-display); font-weight: 600; font-size: 17px; }
.result { margin-top: 10px; font-size: 13px; display: flex; gap: 6px; align-items: center; }

.results { margin-top: 14px; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 28px 16px; text-align: center; color: var(--mg-fg-3);
  border: 1.5px dashed var(--mg-border-strong); border-radius: 20px; }


.ctx-form { display: flex; flex-direction: column; gap: 10px; padding-top: 4px; }
.done { text-align: center; padding: 8px 0 4px; }
.done-ico { width: 64px; height: 64px; margin: 4px auto 10px; border-radius: 50%; display: grid; place-items: center;
  background: var(--mg-positive); color: #fff; animation: pop 0.45s cubic-bezier(0.2, 1.4, 0.4, 1) both; }
@keyframes pop { from { transform: scale(0.4); opacity: 0; } }
.done-t { font-family: var(--mg-display); font-size: 20px; font-weight: 700; }
.done-text { text-align: left; white-space: pre-wrap; font: 13px/1.5 'Inter', sans-serif; margin: 14px 0 0; padding: 12px 14px;
  border-radius: 14px; background: var(--mg-bg-2); max-height: 220px; overflow: auto; }
</style>

<style>
/* Панель дій звірки — через Teleport у body (поза анімованою сторінкою, щоб fixed рахувався від екрана). */
.bt-savebar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 2001; display: flex; align-items: center; gap: 8px;
  padding: 10px max(16px, calc((100vw - 1100px) / 2 + 16px)); background: color-mix(in srgb, var(--mg-bg) 92%, transparent);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-top: 1px solid var(--mg-border); }
.bt-savebar .q-btn { min-height: 48px; border-radius: 14px; }
.bt-savebar .grow { flex: 1; max-width: 260px; }
@media (max-width: 1023px) {
  .bt-savebar { bottom: calc(68px + env(safe-area-inset-bottom)); padding: 8px 16px; }
  .bt-savebar .grow, .bt-savebar .grow-m { flex: 1; max-width: none; }
}
</style>

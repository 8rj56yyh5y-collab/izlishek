<script setup lang="ts">
// «Версія приймальника»: лише своя здача, свої здачі і свій баланс. Ваги складу до звірки не видно.
import { computed, onMounted, ref } from 'vue'
import { useQuasar } from 'quasar'
import { apiError, http, rhttp, type Material, type ReceiverMe, type RecognizeOut, type Submission } from '@/api'
import { dateUa, devClass, devKg, devMoney, todayIso } from '@/format'
import { t } from '@/i18n'
import BrandLogo from '@/components/BrandLogo.vue'
import AppSettings from '@/components/AppSettings.vue'
import RecognizeInput from '@/components/RecognizeInput.vue'

const emit = defineEmits<{ logout: [] }>()
const $q = useQuasar()

const me = ref<ReceiverMe | null>(null)
const materials = ref<Material[]>([])
const subs = ref<Submission[]>([])
const tab = ref<'submit' | 'history'>('submit')

interface Row { material_id: number | null; kg: string; raw?: string | null }
const rows = ref<Row[]>([])
const shipDate = ref(todayIso())
const editingId = ref<number | null>(null)
const saving = ref(false)

const owed = computed(() => me.value?.balance?.materials.filter((m) => m.balance_kg < -0.0005) ?? [])
const total = computed(() => rows.value.reduce((s, r) => s + (parseFloat(r.kg.replace(',', '.')) || 0), 0))

async function load() {
  const [a, b, c] = await Promise.all([
    rhttp.get<ReceiverMe>('/me'), http.get<Material[]>('/materials'), rhttp.get<Submission[]>('/submissions'),
  ])
  me.value = a.data
  materials.value = b.data
  subs.value = c.data
}
onMounted(load)

const options = (cur: number | null) => {
  const used = new Set(rows.value.map((r) => r.material_id))
  return materials.value.filter((m) => m.is_active && (m.id === cur || !used.has(m.id))).map((m) => ({ label: m.name, value: m.id }))
}

function onResult(out: RecognizeOut) {
  if (out.date) shipDate.value = out.date
  for (const it of out.items) {
    if (it.kg === null) continue
    const row = it.material_id ? rows.value.find((r) => r.material_id === it.material_id) : undefined
    if (row) row.kg = String(it.kg)
    else rows.value.push({ material_id: it.material_id, kg: String(it.kg), raw: it.material_id ? null : it.raw })
  }
  $q.notify({ type: out.items.length ? 'positive' : 'warning', message: out.items.length ? t('rec.found', { n: out.items.length }) : t('rec.nothing') })
}

async function send() {
  const lines = rows.value.filter((r) => r.kg.trim() !== '')
  if (lines.some((r) => !r.material_id)) return $q.notify({ type: 'warning', message: t('lines.errUnknown') })
  if (!lines.length) return $q.notify({ type: 'warning', message: t('lines.errEmpty') })
  saving.value = true
  try {
    const body = { ship_date: shipDate.value, lines: lines.map((r) => ({ material_id: r.material_id, kg: parseFloat(r.kg.replace(',', '.')) || 0 })) }
    if (editingId.value) await rhttp.put(`/submissions/${editingId.value}`, body)
    else await rhttp.post('/submissions', body)
    $q.notify({ type: 'positive', message: t('rcv.sent') })
    rows.value = []
    editingId.value = null
    shipDate.value = todayIso()
    await load()
    tab.value = 'history'
  } catch (e) {
    $q.notify({ type: 'negative', message: apiError(e) })
  } finally {
    saving.value = false
  }
}

function edit(s: Submission) {
  if (s.status !== 'pending') return
  editingId.value = s.id
  shipDate.value = s.ship_date
  rows.value = s.lines.map((l) => ({ material_id: l.material_id, kg: String(l.point_kg) }))
  tab.value = 'submit'
}

function remove(s: Submission) {
  $q.dialog({ title: t('rcv.deleteQ'), cancel: { label: t('common.cancel'), flat: true }, ok: { label: t('common.delete'), color: 'negative' } })
    .onOk(async () => {
      await rhttp.delete(`/submissions/${s.id}`)
      load()
    })
}
</script>

<template>
  <div class="rcv-app">
    <header class="top">
      <BrandLogo :size="32" />
      <div class="who">
        <div class="name">{{ me?.receiver_name }}</div>
        <div class="mg-sub">{{ me?.point_name }}</div>
      </div>
      <q-btn flat round dense icon="tune" :aria-label="t('settings.title')">
        <q-menu anchor="bottom right" self="top right" :offset="[0, 8]">
          <AppSettings can-logout @logout="emit('logout')" />
        </q-menu>
      </q-btn>
    </header>

    <main class="body">
      <section v-if="me" class="mg-card bal">
        <div class="mg-sub">{{ t('rcv.balance') }}</div>
        <div class="bal-v num" :class="devClass(me.balance?.balance_amount ?? 0)">{{ devMoney(me.balance?.balance_amount ?? 0) }}</div>
        <div class="mg-sub num">{{ devKg(me.balance?.balance_kg ?? 0) }} {{ t('common.kg') }}</div>
        <div v-if="owed.length" class="owed">
          <div class="mg-sub q-mb-xs">{{ t('rcv.owes') }}</div>
          <span v-for="m in owed" :key="m.material_id" class="chip num">{{ m.material_name }} · {{ devKg(-m.balance_kg).replace('+', '') }} {{ t('common.kg') }}</span>
        </div>
        <div v-else class="mg-sub q-mt-sm">{{ t('rcv.allGood') }}</div>
      </section>

      <div class="seg">
        <button type="button" :class="{ on: tab === 'submit' }" @click="tab = 'submit'"><q-icon name="upload" size="18px" />{{ t('rcv.tabSubmit') }}</button>
        <button type="button" :class="{ on: tab === 'history' }" @click="tab = 'history'"><q-icon name="history" size="18px" />{{ t('rcv.tabHistory') }}</button>
      </div>

      <section v-if="tab === 'submit'" class="mg-card pad">
        <div class="mg-h small">{{ t('rcv.submitTitle') }}</div>
        <div class="mg-sub q-mb-md">{{ editingId ? t('rcv.editing', { date: dateUa(shipDate) }) : t('rcv.submitSub') }}</div>
        <q-input v-model="shipDate" type="date" dense outlined :label="t('common.date')" class="q-mb-md" />
        <RecognizeInput @result="onResult" />

        <div v-if="rows.length" class="lines">
          <div v-for="(r, i) in rows" :key="i" class="line" :class="{ unk: !r.material_id }">
            <div class="col">
              <q-select v-model="r.material_id" :options="options(r.material_id)" emit-value map-options dense borderless
                :placeholder="t('lines.pickMaterial')" />
              <div v-if="!r.material_id && r.raw" class="raw">{{ t('lines.seenAs', { raw: r.raw }) }}</div>
            </div>
            <q-input v-model="r.kg" dense outlined inputmode="decimal" input-class="text-right num" class="kg" :suffix="t('common.kg')" />
            <q-btn flat round dense size="sm" icon="close" @click="rows.splice(i, 1)" />
          </div>
          <div class="sum"><span />
            <span class="num text-weight-bold">Σ {{ devKg(total).replace('+', '') }} {{ t('common.kg') }}</span></div>
        </div>
        <q-btn flat no-caps dense icon="add" :label="t('lines.addRow')" color="primary" class="q-mt-sm"
          @click="rows.push({ material_id: null, kg: '' })" />
      </section>

      <section v-else class="mg-card">
        <div v-if="!subs.length" class="empty">{{ t('rcv.noHistory') }}</div>
        <div v-for="s in subs" :key="s.id" class="sub" :class="{ clickable: s.status === 'pending' }" @click="edit(s)">
          <div class="sub-h">
            <span class="num text-weight-bold">{{ dateUa(s.ship_date) }}</span>
            <span class="badge" :class="s.status">{{ s.status === 'pending' ? t('rcv.pending') : t('rcv.done') }}</span>
            <q-space />
            <span v-if="s.totals" class="num text-weight-bold" :class="devClass(s.totals.deviation_amount)">{{ devMoney(s.totals.deviation_amount) }}</span>
            <q-btn v-if="s.status === 'pending'" flat round dense size="sm" icon="delete_outline" @click.stop="remove(s)" />
          </div>
          <div class="sub-lines">
            <span v-for="l in s.lines" :key="l.material_id" class="sl num">
              {{ l.material_name }} {{ devKg(l.point_kg).replace('+', '') }}
              <b v-if="l.deviation_kg !== null && Math.abs(l.deviation_kg) > 0.0005" :class="devClass(l.deviation_kg)">{{ devKg(l.deviation_kg) }}</b>
            </span>
          </div>
        </div>
      </section>
    </main>

    <div v-if="tab === 'submit' && rows.length" class="savebar">
      <q-btn unelevated no-caps color="primary" icon="send" :label="editingId ? t('rcv.update') : t('rcv.send')" :loading="saving"
        class="full-width" size="lg" @click="send" />
    </div>
  </div>
</template>

<style scoped>
.rcv-app { min-height: 100vh; background: var(--mg-bg-2); animation: in 0.5s cubic-bezier(0.16, 1, 0.3, 1) both; }
@keyframes in { from { opacity: 0; } }
.top { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 12px; padding: 10px 16px;
  background: color-mix(in srgb, var(--mg-bg-2) 80%, transparent); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--mg-border); }
.who { flex: 1; min-width: 0; }
.name { font-weight: 700; }
.body { max-width: 640px; margin: 0 auto; padding: 16px 16px 120px; display: flex; flex-direction: column; gap: 14px; }
.bal { padding: 18px; }
.bal-v { font-family: var(--mg-display); font-size: 30px; font-weight: 700; margin: 2px 0; }
.owed { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.owed .mg-sub { width: 100%; }
.chip { background: var(--mg-negative-soft); color: var(--mg-negative); border-radius: 999px; padding: 4px 10px; font-size: 13px; font-weight: 600; }
.seg { display: grid; grid-template-columns: 1fr 1fr; padding: 4px; gap: 4px; border-radius: 14px; background: var(--mg-bg); border: 1px solid var(--mg-border); }
.seg button { display: flex; align-items: center; justify-content: center; gap: 6px; height: 40px; border: 0; border-radius: 10px;
  background: transparent; color: var(--mg-fg-2); font: 600 14px 'Inter', sans-serif; cursor: pointer; transition: background 0.2s, color 0.2s; }
.seg button.on { background: var(--mg-primary); color: var(--mg-on-primary); }
.pad { padding: 18px; }
.mg-h.small { font-size: 18px; }
.lines { margin-top: 14px; border-top: 1px solid var(--mg-border); }
.line { display: flex; align-items: center; gap: 8px; padding: 6px 0 6px 10px; border-bottom: 1px solid var(--mg-border); border-left: 3px solid transparent; }
.line.unk { border-left-color: var(--mg-warning); background: var(--mg-warning-soft); }
.raw { font-size: 12px; color: var(--mg-warning); margin-top: -4px; }
.kg { width: 120px; }
.sum { display: flex; justify-content: space-between; padding: 10px 6px 0 10px; }
.empty { padding: 32px 16px; text-align: center; color: var(--mg-fg-3); }
.sub { padding: 14px 16px; border-bottom: 1px solid var(--mg-border); }
.sub:last-child { border-bottom: 0; }
.sub.clickable { cursor: pointer; }
.sub.clickable:hover { background: var(--mg-primary-soft); }
.sub-h { display: flex; align-items: center; gap: 8px; }
.badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
.badge.pending { background: var(--mg-primary-soft); color: var(--mg-fg); }
.badge.done { background: var(--mg-positive-soft); color: var(--mg-positive); }
.sub-lines { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; color: var(--mg-fg-2); }
.savebar { position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: color-mix(in srgb, var(--mg-bg) 88%, transparent); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border-top: 1px solid var(--mg-border); }
.savebar .q-btn { max-width: 608px; margin: 0 auto; display: flex; }
</style>

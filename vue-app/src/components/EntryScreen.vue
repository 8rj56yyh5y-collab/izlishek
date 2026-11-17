<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import { lang, setLang, t } from '@/i18n'
import { THEMES, setTheme, theme } from '@/theme'
import BrandLogo from './BrandLogo.vue'

const props = defineProps<{ needPassword: boolean }>()
const emit = defineEmits<{ done: [] }>()

const letters = computed(() => Array.from(t('brand')))
const password = ref('')
const error = ref('')
const busy = ref(false)
const leaving = ref(false)
const pwInput = ref<{ focus: () => void } | null>(null)
let timer: number | undefined

// «Іскри» на фоні: позиції фіксуємо один раз, щоб не стрибали при перерендері.
const sparks = Array.from({ length: 18 }, (_, i) => ({
  left: `${(i * 53) % 100}%`,
  delay: `${(i * 0.37) % 4}s`,
  dur: `${4 + ((i * 7) % 5)}s`,
  size: `${2 + (i % 3)}px`,
}))

function leave() {
  if (leaving.value) return
  leaving.value = true
  window.setTimeout(() => emit('done'), 480)
}

async function submit() {
  if (!password.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await axios.post('/api/v1/auth/login', { password: password.value }, { headers: { 'X-Lang': lang.value } })
    leave()
  } catch {
    error.value = t('entry.wrong')
    password.value = ''
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  if (!props.needPassword) timer = window.setTimeout(leave, 2600)
  else {
    await nextTick()
    window.setTimeout(() => pwInput.value?.focus(), 1300)
  }
})
onBeforeUnmount(() => window.clearTimeout(timer))
</script>

<template>
  <div class="entry" :class="{ leaving }" @click="!needPassword && leave()">
    <div class="glow" />
    <div class="sparks" aria-hidden="true">
      <i v-for="(s, i) in sparks" :key="i"
        :style="{ left: s.left, animationDelay: s.delay, animationDuration: s.dur, width: s.size, height: s.size }" />
    </div>

    <div class="center">
      <div class="logo"><BrandLogo :size="76" /></div>
      <h1 class="word" :aria-label="t('brand')">
        <span v-for="(ch, i) in letters" :key="lang + i" class="ch" :style="{ animationDelay: `${0.35 + i * 0.06}s` }">{{ ch }}</span>
        <span class="shine" aria-hidden="true">{{ t('brand') }}</span>
      </h1>
      <div class="bar" />
      <div class="tagline">{{ t('tagline') }}</div>

      <form v-if="needPassword" class="login" @submit.prevent="submit" @click.stop>
        <q-input ref="pwInput" v-model="password" type="password" dark outlined dense :label="t('entry.password')"
          color="primary" :error="!!error" :error-message="error" autocomplete="current-password" class="pw" />
        <q-btn type="submit" unelevated no-caps color="primary" :label="t('entry.enter')" :loading="busy"
          :disable="!password" class="go" />
      </form>
      <div v-else class="tap">{{ t('entry.tap') }}</div>
    </div>

    <div class="foot" @click.stop>
      <div class="langs">
        <button type="button" :class="{ on: lang === 'uk' }" @click="setLang('uk')">УКР</button>
        <button type="button" :class="{ on: lang === 'ru' }" @click="setLang('ru')">РУС</button>
      </div>
      <div class="dots">
        <button v-for="th in THEMES" :key="th.id" type="button" :class="{ on: theme === th.id }" :title="t(`theme.${th.id}`)"
          :style="{ background: `linear-gradient(135deg, ${th.swatch[0]} 50%, ${th.swatch[1]} 50%)` }"
          @click="setTheme(th.id)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.entry {
  position: fixed; inset: 0; z-index: 9000; overflow: hidden;
  background: #0E1013; color: #EDE6DD;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  transition: opacity 0.45s ease, transform 0.45s ease;
}
.entry.leaving { opacity: 0; transform: scale(1.04); pointer-events: none; }
.glow {
  position: absolute; inset: -20%;
  background:
    radial-gradient(40% 35% at 50% 45%, color-mix(in srgb, var(--mg-primary) 38%, transparent), transparent 70%),
    repeating-linear-gradient(115deg, rgba(255,255,255,0.025) 0 2px, transparent 2px 14px);
  animation: breathe 6s ease-in-out infinite;
}
@keyframes breathe { 50% { transform: scale(1.06); opacity: 0.85; } }

.sparks i {
  position: absolute; bottom: -10px; border-radius: 50%;
  background: color-mix(in srgb, var(--mg-primary) 70%, #FFE2B8);
  box-shadow: 0 0 8px 2px color-mix(in srgb, var(--mg-primary) 60%, transparent);
  opacity: 0; animation: rise linear infinite;
}
@keyframes rise {
  0% { transform: translateY(0) translateX(0); opacity: 0; }
  10% { opacity: 0.9; }
  100% { transform: translateY(-105vh) translateX(30px); opacity: 0; }
}

.center { position: relative; display: flex; flex-direction: column; align-items: center; padding: 0 16px; text-align: center; }
.logo { animation: pop 0.7s cubic-bezier(0.2, 1.4, 0.4, 1) both; filter: drop-shadow(0 6px 24px color-mix(in srgb, var(--mg-primary) 55%, transparent)); }
@keyframes pop { from { transform: scale(0.3) translateY(20px); opacity: 0; } }

.word {
  position: relative; margin: 18px 0 0; font-family: 'Unbounded', 'Inter', sans-serif; font-weight: 800;
  font-size: clamp(34px, 9vw, 64px); line-height: 1.1; letter-spacing: 0.01em; color: #F4EEE6;
}
.ch { display: inline-block; opacity: 0; animation: ch-in 0.6s cubic-bezier(0.2, 0.9, 0.3, 1) both; }
@keyframes ch-in { from { opacity: 0; transform: translateY(45%) rotateX(70deg); filter: blur(6px); } to { opacity: 1; transform: none; filter: none; } }
.shine {
  position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(100deg, transparent 35%, rgba(255, 230, 200, 0.95) 50%, transparent 65%);
  background-size: 250% 100%; background-position: 150% 0;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: sweep 1.3s ease-in-out 1.15s both;
}
@keyframes sweep { to { background-position: -50% 0; } }
.bar { width: 0; height: 3px; margin-top: 14px; border-radius: 3px; background: var(--mg-primary); animation: bar 0.7s ease-out 1.1s forwards; }
@keyframes bar { to { width: 120px; } }
.tagline { margin-top: 12px; font-size: 15px; color: #B6ADA2; opacity: 0; animation: fade 0.6s ease 1.4s forwards; }
@keyframes fade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

.login { margin-top: 34px; display: flex; gap: 8px; align-items: flex-start; width: min(360px, 88vw); opacity: 0; animation: fade 0.6s ease 1.7s forwards; }
.pw { flex: 1; }
.go { height: 40px; padding: 0 18px; }
.tap { margin-top: 34px; font-size: 13px; color: #8F877E; opacity: 0; animation: fade 0.6s ease 1.7s forwards, blink 1.6s ease-in-out 2.3s infinite; }
@keyframes blink { 50% { opacity: 0.45; } }

.foot { position: absolute; bottom: calc(18px + env(safe-area-inset-bottom)); display: flex; gap: 18px; align-items: center; opacity: 0; animation: fade 0.6s ease 1.9s forwards; }
.langs { display: flex; border: 1px solid rgba(255,255,255,0.18); border-radius: 999px; overflow: hidden; }
.langs button { background: transparent; color: #B6ADA2; border: 0; padding: 6px 12px; font: 600 12px 'Inter', sans-serif; cursor: pointer; }
.langs button.on { background: var(--mg-primary); color: #fff; }
.dots { display: flex; gap: 8px; }
.dots button { width: 22px; height: 22px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.25); cursor: pointer; padding: 0; }
.dots button.on { border-color: #fff; }

@media (prefers-reduced-motion: reduce) {
  .glow, .sparks i, .tap { animation: none; }
  .ch, .logo, .tagline, .login, .foot, .bar, .tap { animation-duration: 0.01s; animation-delay: 0s; }
  .shine { display: none; }
}
</style>

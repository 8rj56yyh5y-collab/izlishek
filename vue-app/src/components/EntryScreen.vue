<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import axios from 'axios'
import { lang, setLang, t } from '@/i18n'
import { THEMES, setTheme, theme } from '@/theme'
import BrandLogo from './BrandLogo.vue'

const props = defineProps<{ needPassword: boolean; receiverMode?: boolean }>()
const emit = defineEmits<{ done: [role: string] }>()

// Цитата на вході — одна, обрана власником.
// [uk, ru, автор uk, автор ru]
const QUOTES: [string, string, string, string][] = [
  ['Ніколи не змарнуй кризу. Криза дає змогу прийняти зміни, навчитися і змінитися для майбутнього зростання.',
    'Никогда не упускай кризис. Кризис даёт возможность принять изменения, учиться и меняться для будущего роста.',
    'за мотивами Рама Емануеля', 'по мотивам Рама Эмануэля'],
]
const custom = ref<{ text: string; author: string }[]>([])
const seed = Math.random()
const phrase = computed(() => custom.value.length
  ? custom.value[Math.floor(seed * custom.value.length)].text
  : QUOTES[Math.floor(seed * QUOTES.length)][lang.value === 'ru' ? 1 : 0])
const author = computed(() => custom.value.length
  ? custom.value[Math.floor(seed * custom.value.length)].author
  : QUOTES[Math.floor(seed * QUOTES.length)][lang.value === 'ru' ? 3 : 2])
// Свої цитати підвантажуємо одразу; поки йде запит — фраза ще прихована анімацією.
axios.get<{ text: string; author: string }[]>('/api/v1/auth/quotes').then((r) => { custom.value = r.data }).catch(() => {})

const password = ref('')
const error = ref('')
const busy = ref(false)
const shake = ref(false)
const leaving = ref(false)
const input = ref<HTMLInputElement | null>(null)
let timer: number | undefined

function leave(role = 'admin') {
  if (leaving.value) return
  leaving.value = true
  window.setTimeout(() => emit('done', role), 520)
}

async function submit() {
  if (!password.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const r = await axios.post<{ role: string }>('/api/v1/auth/login', { password: password.value },
      { headers: { 'X-Lang': lang.value } })
    leave(r.data.role)
  } catch (e) {
    const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = d || t('entry.wrong')
    password.value = ''
    shake.value = false
    await nextTick()
    shake.value = true
    input.value?.focus()
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  if (!props.needPassword) timer = window.setTimeout(() => leave(), 2400)
  else window.setTimeout(() => input.value?.focus(), 900)
})
onBeforeUnmount(() => window.clearTimeout(timer))
</script>

<template>
  <div class="entry" :class="{ leaving }" @click="!needPassword && leave()">
    <div class="blob b1" />
    <div class="blob b2" />
    <div class="grid" />

    <main class="center">
      <div class="logo-wrap">
        <div class="halo" />
        <BrandLogo large :size="200" class="logo" />
      </div>
      <figure class="quote">
        <blockquote class="phrase">{{ phrase }}</blockquote>
        <figcaption v-if="author" class="author">{{ author }}</figcaption>
      </figure>

      <form v-if="needPassword" class="login" :class="{ shake }" @submit.prevent="submit" @click.stop
        @animationend="shake = false">
        <div class="field" :class="{ err: !!error }">
          <q-icon name="lock" size="18px" class="lock" />
          <input ref="input" v-model="password" type="password" :placeholder="receiverMode ? t('entry.passwordOrPin') : t('entry.password')"
            autocomplete="current-password" :aria-label="t('entry.password')" @input="error = ''" />
          <button type="submit" class="go" :disabled="!password || busy" :aria-label="t('entry.enter')">
            <q-spinner v-if="busy" size="18px" />
            <q-icon v-else name="arrow_forward" size="20px" />
          </button>
        </div>
        <div class="err-msg">{{ error }}</div>
      </form>
      <button v-else type="button" class="start" @click.stop="leave()">{{ t('entry.enter') }}</button>
    </main>

    <footer class="foot" @click.stop>
      <div class="langs">
        <button type="button" :class="{ on: lang === 'uk' }" @click="setLang('uk')">УКР</button>
        <button type="button" :class="{ on: lang === 'ru' }" @click="setLang('ru')">РУС</button>
      </div>
      <div class="dots">
        <button v-for="th in THEMES" :key="th.id" type="button" :class="{ on: theme === th.id }" :aria-label="t(`theme.${th.id}`)"
          :style="{ background: `linear-gradient(135deg, ${th.swatch[0]} 50%, ${th.swatch[1]} 50%)` }"
          @click="setTheme(th.id)" />
      </div>
    </footer>
  </div>
</template>

<style scoped>
.entry {
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
  --y: #F5B800;
  position: fixed; inset: 0; z-index: 9000; overflow: hidden;
  background: #0A0B0C; color: #F2EFE8;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  transition: opacity 0.5s var(--ease), filter 0.5s var(--ease);
}
.entry.leaving { opacity: 0; filter: blur(6px); pointer-events: none; }
.entry.leaving .logo-wrap { transform: scale(1.06); }

/* фон: два розмитих теплих «прожектори», що повільно дрейфують, і ледь помітна сітка */
.blob { position: absolute; border-radius: 50%; filter: blur(90px); opacity: 0; animation: blob-in 1.6s var(--ease) 0.1s forwards; }
.b1 { width: 52vmax; height: 52vmax; left: -14vmax; top: -18vmax; background: rgba(245, 184, 0, 0.16); }
.b2 { width: 46vmax; height: 46vmax; right: -16vmax; bottom: -20vmax; background: rgba(255, 138, 61, 0.10); }
@keyframes blob-in { to { opacity: 1; } }
.b1 { animation: blob-in 1.6s var(--ease) 0.1s forwards, drift1 22s ease-in-out 1.6s infinite alternate; }
.b2 { animation: blob-in 1.6s var(--ease) 0.3s forwards, drift2 26s ease-in-out 1.8s infinite alternate; }
@keyframes drift1 { to { transform: translate(8vmax, 6vmax); } }
@keyframes drift2 { to { transform: translate(-7vmax, -5vmax); } }
.grid {
  position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
  background-size: 22px 22px;
  mask-image: radial-gradient(60% 55% at 50% 45%, #000 0%, transparent 80%);
  -webkit-mask-image: radial-gradient(60% 55% at 50% 45%, #000 0%, transparent 80%);
}

.center { position: relative; display: flex; flex-direction: column; align-items: center; padding: 0 20px; text-align: center; width: 100%; }
.logo-wrap { position: relative; transition: transform 0.5s var(--ease); }
.logo { position: relative; height: clamp(150px, 30vh, 220px) !important; animation: logo-in 1.1s var(--ease) both; }
@keyframes logo-in { from { opacity: 0; transform: translateY(14px) scale(0.94); filter: blur(14px); } }
.halo {
  position: absolute; left: 50%; top: 55%; width: 70%; height: 40%; transform: translate(-50%, -50%);
  background: radial-gradient(closest-side, rgba(245, 184, 0, 0.35), transparent); filter: blur(18px);
  opacity: 0; animation: fade-in 1.2s var(--ease) 0.5s forwards, halo 5s ease-in-out 1.7s infinite alternate;
}
@keyframes halo { to { opacity: 0.55; transform: translate(-50%, -50%) scale(1.12); } }

.quote { margin: 26px 0 0; }
.author { margin-top: 8px; font-size: 13px; color: #8A857C; letter-spacing: 0.04em; opacity: 0; animation: up 0.9s var(--ease) 0.75s forwards; }
.author::before { content: '— '; }
.phrase {
  margin: 0; font-style: italic; max-width: 520px; font-size: clamp(16px, 2.4vw, 19px); line-height: 1.45; font-weight: 500;
  color: #D9D4CA; letter-spacing: 0.005em; opacity: 0; animation: up 0.9s var(--ease) 0.55s forwards;
}
@keyframes up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes fade-in { to { opacity: 1; } }

.login { margin-top: 30px; width: min(380px, 100%); opacity: 0; animation: up 0.9s var(--ease) 0.8s forwards; }
.login.shake { animation: shake 0.42s ease; opacity: 1; }
@keyframes shake { 20%, 60% { transform: translateX(-7px); } 40%, 80% { transform: translateX(7px); } }
.field {
  display: flex; align-items: center; gap: 8px; height: 54px; padding: 0 6px 0 16px;
  border-radius: 16px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.10);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}
.field:focus-within { border-color: rgba(245, 184, 0, 0.7); box-shadow: 0 0 0 4px rgba(245, 184, 0, 0.12); background: rgba(255, 255, 255, 0.07); }
.field.err { border-color: rgba(255, 107, 107, 0.8); }
.lock { color: #8A857C; }
.field input {
  flex: 1; min-width: 0; height: 100%; background: transparent; border: 0; outline: 0;
  color: #F2EFE8; font: 500 16px 'Inter', sans-serif; letter-spacing: 0.04em;
}
.field input::placeholder { color: #7F7A72; letter-spacing: 0; }
.go {
  width: 42px; height: 42px; border-radius: 12px; border: 0; cursor: pointer; display: grid; place-items: center;
  background: var(--y); color: #15120A; transition: transform 0.15s var(--ease), opacity 0.2s, background 0.2s;
}
.go:hover:not(:disabled) { transform: translateX(2px); }
.go:disabled { opacity: 0.35; cursor: default; }
.err-msg { min-height: 20px; margin-top: 8px; font-size: 13px; color: #FF8E8E; }

.start {
  margin-top: 30px; padding: 12px 28px; border-radius: 14px; border: 0; cursor: pointer;
  background: var(--y); color: #15120A; font: 700 15px 'Inter', sans-serif;
  opacity: 0; animation: up 0.9s var(--ease) 0.8s forwards;
}

.foot {
  position: absolute; bottom: calc(20px + env(safe-area-inset-bottom)); display: flex; gap: 16px; align-items: center;
  opacity: 0; animation: fade-in 1s var(--ease) 1.1s forwards;
}
.langs { display: flex; padding: 3px; border-radius: 999px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.08); }
.langs button { background: transparent; color: #A39E94; border: 0; padding: 5px 12px; border-radius: 999px; font: 600 12px 'Inter', sans-serif; cursor: pointer; transition: background 0.2s, color 0.2s; }
.langs button.on { background: rgba(255, 255, 255, 0.12); color: #F2EFE8; }
.dots { display: flex; gap: 8px; }
.dots button { width: 20px; height: 20px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.18); cursor: pointer; padding: 0; transition: transform 0.2s var(--ease), border-color 0.2s; }
.dots button:hover { transform: scale(1.12); }
.dots button.on { border-color: #F2EFE8; }

@media (prefers-reduced-motion: reduce) {
  .blob, .halo { animation: blob-in 0.01s forwards; }
  .logo, .phrase, .author, .login, .start, .foot { animation-duration: 0.01s; animation-delay: 0s; }
}
</style>

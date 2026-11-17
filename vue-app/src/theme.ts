import { computed, ref } from 'vue'
import { Dark, setCssVar } from 'quasar'

export type ThemeId = 'copper' | 'steel' | 'khaki'

/** Три теми. «Мідь» — фірмова й типова: графіт + мідний акцент (металобрухт, але без «завода»).
 *  Кольори кнопок/брендів Quasar беремо звідси ж, токени сторінки — у tokens.css. */
export const THEMES: { id: ThemeId; dark: boolean; primary: string; positive: string; negative: string; swatch: [string, string] }[] = [
  { id: 'copper', dark: true, primary: '#C8691C', positive: '#3FB37F', negative: '#F05D5E', swatch: ['#1A1D21', '#D9822B'] },
  { id: 'steel', dark: false, primary: '#2F5D8A', positive: '#15803D', negative: '#DC2626', swatch: ['#EEF1F4', '#2F5D8A'] },
  { id: 'khaki', dark: false, primary: '#56652B', positive: '#1F8A5B', negative: '#C62828', swatch: ['#EDEEE4', '#56652B'] },
]

function stored(): ThemeId {
  try {
    const v = localStorage.getItem('bt_theme')
    if (v === 'copper' || v === 'steel' || v === 'khaki') return v
  } catch { /* приватне вікно */ }
  return 'copper'
}

export const theme = ref<ThemeId>(stored())
export const isDark = computed(() => THEMES.find((x) => x.id === theme.value)!.dark)
/** Кольори для неактивних сегментів q-btn-toggle під поточну тему. */
export const seg = computed(() => (isDark.value ? { color: 'grey-9', text: 'grey-4' } : { color: 'grey-2', text: 'grey-9' }))

export function setTheme(id: ThemeId) {
  const th = THEMES.find((x) => x.id === id)!
  theme.value = id
  try { localStorage.setItem('bt_theme', id) } catch { /* ignore */ }
  document.documentElement.dataset.theme = id
  Dark.set(th.dark)
  setCssVar('primary', th.primary)
  setCssVar('positive', th.positive)
  setCssVar('negative', th.negative)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', th.swatch[0])
}

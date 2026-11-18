import { computed, ref } from 'vue'
import { t } from '@/i18n'

export type PeriodKey = 'week' | 'month' | 'year' | 'all'
const iso = (d: Date) => d.toLocaleDateString('sv-SE')

function stored(): PeriodKey {
  try {
    const v = localStorage.getItem('bt_period')
    if (v === 'week' || v === 'month' || v === 'year' || v === 'all') return v
  } catch { /* ignore */ }
  return 'all'
}

/** Спільний для «Головної» та «Історії» вибір періоду (запамʼятовується). */
export const periodKey = ref<PeriodKey>(stored())
export function setPeriod(k: PeriodKey) {
  periodKey.value = k
  try { localStorage.setItem('bt_period', k) } catch { /* ignore */ }
}
export const periodRange = computed(() => {
  const now = new Date()
  const back = (days: number) => iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() - days))
  switch (periodKey.value) {
    case 'week': return { date_from: back(6), date_to: iso(now) }
    case 'month': return { date_from: back(29), date_to: iso(now) }
    case 'year': return { date_from: back(364), date_to: iso(now) }
    default: return { date_from: null, date_to: null }
  }
})
export const periodOptions = computed(() => (['week', 'month', 'year', 'all'] as PeriodKey[]).map((k) => ({ k, label: t(`per.${k}`) })))

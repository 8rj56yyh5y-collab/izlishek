import { useQuasar } from 'quasar'
import type { Material } from '@/api'
import { dateUa, devKg, devMoney } from '@/format'
import { t } from '@/i18n'
import { num, type Row } from '@/lines'

/** Короткий текст підсумку звірки для месенджера: спершу мінуси, потім плюси, наприкінці разом. */
export function summaryText(rows: Row[], materials: Material[], ctx: { date: string; point: string; who: string }): string {
  const byId = new Map(materials.map((m) => [m.id, m]))
  const lines: { name: string; dev: number; amount: number }[] = []
  let dev = 0
  let amount = 0
  for (const r of rows) {
    const a = num(r.point_kg)
    const b = num(r.warehouse_kg)
    if (a === null || b === null || !r.material_id) continue
    const d = Math.round((b - a) * 1000) / 1000
    const m = byId.get(r.material_id)
    const am = d * (r.price_per_kg ?? m?.price_per_kg ?? 0)
    dev += d
    amount += am
    if (Math.abs(d) > 0.0005) lines.push({ name: m?.name ?? '?', dev: d, amount: am })
  }
  lines.sort((x, y) => x.dev - y.dev)
  const out = [t('share.head', { date: dateUa(ctx.date), point: ctx.point, who: ctx.who }), '']
  for (const l of lines) out.push(`${l.dev < 0 ? '🔴' : '🟢'} ${l.name}: ${devKg(l.dev)} ${t('common.kg')}${l.amount ? ` (${devMoney(l.amount)})` : ''}`)
  if (lines.length) out.push('')
  out.push(t('share.total', { kg: devKg(Math.round(dev * 1000) / 1000), money: devMoney(amount) }))
  return out.join('\n')
}

/** Системне «Поділитися» на телефоні (Viber/Telegram/…), інакше — копіювання в буфер. */
export function useShare() {
  const $q = useQuasar()
  return async (text: string) => {
    const nav = navigator as Navigator & { share?: (d: { text: string }) => Promise<void> }
    if (nav.share && /Android|iPhone|iPad|Mobile/i.test(navigator.userAgent)) {
      try { await nav.share({ text }); return } catch { /* скасовано — пробуємо буфер */ }
    }
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      ta.remove()
    }
    $q.notify({ type: 'positive', message: t('share.copied'), icon: 'content_copy' })
  }
}

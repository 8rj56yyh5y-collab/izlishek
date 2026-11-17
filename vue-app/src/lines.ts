import type { RecognizedItem } from '@/api'

export interface Row {
  material_id: number | null
  point_kg: string
  warehouse_kg: string
  price_per_kg: number | null
  raw?: string | null // як було написано на фото/в тексті, якщо матеріал не впізнано
}

export type Column = 'point' | 'warehouse'

export const num = (s: string) => {
  const v = parseFloat(String(s).replace(',', '.').replace(/\s/g, ''))
  return Number.isFinite(v) ? v : null
}

const fmt = (v: number) => String(Math.round(v * 1000) / 1000)
const norm = (s: string | null | undefined) => (s ?? '').trim().toLowerCase()

/** Кладе розпізнані рядки в обрану колонку. Якщо в рядку дві ваги (kg2) —
 *  друга йде в іншу колонку: так фото сторінки зошита «Я | ДМС» заповнює все одразу. */
export function mergeRecognized(rows: Row[], items: RecognizedItem[], column: Column): { filled: number; unknown: number } {
  const other: Column = column === 'point' ? 'warehouse' : 'point'
  const key = (c: Column) => (c === 'point' ? 'point_kg' : 'warehouse_kg') as 'point_kg' | 'warehouse_kg'
  let filled = 0
  let unknown = 0
  for (const it of items) {
    if (it.kg === null) continue
    let row = it.material_id
      ? rows.find((r) => r.material_id === it.material_id)
      : rows.find((r) => !r.material_id && norm(r.raw) === norm(it.raw))
    if (!row) {
      row = { material_id: it.material_id, point_kg: '', warehouse_kg: '', price_per_kg: null, raw: it.raw }
      rows.push(row)
    }
    row[key(column)] = fmt(it.kg)
    if (it.kg2 !== null) row[key(other)] = fmt(it.kg2)
    filled++
    if (!it.material_id) unknown++
  }
  return { filled, unknown }
}

export function linesPayload(rows: Row[]): { lines: object[]; error?: string } {
  const used = rows.filter((r) => r.point_kg !== '' || r.warehouse_kg !== '')
  if (used.some((r) => !r.material_id)) return { lines: [], error: 'Оберіть матеріал у жовтих рядках' }
  const ids = used.map((r) => r.material_id)
  if (new Set(ids).size !== ids.length) return { lines: [], error: 'Матеріал повторюється в кількох рядках' }
  if (!used.length) return { lines: [], error: 'Внесіть вагу хоча б по одному матеріалу' }
  return {
    lines: used.map((r) => ({
      material_id: r.material_id,
      point_kg: num(r.point_kg) ?? 0,
      warehouse_kg: num(r.warehouse_kg) ?? 0,
      price_per_kg: r.price_per_kg,
    })),
  }
}

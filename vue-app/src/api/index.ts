import axios from 'axios'

export const http = axios.create({ baseURL: '/api/v1/surplus' })

export interface Point { id: number; name: string; receiver_name: string; is_active: boolean }
export interface Material { id: number; name: string; group: string; price_per_kg: number; sort: number; is_active: boolean }
export interface Totals {
  point_kg: number; warehouse_kg: number; deviation_kg: number
  surplus_kg: number; shortage_kg: number
  deviation_amount: number; surplus_amount: number; shortage_amount: number
}
export interface Line {
  id: number; material_id: number; material_name: string
  point_kg: number; warehouse_kg: number; price_per_kg: number
  deviation_kg: number; deviation_pct: number | null; deviation_amount: number
}
export interface Shipment {
  id: number; ship_date: string; point_id: number; point_name: string
  receiver_name: string; destination: string; note: string | null
  lines: Line[]; totals: Totals
}
export interface ShipmentListItem extends Omit<Shipment, 'lines' | 'note'> { lines_count: number }
export interface MaterialBalance {
  material_id: number; material_name: string
  deviation_kg: number; settled_kg: number; balance_kg: number; balance_amount: number
}
export interface ReceiverBalance {
  receiver_name: string; shipments: number; surplus_kg: number; shortage_kg: number
  balance_kg: number; balance_amount: number; materials: MaterialBalance[]
}
export interface MaterialStat {
  material_id: number; material_name: string; point_kg: number; warehouse_kg: number
  deviation_kg: number; deviation_pct: number | null; deviation_amount: number
}
export interface TimelinePoint {
  shipment_id: number; ship_date: string; point_name: string; receiver_name: string
  deviation_kg: number; deviation_amount: number
}
export interface Summary {
  shipments: number; totals: Totals; receivers: ReceiverBalance[]
  materials: MaterialStat[]; timeline: TimelinePoint[]
}
export interface LedgerRow {
  kind: 'shipment' | 'settlement'; ref_id: number; on_date: string; title: string
  material_id: number; material_name: string; kg: number; amount: number
  balance_kg: number; balance_amount: number
}
export interface Settlement {
  id: number; settle_date: string; receiver_name: string; material_id: number
  material_name: string; kg: number; price_per_kg: number; amount: number; note: string | null
}

export interface Period { date_from?: string | null; date_to?: string | null; point_id?: number | null }

export function cleanParams(p: Period): Record<string, string | number> {
  const out: Record<string, string | number> = {}
  for (const [k, v] of Object.entries(p)) if (v !== null && v !== undefined && v !== '') out[k] = v
  return out
}

export function apiError(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x: { msg?: string }) => x.msg ?? '').join('; ')
  return 'Помилка запиту'
}

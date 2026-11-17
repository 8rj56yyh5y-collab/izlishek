const kgFmt = new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 0, maximumFractionDigits: 3 })
const moneyFmt = new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
const pctFmt = new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

const sign = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '')

export const kg = (v: number) => kgFmt.format(v)
export const devKg = (v: number) => (v === 0 ? '0' : sign(v) + kgFmt.format(Math.abs(v)))
export const devMoney = (v: number) => (Math.round(v) === 0 ? '0 ₴' : sign(v) + moneyFmt.format(Math.abs(v)) + ' ₴')
export const money = (v: number) => moneyFmt.format(v) + ' ₴'
export const devPct = (v: number | null) => (v === null ? '—' : v === 0 ? '0%' : sign(v) + pctFmt.format(Math.abs(v)) + '%')
export const devClass = (v: number) => (v > 0.0005 ? 'dev-pos' : v < -0.0005 ? 'dev-neg' : 'dev-zero')
export const dateUa = (iso: string) => iso.split('-').reverse().join('.')
export const todayIso = () => new Date().toLocaleDateString('sv-SE')

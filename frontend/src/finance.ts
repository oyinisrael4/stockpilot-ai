import type { Supplier } from './api'

export type Customer = Supplier & { balance: string | null }
export type Discount = { kind: 'fixed' | 'percent'; value: string }
export type SaleItem = { product: number; quantity: string; discount: Discount }
export type Method = 'cash' | 'transfer' | 'card'
export type Payment = { method: Method; amount: string }
export type Draft = {
  request_id: string; customer: number | null; notes: string; payments: Payment[]
  lines: SaleItem[]; discount: Discount
}
export type Totals = { subtotal: string; discount: string; tax: string; total: string }
export type Quote = Totals & { lines: (Totals & { product: number })[] }
export type SaleLine = Totals & { id: number; name: string; quantity: string; returned_quantity: string; price: string; unit: string; tracked: boolean }
export type ReturnRecord = {
  id: number; sale: number; created_at: string; reason: string; void: boolean; total: string; refund: string
  refund_method: Method | ''; lines: { sale_line: number; name: string; quantity: string; restocked: boolean; total: string }[]
}
export type Sale = Totals & {
  id: number; request_id: string; status: 'draft' | 'completed' | 'voided'; created_at: string; posted_at: string | null
  customer_name: string; notes: string; paid: string; balance: string; returned: string
  lines: SaleLine[]; payments: (Payment & { id: number })[]; returns: ReturnRecord[]; draft: Draft
}
export type Expense = { id: number; category: number; category_name: string; amount: string; incurred_on: string; description: string; method: Method; voided: boolean }

export const methods: Record<Method, string> = { cash: 'Cash', transfer: 'Bank transfer', card: 'Card' }
export const zeroDiscount: Discount = { kind: 'fixed', value: '0' }
export const canSell = (role: string) => ['owner', 'manager', 'cashier'].includes(role)
export const todayIn = (zone: string) => new Intl.DateTimeFormat('sv-SE', { timeZone: zone }).format(new Date())
export const shortDate = (date: string, zone: string) => new Intl.DateTimeFormat('en-NG', { dateStyle: 'medium', timeZone: zone }).format(new Date(date))

export function minor(value: string) {
  if (!/^\d+(\.\d{0,2})?$/.test(value)) return 0n
  const [whole, fraction = ''] = value.split('.')
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
}

export function decimal(value: bigint) {
  const absolute = value < 0 ? -value : value
  return `${value < 0 ? '-' : ''}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`
}

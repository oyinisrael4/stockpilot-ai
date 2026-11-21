/// <reference types="vite/client" />
import { useCallback, useEffect, useState } from 'react'

export type User = { id: number; username: string; email: string; first_name: string; last_name: string }
export type Business = {
  id: number; name: string; role: string; currency: string; timezone: string
  address: string; receipt_footer: string; tax_rate: string
}
export type Product = {
  id: number; name: string; sku: string; barcode: string; category: number | null
  category_name: string | null; description: string; image_url: string; unit: string; price: string; cost: string
  stock: string; reorder_level: string; taxable: boolean; track_stock: boolean; active: boolean
}
export type Category = { id: number; name: string }
export type Supplier = { id: number; name: string; email: string; phone: string; address: string; active: boolean }
export type Movement = { id: number; product_name: string; kind: string; quantity: string; balance: string; unit_cost: string; created_at: string }
export type Receipt = {
  id: number; supplier_name: string; reference: string; received_on: string
  lines: { product: number; product_name: string; quantity: string; unit_cost: string }[]
}
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] }

function errorMessage(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(errorMessage).join(' ')
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([key, error]) =>
      key === 'detail' || key === 'non_field_errors' ? errorMessage(error) : `${key.replaceAll('_', ' ')} · ${errorMessage(error)}`).join(' ')
  }
  return 'The request could not be completed.'
}

export async function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  const prefix = (import.meta.env.VITE_STOCKPILOT_CSRF_COOKIE || 'csrftoken') + '='
  const token = document.cookie.split('; ').find(cookie => cookie.startsWith(prefix))?.slice(prefix.length) ?? ''
  const response = await fetch(`/api/v1/${path}`, {
    method, signal, credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': body instanceof Blob ? body.type : 'application/json', 'X-CSRFToken': decodeURIComponent(token) },
    body: body === undefined || body instanceof Blob ? body : JSON.stringify(body),
  })
  if (response.status === 204) return undefined as T
  const data = response.headers.get('Content-Type')?.includes('application/json') ? await response.json() : null
  if (!response.ok) throw new Error(data ? errorMessage(data) : `Request failed (${response.status}). Please refresh and try again.`)
  return data as T
}

export function useData<T>(path: string) {
  const [state, setState] = useState<{ path: string; data?: T; error?: string }>({ path })
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision(value => value + 1), [])
  useEffect(() => {
    const controller = new AbortController()
    api<T>(path, 'GET', undefined, controller.signal).then(
      data => { if (!controller.signal.aborted) setState({ path, data }) },
      error => { if (!controller.signal.aborted) setState({ path, error: error.message }) },
    )
    return () => controller.abort()
  }, [path, revision])
  return {
    data: state.path === path ? state.data : undefined,
    error: state.path === path ? state.error : undefined,
    refresh,
  }
}

export const tenant = (business: Business, resource: string) => `businesses/${business.id}/${resource}`
export const editable = (business: Business) => ['owner', 'manager'].includes(business.role)
export function money(value: string, business: Business, digits = 2) {
  const [integer, fraction = ''] = value.split('.')
  const formatter = new Intl.NumberFormat('en-NG', { style: 'currency', currency: business.currency, maximumFractionDigits: digits })
  const whole = integer === '-0' ? -0 : BigInt(integer)
  const decimals = fraction.padEnd(2, '0').slice(0, digits).replace(/(\d\d.*?)0+$/, '$1')
  return formatter.formatToParts(whole).map(part => part.type === 'fraction' ? decimals : part.value).join('')
}
export const quantity = (value: string) => new Intl.NumberFormat('en-NG', { maximumFractionDigits: 3 }).format(Number(value))

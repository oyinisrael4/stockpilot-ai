import { ArrowUpRight, Check, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, money, quantity, tenant } from './api'
import type { Business, Category } from './api'
import { Lookup } from './catalog'
import { methods, todayIn } from './finance'
import { Dialog, Form } from './ui'

type Cell = string | { money: string }
type Series = { date: string; net_sales: string; operating_expenses: string }
export type Card =
  | { kind: 'table'; title: string; headers: string[]; rows: Cell[][]; link: string }
  | { kind: 'finance'; title: string; start: string; end: string; comparison: string | null; metrics: { label: string; value: string; comparison: string | null }[]; series: Series[]; observations?: string[]; link: string }
  | { kind: 'insights'; items: string[]; link: string }
type Kind = 'sale' | 'expense' | 'purchase' | 'opening' | 'adjustment'
export type Proposal = {
  id: number; revision: number; expires_at: string; kind: Kind
  status: 'pending' | 'confirmed' | 'cancelled' | 'expired' | 'failed'
  payload: Record<string, string | number | null | { kind: string; value: string }>
  preview: Record<string, string>
  result: { id?: number; stock?: string | null; link?: string; error?: unknown }
}
const kinds: Record<Kind, string> = { sale: 'Sale', expense: 'Expense', purchase: 'Purchase receipt', opening: 'Opening stock', adjustment: 'Stock adjustment' }
const paymentLabels: Record<string, string> = { ...methods, credit: 'Credit' }
const labels: Record<string, string> = {
  product: 'Product', sku: 'SKU', unit: 'Unit', unit_price: 'Unit price', quantity: 'Quantity', subtotal: 'Subtotal',
  discount: 'Discount', tax: 'Tax', customer: 'Customer', method: 'Payment', notes: 'Notes', outstanding: 'Outstanding',
  supplier: 'Supplier', unit_cost: 'Unit cost', date: 'Date', reference: 'Reference', category: 'Category', description: 'Description',
  new_balance: 'New stock balance', reason: 'Reason',
}
const moneyFields = new Set(['unit_price', 'subtotal', 'discount', 'tax', 'outstanding', 'unit_cost'])

function formatFailure(value: unknown): string {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(formatFailure).join(' ')
  if (value && typeof value === 'object') return Object.values(value).map(formatFailure).join(' ')
  return 'Review stock and transaction details before preparing a new preview.'
}

export function Trend({ series }: { series: Series[] }) {
  if (series.length < 2) return null
  const all = series.flatMap(point => [Number(point.net_sales), Number(point.operating_expenses)])
  const min = Math.min(0, ...all), max = Math.max(0, ...all)
  const y = (value: string) => 75 - 58 * ((Number(value) - min) / (max - min || 1))
  const path = (key: 'net_sales' | 'operating_expenses') => series.map((point, i) =>
    (i ? 'L' : 'M') + (12 + i * 396 / (series.length - 1)) + ',' + y(point[key])).join(' ')
  return <figure className="assistant-trend">
    <figcaption>Recorded trend <span>Net sales · Expenses</span></figcaption>
    <svg viewBox="0 0 420 88" role="img" aria-label="Net sales in blue and operating expenses in violet">
      {[18, 37, 56, 75].map(tick => <line key={tick} x1="12" x2="408" y1={tick} y2={tick} stroke="#e2e7f8" />)}
      <path d={path('net_sales')} className="line sales-line" /><path d={path('operating_expenses')} className="line expense-line" />
    </svg>
    <div><small>{series[0].date}</small><small>{series.at(-1)?.date}</small></div>
  </figure>
}

export function InsightCard({ card, business }: { card: Card; business: Business }) {
  return <section className="assistant-card">
    {card.kind === 'table' && <>
      <h3>{card.title}</h3>
      <div className="table-scroll"><table><thead><tr>{card.headers.map(header => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{card.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{typeof cell === 'string' ? cell : money(cell.money, business)}</td>)}</tr>)}</tbody></table></div>
    </>}
    {card.kind === 'finance' && <>
      <h3>{card.title}</h3><p className="muted">{card.start} through {card.end}{card.comparison && <> · Compared with {card.comparison}</>}</p>
      <div className="table-scroll"><table><thead><tr><th>Metric</th><th>Selected period</th>{card.comparison && <th>Comparison</th>}</tr></thead>
        <tbody>{card.metrics.map(row => <tr key={row.label}><td>{row.label}</td><td><strong>{money(row.value, business)}</strong></td>
          {card.comparison && <td>{row.comparison === null ? '—' : money(row.comparison, business)}</td>}</tr>)}</tbody></table></div>
      {card.observations?.map(item => <p className="muted" key={item}>{item}</p>)}
      <Trend series={card.series} />
    </>}
    {card.kind === 'insights' && <><h3>Workspace observations</h3><ul className="insight-list">{card.items.map(item => <li key={item}>{item}</li>)}</ul></>}
    <Link className="assistant-source" to={card.link}>Open source records <ArrowUpRight size={15} /></Link>
  </section>
}

function EditProposal({ proposal, business, save }: { proposal: Proposal; business: Business; save: (payload: object) => Promise<void> }) {
  const p = proposal.payload
  const details = proposal.preview
  const selected = (id: unknown, name: string): Category | undefined => id ? { id: Number(id), name } : undefined
  const discount = typeof p.discount === 'object' ? p.discount : null
  const today = todayIn(business.timezone)
  return <Form label="Update preview" submit={async form => {
    const data = Object.fromEntries(form)
    if (proposal.kind === 'sale') {
      await save({ product: Number(data.product), quantity: data.quantity, method: data.method, customer: Number(data.customer) || null,
        notes: data.notes, discount: { kind: data.discount_kind, value: data.discount_value } })
    } else if (proposal.kind === 'purchase') {
      await save({ ...data, product: Number(data.product), supplier: Number(data.supplier) })
    } else if (proposal.kind === 'expense') {
      await save({ ...data, category: Number(data.category) })
    } else {
      await save({ ...data, product: Number(data.product) })
    }
  }}>
    {proposal.kind !== 'expense' && <>
      <Lookup<Category> path={tenant(business, proposal.kind === 'sale' ? 'products/' : 'products/?tracked=1')}
        name="product" label="Product" initial={selected(p.product, details.product)} required />
      <label>Quantity<input name="quantity" type="number" min=".001" step=".001" defaultValue={String(p.quantity)} required /></label>
    </>}
    {proposal.kind === 'purchase' && <>
      <Lookup<Category> path={tenant(business, 'suppliers/?active=1')} name="supplier" label="Supplier" initial={selected(p.supplier, details.supplier)} required />
      <div className="field-grid">
        <label>Unit cost<input name="unit_cost" type="number" min="0" step=".0001" defaultValue={String(p.unit_cost)} required /></label>
        <label>Received on<input name="received_on" type="date" max={today} defaultValue={String(p.received_on)} required /></label>
      </div>
      <label>Reference<input name="reference" maxLength={80} defaultValue={String(p.reference ?? '')} /></label>
    </>}
    {proposal.kind === 'expense' && <>
      <Lookup<Category> path={tenant(business, 'expense-categories/')} name="category" label="Expense category" initial={selected(p.category, details.category)} required />
      <div className="field-grid">
        <label>Amount<input name="amount" type="number" min=".01" step=".01" defaultValue={String(p.amount)} required /></label>
        <label>Expense date<input name="incurred_on" type="date" max={today} defaultValue={String(p.incurred_on)} required /></label>
      </div>
      <label>Description<textarea name="description" maxLength={500} defaultValue={String(p.description)} required /></label>
    </>}
    {proposal.kind === 'opening' && <label>Opening unit cost<input name="unit_cost" type="number" min="0" step=".0001" defaultValue={String(p.unit_cost)} required /></label>}
    {proposal.kind === 'adjustment' && <label>Reason<textarea name="reason" maxLength={500} defaultValue={String(p.reason)} required /></label>}
    {(proposal.kind === 'sale' || proposal.kind === 'expense') && <label>Payment method<select name="method" defaultValue={String(p.method)}>
      {Object.entries(proposal.kind === 'sale' ? paymentLabels : methods).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>}
    {proposal.kind === 'sale' && <>
      <Lookup<Category> path={tenant(business, 'customers/?active=1')} name="customer" label="Customer" initial={selected(p.customer, details.customer)} />
      <div className="field-grid">
        <label>Discount type<select name="discount_kind" defaultValue={discount?.kind}><option value="fixed">Fixed amount</option><option value="percent">Percentage</option></select></label>
        <label>Discount value<input name="discount_value" type="number" min="0" step=".01" defaultValue={discount?.value ?? '0'} required /></label>
      </div>
      <label>Notes<textarea name="notes" maxLength={1000} defaultValue={String(p.notes ?? '')} /></label>
    </>}
  </Form>
}

export function ProposalCard({ proposal, business, update }: { proposal: Proposal; business: Business; update: (value?: Proposal) => void }) {
  const [busy, setBusy] = useState(false)
  const [editing, edit] = useState(false)
  const [error, setError] = useState('')
  async function action(operation: string, payload?: object) {
    if (busy) return
    setBusy(true); setError('')
    try {
      const result = await api<{ proposal: Proposal }>(tenant(business, 'assistant/proposals/' + proposal.id + '/' + operation + '/'), 'POST',
        { revision: proposal.revision, ...(payload ? { payload } : {}) })
      update(result.proposal)
    } catch (problem) {
      update()
      throw problem
    } finally { setBusy(false) }
  }
  async function finish(operation: 'confirm' | 'cancel') {
    try { await action(operation) }
    catch (problem) { setError((problem as Error).message) }
  }
  const currency = { ...business, currency: proposal.preview.currency }
  const kind = kinds[proposal.kind]
  return <section className="assistant-card proposal-card" aria-label={kind + ' preview'}>
    <header><div><span className="eyebrow">Transaction review</span><h3>{kind} preview</h3></div>
      <span className={'pill capitalize proposal-' + proposal.status}>{proposal.status}</span></header>
    <dl className="proposal-fields">
      {Object.entries(labels).map(([key, label]) => proposal.preview[key] && <div key={key}><dt>{label}</dt>
        <dd>{moneyFields.has(key) ? money(proposal.preview[key], currency, key === 'unit_cost' ? 4 : 2)
          : key === 'method' ? paymentLabels[proposal.preview[key]] : key === 'quantity' ? quantity(proposal.preview[key]) : proposal.preview[key]}</dd></div>)}
      <div className="proposal-total"><dt>{proposal.kind === 'opening' || proposal.kind === 'adjustment' ? 'Inventory value added' : 'Total'}</dt><dd>{money(proposal.preview.total, currency)}</dd></div>
    </dl>
    {proposal.status === 'pending' && <><p className="muted">Posts only after confirmation. Expires at <time dateTime={proposal.expires_at}>
      {new Intl.DateTimeFormat('en-NG', { hour: 'numeric', minute: '2-digit', timeZone: business.timezone }).format(new Date(proposal.expires_at))}
    </time> workspace time.</p>
      <div className="actions"><button className="primary confirm-proposal" disabled={busy} onClick={() => finish('confirm')}><Check size={17} /> Confirm {kind.toLowerCase()}</button>
        <button className="secondary" disabled={busy} onClick={() => edit(true)}>Edit preview</button><button className="secondary" disabled={busy} onClick={() => finish('cancel')}><X size={16} /> Cancel</button></div></>}
    {proposal.status === 'confirmed' && <div className="notice" role="status"><Check size={16} /> {kind} #{proposal.result.id} recorded.
      {proposal.result.stock && <> On hand {quantity(proposal.result.stock)}.</>} {proposal.result.link && <Link to={proposal.result.link}>View transaction</Link>}</div>}
    {proposal.status === 'cancelled' && <p className="muted">Proposal cancelled.</p>}
    {proposal.status === 'expired' && <p className="muted">This preview expired. Send a new request for a fresh preview.</p>}
    {proposal.status === 'failed' && <p role="alert" className="notice error">{formatFailure(proposal.result.error)}</p>}
    {error && proposal.status !== 'failed' && <p role="alert" className="notice error">{error}</p>}
    {editing && <Dialog title={'Edit ' + kind.toLowerCase() + ' preview'} close={() => edit(false)}>
      <EditProposal proposal={proposal} business={business} save={async payload => { await action('edit', payload); edit(false) }} />
    </Dialog>}
  </section>
}

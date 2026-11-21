import { Printer, ReceiptText, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, editable, money, quantity, tenant, useData } from './api'
import type { Business, Page } from './api'
import { canSell, methods, minor, shortDate } from './finance'
import type { ReturnRecord, Sale } from './finance'
import { Dialog, Empty, Form, Heading, Pager, Result } from './ui'

export function SaleReceipt({ sale, business }: { sale: Sale; business: Business }) {
  return <div className="receipt-print">
    <div className="receipt-meta"><div><h2>{business.name}</h2>{business.address && <p>{business.address}</p>}<p>Receipt #{sale.id} · {sale.posted_at ? shortDate(sale.posted_at, business.timezone) : 'Draft'}</p><p>{sale.customer_name || 'Walk-in customer'}</p></div>
      <button className="secondary no-print" onClick={() => window.print()}><Printer size={17} /> Print receipt</button></div>
    <div className="table-scroll"><table><thead><tr><th>Product</th><th>Qty</th><th>Unit price</th><th>Total</th></tr></thead>
      <tbody>{sale.lines.map(line => <tr key={line.id}><td>{line.name}{Number(line.returned_quantity) > 0 && <small>{quantity(line.returned_quantity)} returned</small>}</td><td>{quantity(line.quantity)}</td><td>{money(line.price, business)}</td><td>{money(line.total, business)}</td></tr>)}</tbody></table></div>
    <dl className="sale-totals">
      {([['Subtotal', sale.subtotal], ['Discount', sale.discount], ['Tax', sale.tax], ['Total', sale.total], ['Returns', sale.returned], ['Net paid', sale.paid], ['Outstanding balance', sale.balance]]).map(([label, amount]) =>
        <div key={label}><dt>{label}</dt><dd>{money(amount, business)}</dd></div>)}
    </dl>
    {sale.payments.length > 0 && <div className="receipt-notes"><strong>Payments received</strong><ul>{sale.payments.map(payment => <li key={payment.id}>{methods[payment.method]} · {money(payment.amount, business)}</li>)}</ul></div>}
    {sale.returns.length > 0 && <div className="receipt-notes"><strong>Reversals</strong><ul>{sale.returns.map(item => <li key={item.id}>#{item.id} · {item.void ? 'Void' : 'Return'} · {money(item.total, business)} · {money(item.refund, business)} refunded{item.refund_method ? ` via ${methods[item.refund_method]}` : ''} · {item.reason}</li>)}</ul></div>}
    {sale.notes && <p>{sale.notes}</p>}{business.receipt_footer && <p className="muted">{business.receipt_footer}</p>}
  </div>
}

type ReturnQuote = { total: string; refund: string; receivable_reduction: string }
type Reversal = { request_id: string; reason: string; expected_refund: string; refund_method: string; lines?: { sale_line: number; quantity: string; restocked: boolean }[] }

function ReversalForm({ sale, business, voidSale, done }: { sale: Sale; business: Business; voidSale: boolean; done: () => void }) {
  const [key] = useState(() => crypto.randomUUID())
  const [review, setReview] = useState<{ quote: ReturnQuote; payload: Reversal }>()
  const lines = sale.lines.filter(line => Number(line.quantity) > Number(line.returned_quantity))
  const resource = voidSale ? 'void' : 'return'
  const path = tenant(business, `sales/${sale.id}/`)
  if (review) return <Form label={voidSale ? 'Confirm void' : 'Confirm return'} danger={voidSale} submit={async form => {
    await api(path + resource + '/', 'POST', { ...review.payload, expected_refund: review.quote.refund, refund_method: form.get('refund_method') || '' })
    done()
  }}>
    <p>{review.payload.reason}</p>
    <dl className="sale-totals">
      <div><dt>Sale reduction</dt><dd>{money(review.quote.total, business)}</dd></div>
      <div><dt>Balance reduction</dt><dd>{money(review.quote.receivable_reduction, business)}</dd></div>
      <div><dt>Refund to record</dt><dd>{money(review.quote.refund, business)}</dd></div>
    </dl>
    {minor(review.quote.refund) > 0n && <label>Refund method<select name="refund_method" required defaultValue=""><option value="" disabled>Choose the refund tender</option>{Object.entries(methods).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}
    <button type="button" className="secondary" onClick={() => setReview(undefined)}>Revise return</button>
  </Form>
  return <Form label={voidSale ? 'Review void' : 'Review return'} submit={async form => {
    const payload: Reversal = { request_id: key, reason: String(form.get('reason')), expected_refund: '0', refund_method: '' }
    if (!voidSale) payload.lines = lines.flatMap(line => {
      const value = String(form.get(`qty-${line.id}`) || '0')
      return Number(value) > 0 ? [{ sale_line: line.id, quantity: value, restocked: form.has(`restock-${line.id}`) }] : []
    })
    const quote = await api<ReturnQuote>(path + resource + '-quote/', 'POST', payload)
    setReview({ quote, payload })
  }}>
    <p>{voidSale ? 'Voiding reverses remaining sale quantities and restocks tracked items.' : 'Enter a quantity for each item you want to return. Set restock only for items going back into inventory.'}</p>
    {!voidSale && lines.map(line => {
      const max = (Number(line.quantity) - Number(line.returned_quantity)).toFixed(3)
      return <div className="receipt-line" key={line.id}>
        <strong>{line.name}</strong>
        <label>Return quantity for {line.name}<input name={`qty-${line.id}`} type="number" min="0" max={max} step={['kg', 'litre'].includes(line.unit) ? '.001' : '1'} placeholder={`Up to ${quantity(max)}`} /></label>
        {line.tracked && <label className="check"><input type="checkbox" name={`restock-${line.id}`} defaultChecked /> Restock {line.name}</label>}
      </div>
    })}
    <label>Reason<textarea name="reason" maxLength={500} required /></label>
  </Form>
}

function SaleDetails({ id, business, close, refresh }: { id: string; business: Business; close: () => void; refresh: () => void }) {
  const result = useData<Sale>(tenant(business, `sales/${id}/`))
  const [mode, setMode] = useState<'receipt' | 'payment' | 'return' | 'void'>('receipt')
  const [paymentKey, setPaymentKey] = useState(() => crypto.randomUUID())
  const [notice, setNotice] = useState('')
  const sale = result.data
  function done(message: string) {
    setMode('receipt'); setNotice(message); result.refresh(); refresh()
  }
  return <Dialog title={mode === 'receipt' ? `Sale #${id}` : mode === 'payment' ? 'Record payment' : mode === 'void' ? 'Void sale' : 'Return sale items'} close={close}>
    <Result {...result} retry={result.refresh}>
      {notice && <p className="notice" role="status">{notice}</p>}
      {sale && (mode === 'receipt' ? <>
        <div className="sale-detail-actions actions">
          <span className="pill capitalize">{sale.status}</span>
          {sale.status === 'draft' && canSell(business.role) && <Link className="primary" to="/pos" state={{ draft: sale.draft }}>Resume draft</Link>}
          {sale.status === 'completed' && minor(sale.balance) > 0n && canSell(business.role) && <button className="secondary" onClick={() => { setPaymentKey(crypto.randomUUID()); setMode('payment') }}>Record payment</button>}
          {editable(business) && sale.status === 'completed' && sale.lines.some(line => Number(line.quantity) > Number(line.returned_quantity)) && <button className="secondary" onClick={() => setMode('return')}><RotateCcw size={15} /> Return items</button>}
          {editable(business) && sale.status !== 'voided' && <button className="secondary" onClick={() => setMode('void')}>Void sale</button>}
        </div>
        {sale.posted_at ? <SaleReceipt sale={sale} business={business} /> : <p>Draft with {sale.draft.lines?.length ?? 0} products. Stock has not been reserved.</p>}
      </> : mode === 'payment' ? <Form label="Save payment" submit={async form => {
        await api(tenant(business, `sales/${id}/record-payment/`), 'POST', { ...Object.fromEntries(form), request_id: paymentKey })
        done('Payment recorded.')
      }}>
        <p>Current balance <strong>{money(sale.balance, business)}</strong></p>
        <label>Amount<input type="number" name="amount" step=".01" min=".01" max={sale.balance} defaultValue={sale.balance} required /></label>
        <label>Payment method<select name="method">{Object.entries(methods).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <button type="button" className="secondary" onClick={() => setMode('receipt')}>Back to sale</button>
      </Form> : <>
        <button type="button" className="secondary sale-detail-actions" onClick={() => setMode('receipt')}>Back to sale</button>
        <ReversalForm sale={sale} business={business} voidSale={mode === 'void'} done={() => done(mode === 'void' ? 'Sale voided.' : 'Return recorded.')} />
      </>)}
    </Result>
  </Dialog>
}

export function SalesHistory({ business }: { business: Business }) {
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const customer = params.get('customer') ?? ''
  const detail = params.get('sale')
  const result = useData<Page<Sale>>(tenant(business, `sales/?${new URLSearchParams({ page: String(page), search, status: state, customer })}`))
  function select(id?: number) {
    const next = new URLSearchParams(params)
    if (id) next.set('sale', String(id)); else next.delete('sale')
    setParams(next)
  }
  return <>
    <Heading label="Sales counter" title="Sales history" subtitle={customer ? 'Review transactions for the selected customer.' : 'Find receipts, resume drafts, and review payments and reversals.'}>
      {customer && <button className="secondary" onClick={() => { setPage(1); setParams({}) }}>Clear customer filter</button>}
      <Link className="primary" to="/pos"><ReceiptText size={17} /> Open point of sale</Link>
    </Heading>
    <section className="panel">
      <div className="toolbar"><input type="search" aria-label="Search sales" placeholder="Search customer name or notes" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} />
        <select aria-label="Sale status" value={state} onChange={event => { setState(event.target.value); setPage(1) }}><option value="">All states</option><option value="draft">Draft</option><option value="completed">Completed</option><option value="voided">Voided</option></select></div>
      <Result {...result} retry={result.refresh}>
        {result.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Sale</th><th>Customer</th><th>Status</th><th>Total</th><th>Outstanding</th><th>Details</th></tr></thead>
          <tbody>{result.data.results.map(sale => <tr key={sale.id}><td><strong>#{sale.id}</strong><small>{shortDate(sale.posted_at || sale.created_at, business.timezone)}</small></td><td>{sale.customer_name || 'Walk-in'}</td><td><span className="pill capitalize">{sale.status}</span></td><td>{sale.posted_at ? money(sale.total, business) : '—'}</td><td>{sale.posted_at ? money(sale.balance, business) : '—'}</td><td><button className="secondary" onClick={() => select(sale.id)}>View sale #{sale.id}</button></td></tr>)}</tbody></table></div> : <Empty title="No sales found" text="Posted sales and saved drafts will appear here." />}
        <Pager page={page} setPage={setPage} data={result.data} />
      </Result>
    </section>
    {detail && /^\d+$/.test(detail) && <SaleDetails key={detail} id={detail} business={business} close={() => select()} refresh={result.refresh} />}
  </>
}

export function Returns({ business }: { business: Business }) {
  const [page, setPage] = useState(1)
  const result = useData<Page<ReturnRecord>>(tenant(business, `returns/?page=${page}`))
  return <>
    <Heading label="Sales adjustments" title="Returns" subtitle="Review refunds, restocks and voided sales."><Link className="primary" to="/sales">Find original sale</Link></Heading>
    <section className="panel"><Result {...result} retry={result.refresh}>
      {result.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Reversal</th><th>Original sale</th><th>Reason</th><th>Sale reduction</th><th>Refund</th><th>Restocked items</th></tr></thead>
        <tbody>{result.data.results.map(item => <tr key={item.id}><td><strong>{item.void ? 'Void' : 'Return'} #{item.id}</strong><small>{shortDate(item.created_at, business.timezone)}</small></td><td><Link to={`/sales?sale=${item.sale}`}>Sale #{item.sale}</Link></td><td>{item.reason}</td><td>{money(item.total, business)}</td><td>{money(item.refund, business)}<small>{item.refund_method && methods[item.refund_method]}</small></td><td>{item.lines.filter(line => line.restocked).map(line => `${quantity(line.quantity)} × ${line.name}`).join(', ') || '—'}</td></tr>)}</tbody></table></div> : <Empty title="No reversals recorded" text="Open the original sale to review a return or void." />}
      <Pager page={page} setPage={setPage} data={result.data} />
    </Result></section>
  </>
}

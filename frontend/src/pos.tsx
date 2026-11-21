import { BadgePercent, CreditCard, Package, Plus, Search, ShoppingCart, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, money, quantity, tenant, useData } from './api'
import type { Business, Category, Page, Product } from './api'
import { Lookup } from './catalog'
import { canSell, decimal, methods, minor, zeroDiscount } from './finance'
import type { Customer, Discount, Draft, Method, Payment, Quote, Sale, SaleItem, Totals } from './finance'
import { SaleReceipt } from './sales-history'
import { Dialog, Empty, Form, Heading, Pager, Result } from './ui'

function productImage(product: Product) {
  return product.image_url
}

function DiscountFields({ value, change, label }: { value: Discount; change: (value: Discount) => void; label: string }) {
  return <div className="discount-fields">
    <label>{label} type<select value={value.kind} onChange={event => change({ kind: event.target.value as Discount['kind'], value: value.value })}><option value="fixed">Fixed amount</option><option value="percent">Percentage</option></select></label>
    <label>{label} value<input type="number" min="0" max={value.kind === 'percent' ? 100 : undefined} step=".01" value={value.value} onChange={event => change({ ...value, value: event.target.value })} /></label>
  </div>
}

export function SaleTotals({ value, business }: { value: Totals; business: Business }) {
  return <dl className="sale-totals"><div><dt>Subtotal</dt><dd>{money(value.subtotal, business)}</dd></div>
    <div><dt>Discount</dt><dd>{money(value.discount, business)}</dd></div>
    <div><dt>Tax</dt><dd>{money(value.tax, business)}</dd></div>
    <div><dt>Total</dt><dd>{money(value.total, business)}</dd></div></dl>
}

function Checkout({ business, draft, total, done }: { business: Business; draft: Draft; total: Quote; done: (sale?: Sale) => void }) {
  const [payments, setPayments] = useState<Payment[]>(draft.payments.length ? draft.payments : minor(total.total) > 0n ? [{ method: 'cash', amount: total.total }] : [])
  const [credit, setCredit] = useState(draft.payments.length === 0 && minor(total.total) === 0n)
  const [selected] = useState(draft.customer)
  const initial = useData<Customer>(tenant(business, selected ? `customers/${selected}/` : 'customers/?active=1'))
  const [error, setError] = useState('')
  const paid = payments.reduce((sum, payment) => sum + minor(payment.amount), 0n)
  const remaining = minor(total.total) - paid
  function changePayment(index: number, payment: Payment) {
    setPayments(items => items.map((value, position) => position === index ? payment : value))
  }
  async function submit(form: FormData) {
    const customer = Number(form.get('customer')) || null
    const sale = await api<Sale>(tenant(business, 'sales/checkout/'), 'POST', { ...draft, customer, payments, notes: form.get('notes'), expected_total: total.total })
    done(sale)
  }
  return <Result data={selected ? initial.data : true} error={selected ? initial.error : undefined} retry={initial.refresh}>
    <SaleTotals value={total} business={business} />
    <Form label="Post sale" submit={submit}>
      <Lookup<Customer> path={tenant(business, 'customers/?active=1')} name="customer" label="Customer" initial={selected ? initial.data : undefined} required={remaining > 0n} />
      <p className="muted">{remaining > 0n ? 'A registered customer is required for the unpaid balance.' : 'Leave customer blank for a walk-in sale.'}</p>
      <label>Sales notes<textarea name="notes" maxLength={1000} defaultValue={draft.notes} /></label>
      <div className="receipt-line">
        <div className="line-head"><strong>Payment breakdown</strong><CreditCard size={18} /></div>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => { setPayments(minor(total.total) ? [{ method: 'cash', amount: total.total }] : []); setCredit(false); setError('') }}>Pay in full</button>
          <button type="button" className="secondary" onClick={() => { setPayments([]); setCredit(true); setError('') }}>Pay on credit</button>
        </div>
        {payments.map((payment, index) => <div className="payment-row" key={index}>
          <label>Payment method {index + 1}<select value={payment.method} onChange={event => changePayment(index, { ...payment, method: event.target.value as Method })}>{Object.entries(methods).map(([value, text]) => <option value={value} key={value}>{text}</option>)}</select></label>
          <label>Payment amount {index + 1}<input type="number" required min=".01" step=".01" value={payment.amount} onChange={event => changePayment(index, { ...payment, amount: event.target.value })} /></label>
          <button type="button" className="icon-btn" aria-label={`Remove payment ${index + 1}`} onClick={() => setPayments(items => items.filter((_, position) => position !== index))}><Trash2 size={16} /></button>
        </div>)}
        {payments.length < 10 && <button type="button" className="secondary" onClick={() => {
          if (remaining <= 0n) { setError('Reduce an existing payment amount before splitting.'); return }
          setError(''); setCredit(false); setPayments([...payments, { method: 'transfer', amount: decimal(remaining) }])
        }}>Add split payment</button>}
        {error && <p role="alert">{error}</p>}
        <p><strong>{credit ? 'Credit balance' : 'Outstanding'}</strong> {money(decimal(remaining), business)}</p>
        <small>Card and transfer selections record the tender received.</small>
      </div>
    </Form>
  </Result>
}

const emptyDraft = (): Draft => ({ request_id: crypto.randomUUID(), customer: null, notes: '', payments: [], lines: [], discount: zeroDiscount })

export function Pos({ business }: { business: Business }) {
  const location = useLocation()
  const [draft, setDraft] = useState<Draft>(() => location.state?.draft ?? emptyDraft())
  const [catalog, setCatalog] = useState<Record<number, Product>>({})
  const searchInput = useRef<HTMLInputElement>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(1)
  const [quote, setQuote] = useState<{ key: string; data?: Quote; error?: string }>()
  const [quoteRevision, refreshQuote] = useState(0)
  const [checkout, setCheckout] = useState(false)
  const [receipt, setReceipt] = useState<Sale>()
  const [notice, setNotice] = useState('')
  const [draftDialog, setDraftDialog] = useState(false)
  const params = new URLSearchParams({ page: String(page), search })
  if (category) params.set('category', category)
  const products = useData<Page<Product>>(tenant(business, `products/?${params}`))
  const quotePath = tenant(business, 'sales/quote/')
  const quoteKey = JSON.stringify({ lines: draft.lines, discount: draft.discount })
  const currentQuote = quote?.key === quoteKey ? quote.data : undefined
  const quoteError = quote?.key === quoteKey ? quote.error : undefined
  const allowed = canSell(business.role)
  const lineCount = draft.lines.length

  useEffect(() => {
    if (!allowed || !lineCount) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api<Quote>(quotePath, 'POST', JSON.parse(quoteKey), controller.signal).then(
        data => { if (!controller.signal.aborted) setQuote({ key: quoteKey, data }) },
        error => { if (!controller.signal.aborted) setQuote({ key: quoteKey, error: error.message }) },
      )
    }, 180)
    return () => { clearTimeout(timer); controller.abort() }
  }, [allowed, lineCount, quoteKey, quotePath, quoteRevision])

  useEffect(() => {
    if (!location.state?.draft) return
    const controller = new AbortController()
    const original = location.state.draft as Draft
    for (const item of original.lines) {
      api<Product>(tenant(business, `products/${item.product}/`), 'GET', undefined, controller.signal).then(
        product => { if (!controller.signal.aborted) setCatalog(items => ({ ...items, [product.id]: product })) },
        () => {},
      )
    }
    return () => controller.abort()
  }, [business.id, location.state])

  function editLine(product: number, patch: Partial<SaleItem>) {
    setDraft(value => ({ ...value, lines: value.lines.map(line => line.product === product ? { ...line, ...patch } : line) }))
  }
  function step(value: string, direction: number, fractional: boolean) {
    const increment = fractional ? .001 : 1
    return String(Math.max(increment, Number((Number(value || 0) + increment * direction).toFixed(3))))
  }
  function add(product: Product) {
    setNotice('')
    setCatalog(value => ({ ...value, [product.id]: product }))
    setDraft(value => {
      const found = value.lines.find(line => line.product === product.id)
      return { ...value, lines: found
        ? value.lines.map(line => line === found ? { ...line, quantity: step(line.quantity, 1, false) } : line)
        : [...value.lines, { product: product.id, quantity: '1', discount: zeroDiscount }] }
    })
  }
  function complete(sale?: Sale) {
    setCheckout(false)
    if (!sale) return
    setReceipt(sale); setDraft(emptyDraft()); setQuote(undefined); products.refresh()
  }

  return <>
    <Heading label="Sales counter" title="Point of sale" subtitle="Build a cart, review discounts and record payment.">
      {lineCount > 0 && <a className="secondary mobile-cart" href="#current-sale"><ShoppingCart size={17} /> View cart ({lineCount})</a>}
      <Link className="secondary" to="/sales">Sales history</Link>
    </Heading>
    {notice && <div className="notice" role="status">{notice}</div>}
    <div className="pos-layout">
      <section className="panel pos-catalog">
        <div className="toolbar"><div className="search"><Search size={17} /><input ref={searchInput} aria-label="Search POS products" aria-describedby="pos-search-hint" type="search" placeholder="Scan barcode or search product or SKU" value={search} onChange={event => { setPage(1); setSearch(event.target.value) }} onKeyDown={event => {
          if (event.key === 'Enter' && search && allowed) {
            const exact = products.data?.results.find(product => product.barcode === search || product.sku.toLowerCase() === search.toLowerCase())
            if (exact && (!exact.track_stock || Number(exact.stock) > 0)) { add(exact); setSearch(''); setPage(1) }
          }
        }} /></div>
          <div>
            <Lookup<Category> path={tenant(business, 'categories/')} name="pos-category" label="Category" emptyLabel="All categories" onSelect={value => { setCategory(value); setPage(1) }} />
          </div>
        </div>
        <p id="pos-search-hint" className="pos-search-hint muted">Use Enter to add an exact barcode or SKU.</p>
        <Result {...products} retry={products.refresh}>
          {products.data?.results.length ? <div className="product-grid">{products.data.results.map(product => <article className="product-tile" key={product.id}>
            <div className="product-art"><Package size={30} aria-hidden="true" />{productImage(product) && <img src={productImage(product)} alt="" loading="lazy" referrerPolicy="no-referrer" onError={event => { event.currentTarget.hidden = true }} />}</div>
            {product.track_stock && Number(product.stock) <= Number(product.reorder_level) && <span className="pos-stock-tag">{Number(product.stock) === 0 ? "Out of stock" : "Low stock"}</span>}
            <div className="product-copy"><strong>{product.name}</strong><small>{product.sku} · {product.unit}</small><b>{money(product.price, business)}</b></div>
            <div className="product-bottom"><small className={product.track_stock && Number(product.stock) === 0 ? 'negative' : 'positive'}>{product.track_stock ? `${quantity(product.stock)} available` : 'Untracked'}</small>
              {allowed && <button className="icon-btn add-item" aria-label={`Add ${product.name}`} disabled={product.track_stock && Number(product.stock) === 0} onClick={() => add(product)}><Plus size={18} /></button>}</div>
          </article>)}</div> : <Empty title="No matching products" text="Try another search or add products to the catalog." />}
          <Pager page={page} setPage={setPage} data={products.data} />
        </Result>
      </section>
      <section className="panel cart" id="current-sale" aria-label="Current sale">
        <div className="panel-head"><div><h2>Current sale</h2><p>{lineCount} {lineCount === 1 ? 'product' : 'products'} in cart</p></div><ShoppingCart size={21} /></div>
        {!allowed ? <Empty title="Read-only access" text="An owner, manager or cashier can post sales." /> : !lineCount ? <Empty title="Your cart is empty" text="Add an available product to start a sale." /> :
          <div className="cart-content">
            {draft.lines.map(line => {
              const product = catalog[line.product]
              const fractional = product?.unit === 'kg' || product?.unit === 'litre'
              const label = product?.name ?? `Product #${line.product}`
              const quoted = currentQuote?.lines.find(item => item.product === line.product)
              return <article className="cart-line" key={line.product}>
                <div className="line-head"><div className="cart-product">{product && productImage(product) && <img src={productImage(product)} alt="" referrerPolicy="no-referrer" onError={event => { event.currentTarget.hidden = true }} />}<strong>{label}</strong></div><button className="icon-btn" aria-label={`Remove ${label}`} onClick={() => setDraft(value => ({ ...value, lines: value.lines.filter(item => item.product !== line.product) }))}><Trash2 size={15} /></button></div>
                <div className="line-head"><div className="stepper"><button className="icon-btn" aria-label={`Decrease ${label}`} onClick={() => editLine(line.product, { quantity: step(line.quantity, -1, fractional) })}>−</button>
                  <input type="number" min={fractional ? '.001' : '1'} step={fractional ? '.001' : '1'} aria-label={`Quantity for ${label}`} value={line.quantity} onChange={event => editLine(line.product, { quantity: event.target.value })} />
                  <button className="icon-btn" aria-label={`Increase ${label}`} onClick={() => editLine(line.product, { quantity: step(line.quantity, 1, fractional) })}>+</button></div>
                  {quoted && <strong>{money(quoted.total, business)}</strong>}</div>
                <details><summary>Item discount</summary><DiscountFields label={`Discount for ${label}`} value={line.discount} change={discount => editLine(line.product, { discount })} /></details>
              </article>
            })}
            <details className="invoice-discount"><summary><BadgePercent size={16} /> Invoice discount</summary>
              <DiscountFields label="Invoice discount" value={draft.discount} change={discount => setDraft(value => ({ ...value, discount }))} /></details>
            {quoteError ? <div className="notice error" role="alert">{quoteError} <button className="secondary" onClick={() => { setQuote(undefined); refreshQuote(value => value + 1) }}>Refresh quote</button></div> : currentQuote ? <SaleTotals value={currentQuote} business={business} /> : <p className="muted" role="status">Calculating total…</p>}
            <div className="actions cart-actions"><button className="primary" disabled={!currentQuote} onClick={() => setCheckout(true)}>Review checkout</button>
              <button className="secondary" onClick={() => setDraftDialog(true)}>Save draft</button></div>
          </div>}
      </section>
    </div>
    {checkout && currentQuote && <Dialog title="Review checkout" close={() => { setCheckout(false); setQuote(undefined); refreshQuote(value => value + 1) }}><Checkout business={business} draft={draft} total={currentQuote} done={complete} /></Dialog>}
    {draftDialog && <Dialog title="Save sale draft" close={() => setDraftDialog(false)}>
      <Form label="Save draft" submit={async form => {
        const next = { ...draft, notes: String(form.get('notes')) }
        await api(tenant(business, 'sales/draft/'), 'POST', next)
        setDraft(next); setNotice('Draft saved. Resume it from Sales history.'); setDraftDialog(false)
      }}>
        <p>Drafts leave stock and payments unchanged.</p>
        <label>Draft notes<textarea name="notes" maxLength={1000} defaultValue={draft.notes} /></label>
      </Form>
    </Dialog>}
    {receipt && <Dialog title={`Receipt #${receipt.id}`} close={() => { setReceipt(undefined); requestAnimationFrame(() => searchInput.current?.focus()) }}><SaleReceipt business={business} sale={receipt} /></Dialog>}
  </>
}

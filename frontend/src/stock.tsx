import { ClipboardPlus, Plus, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, editable, money, quantity, tenant, useData } from './api'
import type { Business, Movement, Page, Product, Receipt, Supplier } from './api'
import { Lookup } from './catalog'
import { Dialog, Empty, Form, Heading, Pager, Result } from './ui'

export function MovementsTable({ movements, business }: { movements: Movement[]; business: Business }) {
  const time = new Intl.DateTimeFormat('en-NG', { timeZone: business.timezone, dateStyle: 'medium', timeStyle: 'short' })
  const labels: Record<string, string> = { opening: 'Opening stock', purchase: 'Purchase receipt', sale: 'Sale', return: 'Sale return', void: 'Sale void', adjustment: 'Stock adjustment' }
  return <div className="table-scroll"><table><thead><tr><th>Product</th><th>Movement</th><th>Quantity</th><th>Balance</th><th>Recorded</th></tr></thead>
    <tbody>{movements.map(item => <tr key={item.id}><td><strong>{item.product_name}</strong></td><td><span className="pill">{labels[item.kind] ?? item.kind}</span></td><td className={item.quantity.startsWith('-') ? 'negative' : 'positive'}>{item.quantity.startsWith('-') ? '' : '+'}{quantity(item.quantity)}</td><td>{quantity(item.balance)}</td><td>{time.format(new Date(item.created_at))}</td></tr>)}</tbody></table></div>
}

function StockFields({ business, suffix = '' }: { business: Business; suffix?: string }) {
  return <>
    <Lookup<Product> label={suffix ? `Product ${suffix}` : 'Product'} name={`product${suffix}`} required path={tenant(business, 'products/?tracked=1')} optionLabel={product => `${product.name} · ${product.sku} · ${product.unit}`} />
    <div className="field-grid">
      <label>Quantity<input name={`quantity${suffix}`} type="number" min=".001" step=".001" required /></label>
      <label>Unit cost ({business.currency})<input name={`unit_cost${suffix}`} type="number" min="0" step=".0001" required /></label>
    </div>
  </>
}

function stockLine(form: FormData, suffix = '') {
  return { product: Number(form.get(`product${suffix}`)), quantity: form.get(`quantity${suffix}`), unit_cost: form.get(`unit_cost${suffix}`) }
}

export function Inventory({ business }: { business: Business }) {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [logPage, setLogPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState('')
  const low = params.has('low')
  const stock = useData<Page<Product>>(tenant(business, `products/?tracked=1&low=${low ? 1 : 0}&page=${page}&search=${encodeURIComponent(search)}`))
  const log = useData<Page<Movement>>(tenant(business, `movements/?page=${logPage}`))
  return <>
    <Heading label="Stock control" title="Inventory" subtitle="Monitor balances, reorder levels and stock movements.">
      {editable(business) && <button className="primary" onClick={() => setOpen(true)}><Plus size={18} /> Opening stock</button>}
    </Heading>
    {status && <div className="notice" role="status">{status}</div>}
    <section className="panel">
      <div className="toolbar"><div className="search"><Search size={17} /><input type="search" aria-label="Search inventory" placeholder="Search inventory…" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} /></div>
        <label className="check"><input type="checkbox" checked={low} onChange={event => { setParams(event.target.checked ? { low: '1' } : {}); setPage(1) }} /> Low stock only</label></div>
      <Result {...stock} retry={stock.refresh}>
        {stock.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Product</th><th>On hand</th><th>Reorder at</th><th>Average cost</th><th>Stock health</th></tr></thead>
          <tbody>{stock.data.results.map(item => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.sku}</small></td><td>{quantity(item.stock)} {item.unit}</td><td>{quantity(item.reorder_level)}</td><td>{money(item.cost, business, 4)}</td><td><span className={`pill ${Number(item.stock) <= Number(item.reorder_level) ? 'warning' : ''}`}>{Number(item.stock) === 0 ? 'Out of stock' : Number(item.stock) <= Number(item.reorder_level) ? 'Low stock' : 'In stock'}</span></td></tr>)}</tbody></table></div> :
          <Empty title="No matching stock items" text={low ? 'No tracked products match the low-stock filter.' : 'Create stock-tracked products in the catalog to manage them here.'} />}
        <Pager page={page} setPage={setPage} data={stock.data} />
      </Result>
    </section>
    <section className="panel spaced"><div className="panel-head"><div><h2>Movement history</h2><p>Track stock receipts, sales and returns.</p></div></div>
      <Result {...log} retry={log.refresh}>
        {log.data?.results.length ? <MovementsTable movements={log.data.results} business={business} /> : <Empty title="No movements recorded" text="Opening stock and purchase receipts appear here." />}
        <Pager page={logPage} setPage={setLogPage} data={log.data} />
      </Result>
    </section>
    {open && <Dialog title="Record opening stock" close={() => setOpen(false)}>
      <Form label="Record opening stock" submit={async form => {
        await api(tenant(business, 'movements/'), 'POST', stockLine(form))
        setStatus('Opening stock recorded.'); setOpen(false); setLogPage(1); log.refresh(); stock.refresh()
      }}>
        <p>Enter stock already on hand before the first movement for this product.</p><StockFields business={business} />
      </Form>
    </Dialog>}
  </>
}

function ReceiptForm({ business, done }: { business: Business; done: () => void }) {
  const [lines, setLines] = useState([1])
  const [next, setNext] = useState(2)
  const [requestId] = useState(() => crypto.randomUUID())
  const today = new Intl.DateTimeFormat('sv-SE', { timeZone: business.timezone }).format(new Date())
  return <Form label="Post receipt" submit={async form => {
    await api(tenant(business, 'receipts/'), 'POST', {
      request_id: requestId, supplier: Number(form.get('supplier')), received_on: form.get('received_on'),
      reference: form.get('reference'), lines: lines.map(line => stockLine(form, String(line))),
    })
    done()
  }}>
    <p>Posting records the receipt and increases on-hand stock. Review the quantities and costs first.</p>
    <Lookup<Supplier> path={tenant(business, 'suppliers/?active=1')} name="supplier" label="Supplier" required />
    <div className="field-grid"><label>Receipt date<input name="received_on" type="date" defaultValue={today} max={today} required /></label><label>Supplier reference<input name="reference" maxLength={80} /></label></div>
    {lines.map((line, index) => <section className="receipt-line" key={line}><div className="line-head"><strong>Line {index + 1}</strong>{lines.length > 1 && <button type="button" className="icon-btn" aria-label={`Remove line ${index + 1}`} onClick={() => setLines(lines.filter(item => item !== line))}><Trash2 size={16} /></button>}</div><StockFields business={business} suffix={String(line)} /></section>)}
    {lines.length < 100 && <button type="button" className="secondary" onClick={() => { setLines([...lines, next]); setNext(next + 1) }}><Plus size={16} /> Add line</button>}
  </Form>
}

export function Purchases({ business }: { business: Business }) {
  const [params, setParams] = useSearchParams()
  const supplier = params.get('supplier') ?? ''
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<Receipt>()
  const [status, setStatus] = useState('')
  const receipts = useData<Page<Receipt>>(tenant(business, `receipts/?page=${page}&supplier=${encodeURIComponent(supplier)}`))
  return <>
    <Heading label="Procurement" title="Purchases" subtitle={supplier ? 'Review receipts for the selected supplier.' : 'Receive supplier stock and review posted receipts.'}>
      {supplier && <button className="secondary" onClick={() => { setPage(1); setParams({}) }}>Clear supplier filter</button>}
      {editable(business) && <><Link className="secondary" to="/suppliers">Suppliers</Link><button className="primary" onClick={() => setOpen(true)}><ClipboardPlus size={18} /> Receive purchase</button></>}
    </Heading>
    {status && <div className="notice" role="status">{status}</div>}
    <section className="panel">
      <Result {...receipts} retry={receipts.refresh}>
        {receipts.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Receipt</th><th>Supplier</th><th>Received</th><th>Lines</th><th>Details</th></tr></thead>
          <tbody>{receipts.data.results.map(item => <tr key={item.id}><td><strong>#{item.id}</strong><small>{item.reference}</small></td><td>{item.supplier_name}</td><td>{item.received_on}</td><td>{item.lines.length}</td><td><button className="secondary" onClick={() => setDetail(item)}>View receipt</button></td></tr>)}</tbody></table></div> :
          <Empty title="No purchases received" text="Add a supplier and receive a purchase to update stock and average cost." />}
        <Pager page={page} setPage={setPage} data={receipts.data} />
      </Result>
    </section>
    {open && <Dialog title="Receive a purchase" close={() => setOpen(false)}><ReceiptForm business={business} done={() => { setStatus('Purchase received. Stock balances updated.'); setOpen(false); setPage(1); receipts.refresh() }} /></Dialog>}
    {detail && <Dialog title={`Receipt #${detail.id}`} close={() => setDetail(undefined)}>
      <p>{detail.supplier_name} · {detail.received_on}{detail.reference && ` · ${detail.reference}`}</p>
      <div className="table-scroll"><table><thead><tr><th>Product</th><th>Received</th><th>Unit cost</th></tr></thead><tbody>{detail.lines.map(item => <tr key={item.product}><td>{item.product_name}</td><td>{quantity(item.quantity)}</td><td>{money(item.unit_cost, business, 4)}</td></tr>)}</tbody></table></div>
    </Dialog>}
  </>
}

import { Archive, FolderPlus, Pencil, Plus, Search } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, editable, money, quantity, tenant, useData } from './api'
import type { Business, Category, Page, Product, Supplier } from './api'
import { Dialog, Empty, Form, Heading, Pager, Result } from './ui'

export function Lookup<T extends { id: number; name: string }>({ path, label, name, initial, required, optionLabel, onSelect, emptyLabel }: {
  path: string; label: string; name: string; initial?: T; required?: boolean; optionLabel?: (item: T) => string; onSelect?: (value: string) => void; emptyLabel?: string
}) {
  const fieldId = useId()
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(initial)
  const result = useData<Page<T>>(`${path}${path.includes('?') ? '&' : '?'}search=${encodeURIComponent(search)}`)
  const options = result.data?.results ?? []
  const displayed = selected && !options.some(item => item.id === selected.id) ? [selected, ...options] : options
  return <div className="lookup">
    <label>Find {label.toLowerCase()}<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={`Search ${label.toLowerCase()}…`} /></label>
    <div className="lookup-field"><label htmlFor={fieldId}>{label}</label><select id={fieldId} name={name} value={selected?.id ?? ''} required={required} onChange={event => {
      setSelected(displayed.find(item => item.id === Number(event.target.value)))
      onSelect?.(event.target.value)
    }}>
      <option value="">{emptyLabel ?? (required ? 'Choose an option' : 'None')}</option>
      {displayed.map(item => <option value={item.id} key={item.id}>{optionLabel ? optionLabel(item) : item.name}</option>)}
    </select></div>
    {result.error && <span role="alert">{result.error} <button type="button" className="secondary" onClick={result.refresh}>Retry</button></span>}
    {result.data && result.data.count > options.length && <small>Refine your search to see more matches.</small>}
  </div>
}

function ProductForm({ business, product, done }: { business: Business; product?: Product; done: (text: string) => void }) {
  return <Form label={product ? 'Save changes' : 'Create product'} submit={async form => {
    const values = Object.fromEntries(form)
    await api(tenant(business, product ? `products/${product.id}/` : 'products/'), product ? 'PATCH' : 'POST', {
      ...values, category: values.category ? Number(values.category) : null,
      track_stock: form.has('track_stock'), taxable: form.has('taxable'),
    })
    done(product ? 'Product updated.' : 'Product created.')
  }}>
    <div className="field-grid">
      <label>Product name<input name="name" defaultValue={product?.name} maxLength={150} required /></label>
      <label>SKU<input name="sku" defaultValue={product?.sku} maxLength={64} required /></label>
      <label>Barcode<input name="barcode" defaultValue={product?.barcode} maxLength={64} /></label>
      <label>Unit<select name="unit" defaultValue={product?.unit ?? 'unit'}>{Object.entries({ unit: 'Unit', pack: 'Pack', carton: 'Carton', box: 'Box', kg: 'Kilogram', litre: 'Litre' }).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      <label>Selling price ({business.currency})<input type="number" name="price" min="0" step=".01" defaultValue={product?.price ?? '0'} required /></label>
      <label>Unit cost ({business.currency})<input type="number" name="cost" min="0" step=".0001" defaultValue={product?.cost ?? '0'} required /></label>
    </div>
    <Lookup<Category> name="category" label="Category" path={tenant(business, 'categories/')}
      initial={product?.category && product.category_name ? { id: product.category, name: product.category_name } : undefined} />
    <div className="field-grid"><label>Low-stock threshold<input type="number" name="reorder_level" min="0" step=".001" defaultValue={product?.reorder_level ?? '0'} required /></label>
      <div className="checks"><label><input type="checkbox" name="track_stock" defaultChecked={product?.track_stock ?? true} /> Track stock</label><label><input type="checkbox" name="taxable" defaultChecked={product?.taxable ?? false} /> Taxable</label></div></div>
    <label>Description<textarea name="description" maxLength={2000} defaultValue={product?.description} /></label>
    <label>Product image URL<input name="image_url" type="url" placeholder="https://…" maxLength={500} defaultValue={product?.image_url} /></label>
    {product && <small className="muted">Unit, cost and stock tracking lock after the first movement. Purchase receipts update average cost.</small>}
  </Form>
}

function Categories({ business, done }: { business: Business; done: () => void }) {
  const [page, setPage] = useState(1)
  const [current, setCurrent] = useState<Category>()
  const [remove, setRemove] = useState(false)
  const [revision, setRevision] = useState(0)
  const result = useData<Page<Category>>(tenant(business, `categories/?page=${page}`))
  function refresh() { setCurrent(undefined); setRemove(false); setRevision(value => value + 1); setPage(1); result.refresh(); done() }
  return <>
    <Result {...result} retry={result.refresh}>
      <ul className="category-list">{result.data?.results.map(item => <li key={item.id}><span>{item.name}</span><button className="secondary" onClick={() => { setCurrent(item); setRemove(false) }}>Edit</button><button className="secondary" onClick={() => { setCurrent(item); setRemove(true) }}>Delete</button></li>)}</ul>
      <Pager page={page} setPage={setPage} data={result.data} />
    </Result>
    <Form key={`${current?.id}-${remove}-${revision}`} label={remove ? 'Delete category' : current ? 'Save category' : 'Add category'} danger={remove} submit={async form => {
      await api(tenant(business, current ? `categories/${current.id}/` : 'categories/'), remove ? 'DELETE' : current ? 'PATCH' : 'POST', remove ? undefined : Object.fromEntries(form))
      refresh()
    }}>
      {remove ? <p>Delete <strong>{current?.name}</strong>?</p> : <label>Category name<input name="name" defaultValue={current?.name} maxLength={80} required /></label>}
      {current && <button type="button" className="secondary" onClick={() => { setCurrent(undefined); setRemove(false) }}>Cancel</button>}
    </Form>
  </>
}

export function Products({ business }: { business: Business }) {
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('name')
  const [state, setState] = useState('active')
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState<'form' | 'categories' | 'archive' | 'restore'>()
  const [current, setCurrent] = useState<Product>()
  const [status, setStatus] = useState('')
  const canEdit = editable(business)
  const result = useData<Page<Product>>(tenant(business, `products/?${new URLSearchParams({ search, state, ordering: sort, page: String(page) })}`))
  function done(message: string) { setStatus(message); setModal(undefined); setPage(1); result.refresh() }
  return <>
    <Heading label="Catalog" title="Products" subtitle="Manage your catalog, prices and stock settings.">
      {canEdit && <><button className="secondary" onClick={() => setModal('categories')}><FolderPlus size={17} /> Categories</button><button className="primary" onClick={() => { setCurrent(undefined); setModal('form') }}><Plus size={18} /> Add product</button></>}
    </Heading>
    {status && <div role="status" className="notice">{status}</div>}
    <section className="panel">
      <div className="toolbar">
        <div className="search"><Search size={17} /><input aria-label="Search products" type="search" placeholder="Search by product, SKU or barcode" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} /></div>
        <select aria-label="Product status" value={state} onChange={event => { setState(event.target.value); setPage(1) }}><option value="active">Active products</option><option value="archived">Archived products</option><option value="all">All products</option></select>
        <select aria-label="Sort products" value={sort} onChange={event => { setSort(event.target.value); setPage(1) }}><option value="name">Name A–Z</option><option value="-created_at">Newest first</option><option value="price">Lowest price</option><option value="stock">Lowest stock</option></select>
      </div>
      <Result {...result} retry={result.refresh}>
        {result.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Stock</th>{canEdit && <th>Actions</th>}</tr></thead>
          <tbody>{result.data.results.map(item => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.sku} · {item.unit}{!item.active && ' · Archived'}</small></td><td>{item.category_name ?? '—'}</td><td>{money(item.price, business)}</td><td>{item.track_stock ? quantity(item.stock) : 'Untracked'}</td>
            {canEdit && <td><div className="actions"><button className="icon-btn" aria-label={`Edit ${item.name}`} onClick={() => { setCurrent(item); setModal('form') }}><Pencil size={16} /></button><button className="icon-btn" aria-label={`${item.active ? 'Archive' : 'Restore'} ${item.name}`} onClick={() => { setCurrent(item); setModal(item.active ? 'archive' : 'restore') }}><Archive size={16} /></button></div></td>}</tr>)}</tbody></table></div> :
          <Empty title="No products found" text={search ? 'Try a different search.' : canEdit ? 'Add a product to get started.' : 'Products will appear here when added.'} />}
        <Pager page={page} setPage={setPage} data={result.data} />
      </Result>
    </section>
    {modal === 'form' && <Dialog title={current ? 'Edit product' : 'Add product'} close={() => setModal(undefined)}><ProductForm business={business} product={current} done={done} /></Dialog>}
    {modal === 'categories' && <Dialog title="Product categories" close={() => setModal(undefined)}><Categories business={business} done={result.refresh} /></Dialog>}
    {(modal === 'archive' || modal === 'restore') && current && <Dialog title={modal === 'archive' ? 'Archive product' : 'Restore product'} close={() => setModal(undefined)}>
      <Form label={modal === 'archive' ? 'Archive product' : 'Restore product'} danger={modal === 'archive'} submit={async () => {
        if (modal === 'archive') await api(tenant(business, `products/${current.id}/`), 'DELETE')
        else await api(tenant(business, `products/${current.id}/`), 'PATCH', { active: true })
        done(modal === 'archive' ? 'Product archived.' : 'Product restored.')
      }}><p>{modal === 'archive' ? 'Archive' : 'Restore'} <strong>{current.name}</strong>?</p></Form>
    </Dialog>}
  </>
}

export function Suppliers({ business }: { business: Business }) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [current, setCurrent] = useState<Supplier>()
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState('')
  const result = useData<Page<Supplier>>(tenant(business, `suppliers/?page=${page}&search=${encodeURIComponent(search)}`))
  return <>
    <Heading label="Procurement" title="Suppliers" subtitle="Keep supplier contact details ready for purchase receiving.">
      {editable(business) && <button className="primary" onClick={() => { setCurrent(undefined); setOpen(true) }}><Plus size={18} /> Add supplier</button>}
    </Heading>
    {status && <div className="notice" role="status">{status}</div>}
    <section className="panel">
      <div className="toolbar"><div className="search"><Search size={17} /><input type="search" aria-label="Search suppliers" placeholder="Search suppliers…" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} /></div></div>
      <Result {...result} retry={result.refresh}>
        {result.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Supplier</th><th>Contact</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>{result.data.results.map(item => <tr key={item.id}><td><strong>{item.name}</strong><small>{item.address}</small></td><td>{item.email || '—'}<small>{item.phone}</small></td><td><span className="pill">{item.active ? 'Active' : 'Archived'}</span></td>
          <td><div className="actions"><Link className="secondary" to={`/purchases?supplier=${item.id}`}>Purchase history</Link>{editable(business) && <button className="secondary" onClick={() => { setCurrent(item); setOpen(true) }}>Edit</button>}</div></td></tr>)}</tbody></table></div> :
          <Empty title="No suppliers found" text="Suppliers appear here when they are added to your workspace." />}
        <Pager page={page} setPage={setPage} data={result.data} />
      </Result>
    </section>
    {open && <Dialog title={current ? 'Edit supplier' : 'Add supplier'} close={() => setOpen(false)}>
      <Form label={current ? 'Save supplier' : 'Create supplier'} submit={async form => {
        await api(tenant(business, current ? `suppliers/${current.id}/` : 'suppliers/'), current ? 'PATCH' : 'POST', { ...Object.fromEntries(form), active: form.has('active') })
        setStatus(current ? 'Supplier updated.' : 'Supplier added.'); setOpen(false); setPage(1); result.refresh()
      }}>
        <label>Supplier name<input name="name" defaultValue={current?.name} maxLength={150} required /></label>
        <label>Email<input name="email" type="email" defaultValue={current?.email} /></label>
        <label>Phone<input name="phone" type="tel" defaultValue={current?.phone} maxLength={40} /></label>
        <label>Address<input name="address" defaultValue={current?.address} maxLength={250} /></label>
        <label className="check"><input name="active" type="checkbox" defaultChecked={current?.active ?? true} /> Active supplier</label>
      </Form>
    </Dialog>}
  </>
}

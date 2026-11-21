import { History, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, editable, money, tenant, useData } from './api'
import type { Business, Category, Page } from './api'
import { Lookup } from './catalog'
import { canSell, methods, shortDate, todayIn } from './finance'
import type { Customer, Expense } from './finance'
import { ExpenseBreakdown } from './reports'
import { Dialog, Empty, Form, Heading, Pager, Result } from './ui'

export function Customers({ business }: { business: Business }) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [edit, setEdit] = useState<Customer | 'new'>()
  const current = edit === 'new' ? undefined : edit
  const [notice, setNotice] = useState('')
  const result = useData<Page<Customer>>(tenant(business, `customers/?page=${page}&search=${encodeURIComponent(search)}`))
  const allowed = canSell(business.role)
  return <>
    <Heading label="Relationships" title="Customers" subtitle="Manage contacts, review transaction histories and track balances.">
      {allowed && <button className="primary" onClick={() => setEdit('new')}><Plus size={17} /> Add customer</button>}
    </Heading>
    {notice && <p className="notice" role="status">{notice}</p>}
    <section className="panel">
      <div className="toolbar"><input aria-label="Search customers" type="search" placeholder="Search by name, email or phone" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} /></div>
      <Result {...result} retry={result.refresh}>
        {result.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Customer</th><th>Contact</th><th>Outstanding</th><th>Actions</th></tr></thead>
          <tbody>{result.data.results.map(customer => <tr key={customer.id}><td><strong>{customer.name}</strong><small>{customer.active ? customer.address : 'Archived'}</small></td><td>{customer.email || '—'}<small>{customer.phone}</small></td><td>{money(customer.balance ?? '0.00', business)}</td><td><div className="actions"><Link className="secondary" to={`/sales?customer=${customer.id}`}>Sales history</Link>{allowed && <button className="secondary" onClick={() => setEdit(customer)}>Edit</button>}</div></td></tr>)}</tbody></table></div> : <Empty title="No customers found" text="Add a customer to manage their contact details and balances." />}
        <Pager page={page} setPage={setPage} data={result.data} />
      </Result>
    </section>
    {edit && <Dialog title={current ? 'Edit customer' : 'Add customer'} close={() => setEdit(undefined)}>
      <Form label={current ? 'Save customer' : 'Create customer'} submit={async form => {
        await api(tenant(business, current ? `customers/${current.id}/` : 'customers/'), current ? 'PATCH' : 'POST', { ...Object.fromEntries(form), active: form.has('active') })
        setEdit(undefined); setPage(1); result.refresh(); setNotice(current ? 'Customer updated.' : 'Customer added.')
      }}>
        <label>Customer name<input name="name" defaultValue={current?.name} maxLength={150} required /></label>
        <label>Email<input name="email" type="email" defaultValue={current?.email} /></label>
        <label>Phone<input name="phone" type="tel" defaultValue={current?.phone} maxLength={40} /></label>
        <label>Address<input name="address" defaultValue={current?.address} maxLength={250} /></label>
        <label className="check"><input name="active" type="checkbox" defaultChecked={current?.active ?? true} /> Active customer</label>
      </Form>
    </Dialog>}
  </>
}

type ExpenseEvent = { action: string; actor__username: string; created_at: string; details: { reason?: string; before?: ExpenseSnapshot; after?: ExpenseSnapshot } }
type ExpenseSnapshot = { amount: string; description: string; incurred_on: string; method: Expense['method']; category_id: number }

function ExpenseHistory({ business, expense }: { business: Business; expense: Expense }) {
  const result = useData<ExpenseEvent[]>(tenant(business, `expenses/${expense.id}/history/`))
  return <Result {...result} retry={result.refresh}><div className="audit-list">
    {result.data?.map((event, index) => <article className="receipt-line" key={index}>
      <strong className="capitalize">{event.action.split('.')[1]}</strong>
      <small>{shortDate(event.created_at, business.timezone)} · {event.actor__username}</small>
      {event.details.reason && <p>{event.details.reason}</p>}
      {([['Before', event.details.before], ['After', event.details.after]] as const).map(([label, snapshot]) => snapshot && <p key={label}><strong>{label}</strong> {money(snapshot.amount, business)} · {snapshot.incurred_on} · {methods[snapshot.method]} · {snapshot.description} · Category #{snapshot.category_id}</p>)}
    </article>)}
  </div></Result>
}

function ExpenseCategories({ business }: { business: Business }) {
  const [page, setPage] = useState(1)
  const [category, setCategory] = useState<Category>()
  const [remove, setRemove] = useState(false)
  const [revision, revise] = useState(0)
  const result = useData<Page<Category>>(tenant(business, `expense-categories/?page=${page}`))
  return <>
    <Result {...result} retry={result.refresh}>
      <ul className="category-list">{result.data?.results.map(item => <li key={item.id}><span>{item.name}</span>
        <button className="secondary" onClick={() => { setCategory(item); setRemove(false) }}>Edit</button>
        <button className="secondary" onClick={() => { setCategory(item); setRemove(true) }}>Delete</button></li>)}</ul>
      <Pager page={page} setPage={setPage} data={result.data} />
    </Result>
    <Form key={`${category?.id}-${remove}-${revision}`} label={remove ? 'Delete category' : category ? 'Save category' : 'Add category'} danger={remove} submit={async form => {
      await api(tenant(business, category ? `expense-categories/${category.id}/` : 'expense-categories/'), remove ? 'DELETE' : category ? 'PATCH' : 'POST', remove ? undefined : Object.fromEntries(form))
      setCategory(undefined); setRemove(false); revise(value => value + 1); setPage(1); result.refresh()
    }}>
      {remove ? <p>Delete <strong>{category?.name}</strong>?</p> : <label>Category name<input name="name" maxLength={80} required defaultValue={category?.name} /></label>}
      {category && <button className="secondary" type="button" onClick={() => { setCategory(undefined); setRemove(false) }}>Cancel</button>}
    </Form>
  </>
}

export function Expenses({ business }: { business: Business }) {
  const today = todayIn(business.timezone)
  const [filter, setFilter] = useState({ start: today.slice(0, 8) + '01', end: today, search: '' })
  const [page, setPage] = useState(1)
  const [edit, setEdit] = useState<Expense | 'new'>()
  const current = edit === 'new' ? undefined : edit
  const [voiding, setVoiding] = useState<Expense>()
  const [history, setHistory] = useState<Expense>()
  const [categories, setCategories] = useState(false)
  const [notice, setNotice] = useState('')
  const result = useData<Page<Expense>>(tenant(business, `expenses/?${new URLSearchParams({ ...filter, page: String(page) })}`))
  const summary = useData<import('./reports').FinancialReport>(tenant(business, `reports/?${new URLSearchParams({ start: filter.start, end: filter.end, group: 'month' })}`))
  function refresh(message: string) { result.refresh(); summary.refresh(); setPage(1); setNotice(message) }
  return <>
    <Heading label="Operating costs" title="Expenses" subtitle="Track business spending and keep a record of every correction.">
      {editable(business) && <><button className="secondary" onClick={() => setCategories(true)}>Categories</button><button className="primary" onClick={() => setEdit('new')}><Plus size={17} /> Record expense</button></>}
    </Heading>
    {notice && <p className="notice" role="status">{notice}</p>}
    <section className="panel expense-filters">
      <Form label="Apply filters" submit={async form => {
        const start = String(form.get('start')), end = String(form.get('end'))
        if (start > end) throw new Error('The start date must be on or before the end date.')
        setFilter({ start, end, search: String(form.get('search')) }); setPage(1)
      }}>
        <div className="report-dates"><label>From<input type="date" name="start" defaultValue={filter.start} required /></label><label>Through<input type="date" name="end" defaultValue={filter.end} required /></label><label>Search expenses<input type="search" name="search" placeholder="Description or category" /></label></div>
      </Form>
    </section>
    <div className="spaced">
      <Result {...summary} retry={summary.refresh}>{summary.data && <ExpenseBreakdown period={summary.data.current} business={business} />}</Result>
    </div>
    <section className="panel spaced">
      <Result {...result} retry={result.refresh}>
        {result.data?.results.length ? <div className="table-scroll"><table><thead><tr><th>Description</th><th>Date</th><th>Category</th><th>Amount</th><th>Actions</th></tr></thead>
          <tbody>{result.data.results.map(expense => <tr key={expense.id}><td><strong>{expense.description}</strong><small>{expense.voided ? 'Voided' : methods[expense.method]}</small></td><td>{expense.incurred_on}</td><td>{expense.category_name}</td><td>{money(expense.amount, business)}</td><td><div className="actions">
            <button className="secondary" onClick={() => setHistory(expense)}><History size={15} /> Audit</button>
            {editable(business) && !expense.voided && <><button className="secondary" onClick={() => setEdit(expense)}>Correct</button><button className="secondary" onClick={() => setVoiding(expense)}>Void</button></>}
          </div></td></tr>)}</tbody></table></div> : <Empty title="No expenses found" text="Record an expense or change the date and search filters." />}
        <Pager page={page} setPage={setPage} data={result.data} />
      </Result>
    </section>
    {categories && <Dialog title="Expense categories" close={() => setCategories(false)}><ExpenseCategories business={business} /></Dialog>}
    {history && <Dialog title={`Expense #${history.id} audit history`} close={() => setHistory(undefined)}><ExpenseHistory business={business} expense={history} /></Dialog>}
    {voiding && <Dialog title="Void expense" close={() => setVoiding(undefined)}><Form label="Void expense" danger submit={async form => {
      await api(tenant(business, `expenses/${voiding.id}/void/`), 'POST', Object.fromEntries(form))
      setVoiding(undefined); refresh('Expense voided.')
    }}><p>Void {money(voiding.amount, business)} for <strong>{voiding.description}</strong>?</p><label>Reason<textarea name="reason" maxLength={500} required /></label></Form></Dialog>}
    {edit && <Dialog title={current ? 'Correct expense' : 'Record expense'} close={() => setEdit(undefined)}>
      <Form label={current ? 'Save correction' : 'Save expense'} submit={async form => {
        await api(tenant(business, current ? `expenses/${current.id}/` : 'expenses/'), current ? 'PATCH' : 'POST', { ...Object.fromEntries(form), category: Number(form.get('category')) })
        setEdit(undefined); refresh(current ? 'Expense corrected.' : 'Expense recorded.')
      }}>
        <Lookup<Category> path={tenant(business, 'expense-categories/')} name="category" label="Category" required initial={current ? { id: current.category, name: current.category_name } : undefined} />
        <div className="field-grid"><label>Amount ({business.currency})<input name="amount" type="number" min=".01" step=".01" defaultValue={current?.amount} required /></label>
          <label>Expense date<input name="incurred_on" type="date" max={today} defaultValue={current?.incurred_on ?? today} required /></label></div>
        <label>Description<textarea name="description" maxLength={500} defaultValue={current?.description} required /></label>
        <label>Payment method<select name="method" defaultValue={current?.method ?? 'cash'}>{Object.entries(methods).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {current && <label>Correction reason<textarea name="reason" maxLength={500} required /></label>}
      </Form>
    </Dialog>}
  </>
}

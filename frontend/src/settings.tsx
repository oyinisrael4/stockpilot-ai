import { useState } from 'react'
import { api, tenant, useData } from './api'
import type { Business, Page, User } from './api'
import { Dialog, Form, Heading, Pager, Result } from './ui'

type Member = { id: number; username: string; role: string }

function Team({ business }: { business: Business }) {
  const [page, setPage] = useState(1)
  const [removing, setRemoving] = useState<Member>()
  const [status, setStatus] = useState('')
  const result = useData<Page<Member>>(tenant(business, `members/?page=${page}`))
  return <section className="panel settings-panel">
    <h2>Team access</h2><p className="muted">Grant workspace access to a registered StockPilot AI account.</p>
    {status && <div role="status" className="notice">{status}</div>}
    <Result {...result} retry={result.refresh}>
      <ul className="category-list">{result.data?.results.map(item => <li key={item.id}><span>{item.username}</span><span className="pill capitalize">{item.role}</span>{item.role !== 'owner' && <button className="secondary" onClick={() => setRemoving(item)}>Remove</button>}</li>)}</ul>
      <Pager page={page} setPage={setPage} data={result.data} />
    </Result>
    <Form label="Save member access" submit={async form => {
      await api(tenant(business, 'members/'), 'POST', Object.fromEntries(form))
      setStatus('Member access saved.'); setPage(1); result.refresh()
    }}>
      <div className="field-grid"><label>Member username<input name="username" maxLength={150} required /></label><label>Role<select name="role" defaultValue="viewer"><option value="viewer">Viewer</option><option value="analyst">Analyst</option><option value="cashier">Cashier</option><option value="manager">Manager</option></select></label></div>
    </Form>
    {removing && <Dialog title="Remove access" close={() => setRemoving(undefined)}><Form label="Remove member" danger submit={async () => {
      await api(tenant(business, `members/${removing.id}/`), 'DELETE')
      setStatus('Member access removed.'); setRemoving(undefined); setPage(1); result.refresh()
    }}><p>Remove <strong>{removing.username}</strong> from this workspace?</p></Form></Dialog>}
  </section>
}

export function WorkspaceSettings({ business, user, onUser, refresh }: { business: Business; user: User; onUser: (user: User) => void; refresh: () => void }) {
  const [status, setStatus] = useState('')
  const owner = business.role === 'owner'
  const fields = <>
    <label>Business name<input name="name" defaultValue={business.name} maxLength={120} required /></label>
    <div className="field-grid"><label>Currency<select name="currency" defaultValue={business.currency}>{['NGN', 'USD', 'GBP', 'EUR'].map(code => <option key={code}>{code}</option>)}</select></label><label>Time zone<input name="timezone" defaultValue={business.timezone} maxLength={64} required /></label></div>
    <label>Default tax rate (%)<input name="tax_rate" type="number" min="0" max="100" step=".01" defaultValue={business.tax_rate} required /></label>
    <label>Address<input name="address" defaultValue={business.address} maxLength={250} /></label>
    <label>Receipt footer<input name="receipt_footer" defaultValue={business.receipt_footer} maxLength={250} /></label>
  </>
  return <>
    <Heading label="Administration" title="Settings" subtitle="Manage your profile and workspace preferences." />
    {status && <div className="notice" role="status">{status}</div>}
    <div className="settings-grid">
      <section className="panel settings-panel"><h2>Business settings</h2><p className="muted">{owner ? 'Configure the defaults for your business.' : 'The workspace owner manages these settings.'}</p>
        {owner ? <Form label="Save settings" submit={async form => {
          await api(tenant(business, 'settings/'), 'PATCH', Object.fromEntries(form))
          refresh(); setStatus('Workspace settings saved.')
        }}>{fields}</Form> : <fieldset disabled>{fields}</fieldset>}
      </section>
      <section className="panel settings-panel"><h2>Profile</h2><p className="muted">{user.username} · {user.email}</p>
        <Form label="Save profile" submit={async form => { onUser(await api<User>('auth/profile/', 'PATCH', Object.fromEntries(form))); setStatus('Profile saved.') }}>
          <label>First name<input name="first_name" defaultValue={user.first_name} maxLength={150} /></label>
          <label>Last name<input name="last_name" defaultValue={user.last_name} maxLength={150} /></label>
        </Form>
      </section>
      {owner && <Team business={business} />}
    </div>
  </>
}

import { Archive, BarChart3, Boxes, Building2, ChevronRight, ClipboardList, LayoutDashboard, LogOut, Menu, Package, ReceiptText, RotateCcw, Settings, ShieldCheck, ShoppingCart, Sparkles, Truck, Users, Wallet, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { api, editable, tenant, useData } from './api'
import type { Business, Movement, User } from './api'
import { Brand, Empty, Form, Heading, Result } from './ui'
import { Products, Suppliers } from './catalog'
import { Inventory, MovementsTable, Purchases } from './stock'
import { WorkspaceSettings } from './settings'
import { Pos } from './pos'
import { Returns, SalesHistory } from './sales-history'
import { Customers, Expenses } from './operations'
import { DashboardFinance, Reports } from './reports'
import { Insights } from './insights'
import { Assistant } from './assistant'
import { Landing, StockSculpture } from './landing'
import './style.css'
import './design.css'

const navigation = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/pos', label: 'Point of sale', icon: ShoppingCart },
  { path: '/sales', label: 'Sales history', icon: ReceiptText },
  { path: '/products', label: 'Products', icon: Package },
  { path: '/inventory', label: 'Inventory', icon: Boxes },
  { path: '/purchases', label: 'Purchases', icon: ClipboardList },
  { path: '/customers', label: 'Customers', icon: Users },
  { path: '/suppliers', label: 'Suppliers', icon: Truck },
  { path: '/returns', label: 'Returns', icon: RotateCcw },
  { path: '/expenses', label: 'Expenses', icon: Wallet },
  { path: '/reports', label: 'Reports', icon: BarChart3 },
  { path: '/insights', label: 'Insights', icon: BarChart3 },
  { path: '/assistant', label: 'AI Assistant', icon: Sparkles },
  { path: '/settings', label: 'Settings', icon: Settings },
]

function Account({ signedIn }: { signedIn: (user: User) => void }) {
  const navigate = useNavigate()
  const [resetSent, setResetSent] = useState(false)
  const [resetDone, setResetDone] = useState(false)
  const token = new URLSearchParams(location.hash.slice(1))
  const resetMode = token.has('uid') && token.has('token') && !resetDone
  function authForm(register: boolean) {
    return <Form key={register ? 'register' : 'login'} label={register ? 'Create workspace' : 'Sign in'} submit={async form => {
      signedIn(await api<User>(`auth/${register ? 'register' : 'login'}/`, 'POST', Object.fromEntries(form)))
      navigate('/')
    }}>
      {register && <label>Business name<input name="business_name" maxLength={120} required autoComplete="organization" /></label>}
      <label>Username<input name="username" autoComplete="username" maxLength={150} required /></label>
      {register && <label>Email<input name="email" type="email" autoComplete="email" required /></label>}
      <label>Password<input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 8 : undefined} maxLength={256} required /></label>
    </Form>
  }
  return <main className="account-layout">
    <aside className="account-art">
      <Link className="auth-brand-link" to="/about"><Brand /></Link>
      <div className="account-story"><StockSculpture />
        <span className="eyebrow">Business operations workspace</span><h1>Know what’s in stock.<br />Stay ready for what’s next.</h1>
        <p>Manage products, receive purchases and track inventory in one place.</p></div>
      <small>StockPilot AI · Created by Israel Oyinlola</small>
    </aside>
    <section className="account-card">
      <Link className="mobile-brand" to="/about"><Brand /></Link>
      <Routes>
        <Route path="/register" element={<><Heading label="Get started" title="Create your workspace" subtitle="Set up your business and start building your catalog." />{authForm(true)}<p>Already registered? <Link to="/login">Sign in</Link></p></>} />
        <Route path="/reset" element={<>
          <Heading label="Account access" title={resetMode ? 'Choose a new password' : 'Reset your password'} subtitle="Recover access to your StockPilot AI account." />
          {resetDone ? <div className="notice" role="status">Password updated. Sign in with your new password.</div> : resetSent ?
            <div className="notice" role="status">If the address is registered, a reset link will be sent.</div> :
            <Form label={resetMode ? 'Update password' : 'Send reset link'} submit={async form => {
              if (resetMode) {
                await api('auth/reset/confirm/', 'POST', { uid: token.get('uid'), token: token.get('token'), password: form.get('password') })
                setResetDone(true)
                navigate('/reset', { replace: true })
              } else {
                await api('auth/reset/', 'POST', { email: form.get('email') })
                setResetSent(true)
              }
            }}>{resetMode ? <label>New password<input name="password" type="password" autoComplete="new-password" minLength={8} maxLength={256} required /></label> :
              <label>Email<input name="email" type="email" autoComplete="email" required /></label>}</Form>}
          <p><Link to="/login">Back to sign in</Link></p>
        </>} />
        <Route path="/login" element={<><Heading label="Your workspace" title="Welcome back" subtitle="Sign in to manage your business." />{authForm(false)}<p><Link to="/reset">Forgot password?</Link></p><p>New to StockPilot AI? <Link to="/register">Create a workspace</Link></p></>} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </section>
  </main>
}

type OverviewData = { products: number; tracked: number; low_stock: number; receipts: number; recent_movements: Movement[] }

function Overview({ business }: { business: Business }) {
  const result = useData<OverviewData>(tenant(business, 'overview/'))
  const data = result.data
  return <>
    <Heading label="Workspace overview" title="Overview" subtitle="See financial performance, stock health and the latest activity.">
      <Link className="secondary" to="/products">Open catalog <ChevronRight size={16} /></Link>
      <Link className="primary" to="/assistant"><Sparkles size={17} /> Ask StockPilot AI</Link>
    </Heading>
    <DashboardFinance business={business} />
    <Result {...result} retry={result.refresh}>{data && <>
      <div className="metrics">
        {[
          { label: 'Active products', value: data.products, icon: Package, to: '/products', tone: 'blue' },
          { label: 'Tracked products', value: data.tracked, icon: Boxes, to: '/inventory', tone: 'mint' },
          { label: 'Low stock', value: data.low_stock, icon: Archive, to: '/inventory?low=1', tone: 'amber' },
          { label: 'Purchase receipts', value: data.receipts, icon: ClipboardList, to: '/purchases', tone: 'violet' },
        ].map(({ label, value, icon: Icon, to, tone }) => <Link key={label} to={to} className={`metric ${tone}`}><span className="tile-icon"><Icon size={21} /></span><span>{label}<strong>{value}</strong></span><ChevronRight className="metric-arrow" size={16} /></Link>)}
      </div>
      <div className="overview-grid">
        <section className="panel"><div className="panel-head"><div><h2>Recent stock activity</h2><p>Stock received, sold and returned.</p></div><Link to="/inventory">View inventory <ChevronRight size={15} /></Link></div>
          {data.recent_movements.length ? <MovementsTable movements={data.recent_movements} business={business} /> : <Empty title="No stock activity yet" text="Record an opening balance or receive a purchase to see it here." />}
        </section>
        <section className="panel quick"><div className="panel-head"><div><h2>Quick actions</h2><p>Get to the work that matters.</p></div></div>
          <Link to="/products"><Package size={19} /><span>Manage catalog<small>Browse products and categories</small></span><ChevronRight size={16} /></Link>
          <Link to="/purchases"><ClipboardList size={19} /><span>{editable(business) ? 'Receive purchases' : 'View purchases'}<small>Open the supplier receipt log</small></span><ChevronRight size={16} /></Link>
          <Link to="/suppliers"><Truck size={19} /><span>Open suppliers<small>View your supplier directory</small></span><ChevronRight size={16} /></Link>
        </section>
      </div>
    </>}</Result>
  </>
}

function Workspace({ user, onUser }: { user: User; onUser: (user: User | null) => void }) {
  const workspaces = useData<Business[]>('businesses/')
  const [selected, select] = useState<number>()
  const [drawer, showDrawer] = useState(false)
  const menu = useRef<HTMLButtonElement>(null)
  const closeMenu = useRef<HTMLButtonElement>(null)
  const mobileNav = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!drawer) return
    closeMenu.current?.focus()
    function handle(event: KeyboardEvent) {
      if (event.key === 'Escape') showDrawer(false)
      if (event.key !== 'Tab') return
      const items = Array.from(mobileNav.current?.querySelectorAll<HTMLElement>('a, button') ?? [])
      const first = items[0], last = items.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    window.addEventListener('keydown', handle)
    return () => { window.removeEventListener('keydown', handle); menu.current?.focus() }
  }, [drawer])
  const [signOutError, setSignOutError] = useState('')
  const navigate = useNavigate()
  const business = workspaces.data?.find(item => item.id === selected) ?? workspaces.data?.[0]
  async function signOut() {
    try { await api('auth/logout/', 'POST'); onUser(null); navigate('/login') }
    catch (error) { setSignOutError((error as Error).message) }
  }
  return <Result {...workspaces} retry={workspaces.refresh}>
    {!business ? <div className="no-workspace"><Empty title="No workspace access" text="Ask a workspace owner to add your account." /><button className="secondary" onClick={signOut}>Sign out</button>{signOutError && <p role="alert">{signOutError}</p>}</div> :
      <div className="app-layout">
        <a className="skip" href="#main-content">Skip to content</a>
        {drawer && <button className="scrim" aria-label="Close navigation" onClick={() => showDrawer(false)} />}
        <aside ref={mobileNav} id="workspace-nav" className={`sidebar ${drawer ? 'visible' : ''}`}>
          <div className="sidebar-brand"><Link to="/" onClick={() => showDrawer(false)}><Brand /></Link><button className="icon-btn menu-toggle" ref={closeMenu} aria-label="Close menu" onClick={() => showDrawer(false)}><X size={20} /></button></div>
          
          <nav aria-label="Main navigation">{[
            ['Operations', ['/', '/pos', '/sales', '/returns', '/expenses']],
            ['Stock & relationships', ['/products', '/inventory', '/purchases', '/suppliers', '/customers']],
            ['Intelligence', ['/reports', '/insights', '/assistant']],
            ['Workspace', ['/settings']],
          ].map(([name, paths]) => <div className="nav-group" key={String(name)}><span>{name}</span>
            {navigation.filter(item => paths.includes(item.path)).map(({ path, label, icon: Icon }) =>
              <NavLink key={path} to={path} end={path === '/'} onClick={() => showDrawer(false)}><Icon size={18} /><span>{label}</span></NavLink>)}
          </div>)}</nav>
          <div className="sidebar-footer"><ShieldCheck size={21} /><span>Business workspace<small>Created by Israel Oyinlola</small></span></div>
        </aside>
        <div className="app-main">
          <div className="topbar"><button className="icon-btn menu-toggle" ref={menu} aria-controls="workspace-nav" aria-label="Open menu" aria-expanded={drawer} onClick={() => showDrawer(!drawer)}><Menu size={21} /></button>
            <div className="business-switch"><Building2 size={19} />{workspaces.data!.length > 1 ?
              <select aria-label="Business workspace" value={business.id} onChange={event => select(Number(event.target.value))}>{workspaces.data!.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select> : <strong>{business.name}</strong>}</div>
            <div className="account-menu"><span className="avatar" aria-hidden="true">{(user.first_name || user.username).slice(0, 2).toUpperCase()}</span>
              <span className="identity"><strong>{user.first_name || user.username}</strong><small>{business.role}</small></span><button className="icon-btn" title="Sign out" aria-label="Sign out" onClick={signOut}><LogOut size={18} /></button></div>
          </div>
          <main className="content" id="main-content" tabIndex={-1} key={business.id}>
            {signOutError && <div className="notice error" role="alert">{signOutError}</div>}
            <Routes>
              <Route path="/" element={<Overview business={business} />} />
              <Route path="/app" element={<Navigate to="/" replace />} />
              <Route path="/pos" element={<Pos business={business} />} />
              <Route path="/sales" element={<SalesHistory business={business} />} />
              <Route path="/products" element={<Products business={business} />} />
              <Route path="/inventory" element={<Inventory business={business} />} />
              <Route path="/purchases" element={<Purchases business={business} />} />
              <Route path="/suppliers" element={<Suppliers business={business} />} />
              <Route path="/customers" element={<Customers business={business} />} />
              <Route path="/returns" element={<Returns business={business} />} />
              <Route path="/expenses" element={<Expenses business={business} />} />
              <Route path="/reports" element={<Reports business={business} />} />
              <Route path="/insights" element={<Insights business={business} />} />
              <Route path="/assistant" element={<Assistant business={business} />} />
              <Route path="/settings" element={<WorkspaceSettings business={business} user={user} onUser={onUser} refresh={workspaces.refresh} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>}
  </Result>
}

function App() {
  useEffect(() => {
    function makeTablesAccessible() {
      document.querySelectorAll<HTMLElement>('.table-scroll').forEach(region => {
        region.tabIndex = 0
        if (!region.hasAttribute('role')) region.setAttribute('role', 'region')
        if (!region.hasAttribute('aria-label')) region.setAttribute('aria-label', 'Scrollable records')
      })
    }
    makeTablesAccessible()
    const observer = new MutationObserver(makeTablesAccessible)
    observer.observe(document.getElementById('root')!, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])
  const { pathname } = useLocation()
  const session = useData<{ user: User | null }>('auth/session/')
  const [user, setUser] = useState<User | null>()
  const current = user === undefined ? session.data?.user : user
  if (pathname === "/about" || (pathname === "/" && current === null)) return <Landing signedIn={Boolean(current)} />
  return <Result {...session} retry={session.refresh}>{current ? <Workspace user={current} onUser={setUser} /> : <Account signedIn={setUser} />}</Result>
}

createRoot(document.getElementById('root')!).render(<BrowserRouter><App /></BrowserRouter>)

import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter, Link, Route, Routes } from 'react-router-dom'
import { ArrowLeft, RotateCcw, ShoppingCart, Sparkles } from 'lucide-react'
import { Landing } from './landing'
import { Brand } from './ui'
import './style.css'
import './design.css'
import './showcase.css'

// Deliberately authored public fiction; never exported from a private workspace.
const catalog = [
  { name: 'Spring Water 75 cl', image: 'spring-water', price: 35000, cost: 20000, stock: 24 },
  { name: 'Sparkling Water 50 cl', image: 'sparkling-water', price: 65000, cost: 39000, stock: 8 },
  { name: 'Hibiscus Cooler 33 cl', image: 'hibiscus', price: 75000, cost: 42000, stock: 18 },
  { name: 'Plantain Crisps 75 g', image: 'plantain', price: 120000, cost: 72000, stock: 16 },
  { name: 'Ginger Tea 20 bags', image: 'ginger-tea', price: 240000, cost: 144000, stock: 12 },
  { name: 'Roasted Cashews 100 g', image: 'cashews', price: 185000, cost: 111000, stock: 14 },
]
const money = (cents: number) => new Intl.NumberFormat('en-NG', { style: 'currency', currency: 'NGN' }).format(cents / 100)
const asset = (name: string) => `${import.meta.env.BASE_URL}portfolio/${name}`

function Creator() {
  const github = import.meta.env.VITE_STOCKPILOT_GITHUB_URL || 'https://github.com/oyinisrael4'
  const portfolio = import.meta.env.VITE_STOCKPILOT_PORTFOLIO_URL || 'https://israel-projects-one.vercel.app'
  return <section className="creator"><h2>Built by Israel Oyinlola</h2><p>Full-stack engineering · Financial integrity · Local AI · Product design</p><div className="actions"><a className="secondary" href={github} rel="noopener noreferrer">GitHub ↗</a>{/^https:\/\//.test(portfolio || '') ? <a className="secondary" href={portfolio} rel="noopener noreferrer">Portfolio ↗</a> : <Link className="secondary" to="/creator">Developer portfolio</Link>}</div></section>
}

function DeveloperPortfolio() {
  return <main className="creator"><Link className="secondary" to="/">← StockPilot showcase</Link><span className="eyebrow">Selected project · Israel Oyinlola</span><h1>Engineering a business workspace from checkout to clarity.</h1><p>StockPilot AI connects a React and TypeScript interface to Django REST Framework and PostgreSQL, with optional local Ollama and Whisper inference.</p><h2>What this project demonstrates</h2><ul><li>Workspace-scoped permissions and transaction confirmation.</li><li>Deterministic financial calculations, inventory locking and retry safeguards.</li><li>Typed and spoken conversational workflows backed by authorized tools.</li><li>Responsive product design with a distinct, consistent V2 identity.</li></ul><p>This is the StockPilot project portfolio page. A separate personal portfolio website can be linked when available.</p><Creator /></main>
}

function Demo() {
  const [tab, setTab] = useState('Checkout')
  const [stock, setStock] = useState(catalog.map(p => p.stock))
  const [cart, setCart] = useState<number[]>(catalog.map(() => 0))
  const [sales, setSales] = useState<{ total: number; cost: number; units: number }[]>([])
  const [review, setReview] = useState(false)
  const [proposal, setProposal] = useState(false)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const total = cart.reduce((sum, qty, i) => sum + qty * catalog[i].price, 0)
  const revenue = sales.reduce((sum, sale) => sum + sale.total, 0)
  const cost = sales.reduce((sum, sale) => sum + sale.cost, 0)
  function checkout(quantities: number[]) {
    if (!quantities.some(Boolean) || quantities.some((qty, i) => qty < 0 || qty > stock[i])) return
    setSales(current => [...current, { total: quantities.reduce((s, q, i) => s + q * catalog[i].price, 0), cost: quantities.reduce((s, q, i) => s + q * catalog[i].cost, 0), units: quantities.reduce((s, q) => s + q, 0) }])
    setStock(current => current.map((q, i) => q - quantities[i]))
    setCart(catalog.map(() => 0)); setReview(false); setProposal(false)
    setStatus('Fictional sale recorded in this tab. No backend or payment was contacted.')
  }
  function reset() { setStock(catalog.map(p => p.stock)); setCart(catalog.map(() => 0)); setSales([]); setReview(false); setProposal(false); setStatus('Demo reset.'); setSearch('') }
  return <main className="public-demo">
    <header className="demo-heading"><Link to="/" className="secondary"><ArrowLeft size={16} /> Showcase</Link><Brand /><button className="secondary" onClick={reset}><RotateCcw size={16} /> Reset demo</button></header>
    <div className="notice demo-disclosure"><strong>Fictional, browser-only sandbox</strong><p>Juniper Market Supply · Authored sample catalog. Changes exist only in this tab and reset on reload. No real payments, accounts, microphone recording, live AI, or database connection.</p></div>
    <header className="page-heading"><div><span className="eyebrow">Juniper Market Supply</span><h1>Your next sale. A clearer picture.</h1><p>Try checkout, then see its effect on stock and profit.</p></div></header>
    <nav className="preview-steps" aria-label="Demo sections">{['Checkout', 'Performance', 'Guided assistant', 'Voice walkthrough'].map(name => <button key={name} className={tab === name ? 'primary' : 'secondary'} aria-pressed={tab === name} onClick={() => { setTab(name); setReview(false) }}>{name}</button>)}</nav>
    <p role="status" className="demo-status">{status}</p>
    {tab === 'Checkout' && <div className="sandbox-pos"><section><label className="demo-search">Search fictional products<input value={search} onChange={e => setSearch(e.target.value)} type="search" placeholder="Try water or tea" /></label><div className="demo-products">{catalog.map((p, i) => p.name.toLowerCase().includes(search.toLowerCase()) && <article className="product-tile" key={p.name}><img src={asset(p.image + '.webp')} alt={p.name} /><div><h2>{p.name}</h2><p>{stock[i]} units available {stock[i] <= 8 && <strong>· Low stock</strong>}</p><strong className="money">{money(p.price)}</strong><button className="secondary" disabled={cart[i] >= stock[i]} onClick={() => { setCart(c => c.map((q, n) => n === i ? q + 1 : q)); setReview(false) }}>Add {p.name}</button></div></article>)}</div>{!catalog.some(p => p.name.toLowerCase().includes(search.toLowerCase())) && <p>No products match. Try another search.</p>}</section><section className="panel demo-cart"><h2><ShoppingCart size={21} /> Current sale</h2>{cart.map((q, i) => q > 0 && <div className="demo-cart-line" key={i}><strong>{catalog[i].name}</strong><div className="actions"><button className="secondary" aria-label={'Remove one ' + catalog[i].name} onClick={() => { setCart(c => c.map((v, n) => n === i ? v - 1 : v)); setReview(false) }}>−</button><span>{q} × {money(catalog[i].price)}</span></div></div>)}<p className="demo-total">Total <strong className="money">{money(total)}</strong></p>{review ? <><p>Review complete. Record this fictional cash sale?</p><button className="primary" onClick={() => checkout(cart)}>Confirm fictional sale</button><button className="secondary" onClick={() => setReview(false)}>Cancel review</button></> : <button className="primary" disabled={!total} onClick={() => setReview(true)}>Review checkout</button>}</section></div>}
    {tab === 'Performance' && <section><div className="demo-metrics">{[['Net sales', revenue], ['Cost of goods', cost], ['Gross profit', revenue - cost]].map(([label, amount]) => <article className="panel" key={label}><p>{label}</p><strong className="money">{money(Number(amount))}</strong></article>)}</div><section className="panel"><h2>Recorded in this tab</h2><p>{sales.length} fictional sales · {sales.reduce((s, sale) => s + sale.units, 0)} units sold. No operating expenses are included, so gross profit is not net profit.</p><h3>Sales by transaction</h3>{sales.length ? sales.map((sale, i) => <div className="demo-bar" key={i}><span>Sale {i + 1}</span><meter aria-label={'Sale ' + (i + 1)} min={0} max={Math.max(...sales.map(s => s.total))} value={sale.total} /><strong className="money">{money(sale.total)}</strong></div>) : <p>No sample sales yet. Complete a checkout to populate this view.</p>}</section></section>}
    {tab === 'Guided assistant' && <section className="panel demo-chat"><span className="eyebrow"><Sparkles size={16} /> Scripted workflow · No model connected</span><h2>Explore the confirmation safeguard</h2><p>The full application accepts natural language with local Ollama. Here, choose a guided scenario to inspect a proposal or a summary calculated from this tab’s sample sales.</p><div className="actions"><button className="secondary" disabled={stock[0] < 2 || proposal} onClick={() => { setProposal(true); setStatus('Guided scenario: Sell two bottles of spring water in cash.') }}>Preview two waters</button><button className="secondary" onClick={() => setStatus(`Calculated sample summary: ${sales.length} sales; net sales ${money(revenue)}; gross profit ${money(revenue - cost)}. These are browser sandbox totals, not a live AI response.`)}>Summarize sample sales</button></div>{proposal && <div className="demo-proposal"><h3>Sale preview · Not recorded</h3><p>2 × Spring Water 75 cl · Cash</p><strong className="money">{money(catalog[0].price * 2)}</strong><p>Stock and totals change only when you confirm.</p><div className="actions"><button className="primary" onClick={() => checkout([2, 0, 0, 0, 0, 0])}>Confirm fictional proposal</button><button className="secondary" onClick={() => { setProposal(false); setStatus('Proposal cancelled. Stock and sales are unchanged.') }}>Cancel proposal</button></div></div>}</section>}
    {tab === 'Voice walkthrough' && <section className="panel demo-chat"><span className="eyebrow">Illustrated workflow · No recording or transcription</span><h2>Speak. Review. Then send.</h2><ol><li>In the local application, allow microphone access and record up to 45 seconds.</li><li>Preview or discard the audio. Offline Whisper creates a transcription.</li><li>Edit the transcription before explicitly sending it into the shared conversation.</li><li>Review the proposed transaction and confirm before anything is recorded.</li></ol><p>This static demo deliberately does not request microphone permission or simulate speech recognition.</p><img className="voice-capture" src={asset('assistant.png')} alt="Genuine local StockPilot assistant interface captured in the fictional demo workspace" /></section>}
  </main>
}

createRoot(document.getElementById('root')!).render(<HashRouter><Routes><Route path="/" element={<><Landing signedIn={false} showcase /><Creator /></>} /><Route path="/demo" element={<Demo />} /><Route path="/creator" element={<DeveloperPortfolio />} /><Route path="*" element={<main className="creator"><h1>Page not found</h1><Link to="/">Return to the showcase</Link></main>} /></Routes></HashRouter>)

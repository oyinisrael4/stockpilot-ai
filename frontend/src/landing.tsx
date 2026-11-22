import { ArrowRight, BarChart3, Boxes, ShoppingCart, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { Brand } from './ui'

const views = [
  { image: 'pos', title: 'Record a sale', icon: ShoppingCart, description: 'Scan or search for items, review the total, then record payment.' },
  { image: 'overview', title: 'See what changed', icon: BarChart3, description: 'Follow sales, costs and stock movements as they appear in the workspace.' },
  { image: 'assistant', title: 'Ask for the breakdown', icon: Sparkles, description: 'Ask a follow-up and review the recorded figures behind the answer.' },
]

export function StockSculpture() {
  return <img className="stock-sculpture" src={import.meta.env.BASE_URL + 'portfolio/retail-studio.webp'} alt="" fetchPriority="high" />
}

export function Landing({ signedIn, showcase = false, demoUrl }: { signedIn: boolean; showcase?: boolean; demoUrl?: string }) {
  function scrollSection(event: MouseEvent<HTMLAnchorElement>) {
    if (!showcase) return
    event.preventDefault()
    const target = document.getElementById(event.currentTarget.hash.slice(1))
    target?.scrollIntoView()
    target?.focus({ preventScroll: true })
  }
  const [active, setActive] = useState(1)
  const view = views[active]
  const local = ['localhost', '127.0.0.1'].includes(location.hostname)
  const demo = demoUrl || import.meta.env.VITE_STOCKPILOT_DEMO_URL || (local ? 'http://127.0.0.1:5196/login' : '')
  return <div className="landing landing-v2">
    <a className="skip" href="#product" onClick={scrollSection}>Skip to content</a>
    <header className="landing-nav">
      <Link to={showcase ? '/' : '/about'} aria-label="StockPilot AI home"><Brand /></Link>
      <nav aria-label="Product navigation"><a href="#workflows" onClick={scrollSection}>How it works</a>{showcase ? <Link to="/demo">Try the demo</Link> : <Link to={signedIn ? '/app' : '/login'}>{signedIn ? 'Open workspace' : 'Sign in'}</Link>}</nav>
    </header>
    <main id="product" tabIndex={-1}>
      <section className="landing-hero">
        <div className="hero-copy">
          <span className="eyebrow">Built for retail businesses</span>
          <h1>Know what sells.<br />Know what stays.</h1>
          <p>Inventory, checkout and intelligence in one workspace. See what moved, what earned a profit, and where to act next.</p>
          <div className="actions">
            {showcase ? <Link className="primary" to="/demo">Explore interactive demo <ArrowRight size={17} /></Link> : <a className="primary" href={demo || '#workflows'}>{demo ? 'Explore live demo' : 'Explore product'} <ArrowRight size={17} /></a>}
            {showcase ? <a className="secondary" href="#capabilities" onClick={scrollSection}>See the capabilities</a> : <Link className="secondary" to={signedIn ? '/app' : '/register'}>{signedIn ? 'Open workspace' : 'Create a workspace'}</Link>}
          </div>
        </div>
        <StockSculpture />
      </section>
      {showcase && <section className="showcase-capabilities" id="capabilities"><span className="eyebrow">One connected operation</span><h2>Built for the work behind the numbers.</h2><div className="capability-grid">{[
        ['Inventory & purchasing', 'Stock movements, supplier receipts, weighted-average costs and low-stock alerts.'],
        ['Point of sale', 'Search, discounts, split tenders, receipts and returns with stock-safe checkout.'],
        ['Financial reporting', 'Recorded sales, costs, expenses and receivables across custom date ranges.'],
        ['Conversational assistant', 'Local Ollama interprets requests; authorized backend tools retrieve records and prepare confirmed actions.'],
        ['Optional voice input', 'Offline Whisper transcription, audio preview and editable text before sending.'],
        ['Business intelligence', 'Period comparisons, stock recommendations and clearly labelled forecasts when history supports them.'],
      ].map(([title, text]) => <article key={title}><h3>{title}</h3><p>{text}</p></article>)}</div><p className="notice">The full application runs locally with Django, PostgreSQL, Ollama and Whisper. This public showcase uses screenshots and a guided browser-only sandbox. No live AI or speech recognition runs here.</p></section>}
      <section className="landing-workflows portfolio-preview" id="workflows">
        <div className="preview-heading"><div><span className="eyebrow">From checkout to clarity</span><h2>A sale is only the beginning.</h2></div>
          <p>Explore real screens captured in the fictional Juniper Market Supply workspace.</p></div>
        <nav aria-label="Product preview steps" className="preview-steps">
          {views.map(({ title, icon: Icon }, index) => <button type="button" className={active === index ? 'primary' : 'secondary'}
            key={title} aria-pressed={active === index} aria-controls="workflow-preview" onClick={() => setActive(index)}><Icon size={17} />{title}</button>)}
        </nav>
        <figure id="workflow-preview" className="preview-frame">
          <figcaption><strong>{view.title}</strong><span>{view.description}</span></figcaption>
          <img key={view.image} src={import.meta.env.BASE_URL + 'portfolio/' + view.image + '.png'} alt={'StockPilot interface: ' + view.title} loading="lazy" />
        </figure>
      </section>
    </main>
    <footer className="landing-footer"><Brand /><span><Boxes size={16} /> Created by Israel Oyinlola</span></footer>
  </div>
}

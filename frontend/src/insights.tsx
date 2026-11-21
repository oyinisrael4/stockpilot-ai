import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, ChartNoAxesCombined, PackageSearch, Sparkles } from 'lucide-react'
import { money, quantity, tenant, useData, type Business } from './api'
import { todayIn } from './finance'
import { Heading } from './ui'
import { Trend } from './assistant-cards'

type Amount = string
type Product = { name: string; sku: string; units: string; revenue: Amount; previous_revenue: Amount; profit: Amount }
type Data = {
  start: string; end: string; comparison_start: string; comparison_end: string; comparable: boolean
  metrics: { key: string; label: string; current: string | number; previous: string | number; delta: string | number; percent: string | null }[]
  drivers: { label: string; delta: Amount }[]
  recommendations: { key: string; priority: number; title: string; evidence: string; action: string; estimate: string | null; link: string }[]
  products: Product[]
  series: { date: string; net_sales: Amount; operating_expenses: Amount }[]
  unusual: { name: string; largest: Amount; baseline: Amount }[]
  expenses: { name: string; current: Amount; previous: Amount; delta: Amount }[]
  low: (Product & { stock: string; reorder_at: string; unit: string; selling_days: number; suggested: string | null })[]
  slow: (Product & { stock: string; unit: string; selling_days: number })[]
  customers: { id: number; name: string; outstanding: Amount; age: number | null; open_invoices: number;
    payments: Amount; later_payments: number; latest_payment: string | null }[]
  outstanding: Amount
  active_days: number
  forecast: { available: false; note: string } | { available: true; note: string; start: string; end: string;
    history_start: string; history_end: string; history: { date: string; net_sales: Amount }[]; estimate: Amount; low: Amount; high: Amount }
}
function ForecastPlot({ series, estimate }: { series: { date: string; net_sales: Amount }[]; estimate: Amount }) {
  const values = [...series.map(point => Number(point.net_sales)), Number(estimate)]
  const max = Math.max(...values, 1)
  const xy = (index: number) => [15 + index * 390 / (values.length - 1), 111 - values[index] / max * 93]
  const points = values.slice(0, -1).map((_, index) => xy(index).join(',')).join(' ')
  const [x, y] = xy(values.length - 1)
  return <figure className="forecast-plot"><svg viewBox="0 0 420 125" aria-hidden="true">
    {[18, 49, 80, 111].map(tick => <line key={tick} x1="15" x2="405" y1={tick} y2={tick} className="chart-grid" />)}
    <polyline points={points} fill="none" stroke="#4934c2" strokeWidth="2.5" />
    <polyline points={xy(values.length - 2).join(',') + ' ' + xy(values.length - 1).join(',')} fill="none" stroke="#4934c2" strokeWidth="2.5" strokeDasharray="5 5" />
    <circle cx={x} cy={y} r="4" fill="white" stroke="#4934c2" strokeWidth="2" />
  </svg><figcaption>Recorded weekly sales · Dashed line shows estimate</figcaption></figure>
}

const sections = ['Priorities', 'Performance', 'Stock', 'Payments'] as const

function DataTable({ caption, headers, rows, empty }: { caption: string; headers: string[]; rows: ReactNode[][]; empty: string }) {
  return <section className="panel insights-panel">
    <h2>{caption}</h2>
    {rows.length > 0 ? <div className="table-scroll" tabIndex={0} role="region" aria-label={caption + " data"}><table aria-label={caption}><thead><tr>
      {headers.map(header => <th key={header} scope="col">{header}</th>)}
    </tr></thead><tbody>{rows.map((row, index) => <tr key={index}>
      {row.map((cell, col) => <td key={col}>{cell}</td>)}
    </tr>)}</tbody></table></div> : <p className="muted">{empty}</p>}
  </section>
}

export function Insights({ business }: { business: Business }) {
  const today = todayIn(business.timezone)
  const lastDay = new Date(Date.parse(today) - 86400000).toISOString().slice(0, 10)
  const firstDay = new Date(Date.parse(today) - 30 * 86400000).toISOString().slice(0, 10)
  const [query, setQuery] = useState({ start: firstDay, end: lastDay, group: 'week' })
  const [custom, setCustom] = useState(false)
  const [section, setSection] = useState<typeof sections[number]>('Priorities')
  const [invalid, setInvalid] = useState('')
  const { data, error } = useData<Data>(tenant(business, 'insights/?' + new URLSearchParams(query)))
  const currency = (value: string | number) => money(String(value), business)
  const signed = (value: string | number) => Number(value) > 0 ? '+' + currency(value) : currency(value)
  const ask = (prompt: string) => '/assistant?' + new URLSearchParams({ draft: prompt })
  return <div className="insights-page">
    <Heading label="Workspace intelligence" title="Business Insights" subtitle="See what changed, what needs attention, and where to look next.">
      <Link className="primary" to={ask(data ? `What insights should I focus on from ${data.start} to ${data.end} compared with ${data.comparison_start} to ${data.comparison_end}?` : 'What insights should I focus on?')}><Sparkles size={17} /> Ask StockPilot AI</Link>
    </Heading>
    <form className="panel insight-filters" onSubmit={event => {
      event.preventDefault()
      const values = Object.fromEntries(new FormData(event.currentTarget)) as typeof query & { compare_start?: string; compare_end?: string }
      if (values.start > values.end || (values.compare_start && values.compare_end && values.compare_start > values.compare_end)) {
        setInvalid('Choose a start date that comes before or on the end date.'); return
      }
      setInvalid(''); setQuery(values)
    }}>
      <label>From<input type="date" name="start" required defaultValue={firstDay} /></label>
      <label>Through<input type="date" name="end" required defaultValue={lastDay} /></label>
      <label>Compare with<select value={custom ? 'custom' : 'previous'} onChange={event => setCustom(event.target.value === 'custom')}>
        <option value="previous">Previous period</option><option value="custom">Custom dates</option>
      </select></label>
      {custom && <><label>Comparison from<input type="date" name="compare_start" required /></label>
        <label>Comparison through<input type="date" name="compare_end" required /></label></>}
      <label>Trend interval<select name="group" defaultValue="week"><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option></select></label>
      <button className="primary" type="submit">Apply dates</button>
    </form>
    {(invalid || error) && <p className="notice error" role="alert">{invalid || error}</p>}
    {!data && !error && <p role="status">Loading recorded activity…</p>}
    {data && <>
      <p className="muted insights-period">Recorded {data.start} to {data.end} · Comparison {data.comparison_start} to {data.comparison_end}.
        {!data.comparable && ' The periods differ in length or include an incomplete day. Interpret changes with care.'}</p>
      <div className="insight-metrics">{data.metrics.map(item => <article className="panel" key={item.key}>
        <span className="muted">{item.label}</span>
        <strong>{item.key === 'sale_count' ? item.current : currency(item.current)}</strong>
        <small className="muted">Prior {item.key === 'sale_count' ? item.previous : currency(item.previous)}
          {item.percent !== null && <> · {Number(item.percent) > 0 ? '+' : ''}{item.percent}%</>}</small>
      </article>)}</div>
      <nav className="insight-tabs" aria-label="Insight sections">{sections.map(tab => <button type="button" key={tab}
        className={section === tab ? 'primary' : 'secondary'} aria-pressed={section === tab} onClick={() => setSection(tab)}>{tab}</button>)}</nav>
      {section === 'Priorities' && <>
        <section className="insight-recommendations"><h2>Recommended next actions</h2>
          {!data.recommendations.length && <div className="panel insights-panel"><PackageSearch size={24} /><p>There are no priority alerts supported by these records. As activity builds up, recommendations will appear here.</p></div>}
          <div className="insight-grid">{data.recommendations.map(item => <article className="panel insights-panel insight-recommendation" key={item.key}>
            <span className={'insight-priority priority-' + item.priority}>{['', 'High priority', 'Review soon', 'Monitor'][item.priority]}</span>
            <h3>{item.title}</h3><p><strong>Recorded:</strong> {item.evidence}</p>
            {item.estimate && <p className="insight-estimate">{item.estimate}</p>}
            <Link className="assistant-source" to={item.link}>{item.action} <ArrowUpRight size={15} /></Link>
          </article>)}</div>
        </section>
        <section className="panel insights-panel forecast-panel"><ChartNoAxesCombined size={22} /><div>
          <h2>Weekly net sales forecast</h2>
          {data.forecast.available && <><strong className="forecast-figure">{currency(data.forecast.estimate)}</strong> <span className="pill">Estimate</span>{data.forecast.history?.length > 0 && <ForecastPlot series={data.forecast.history} estimate={data.forecast.estimate} />}
            <p>{data.forecast.start} to {data.forecast.end} · Observed range {currency(data.forecast.low)} to {currency(data.forecast.high)}</p>
            <small className="muted">History from {data.forecast.history_start} to {data.forecast.history_end}</small></>}
          <p className="muted">{data.forecast.note}</p>
        </div></section>
      </>}
      {section === 'Performance' && <>
        <DataTable caption="What moved operating profit" headers={['Recorded component', 'Impact']} empty="No comparable activity."
          rows={data.drivers.map(row => [row.label, signed(row.delta)])} />
        <p className="muted">These components explain the accounting change. Review the source records to identify business causes.</p>
        <Link className="assistant-source" to={ask(`Explain what drove operating profit from ${data.start} to ${data.end} compared with ${data.comparison_start} to ${data.comparison_end}`)}>Discuss this comparison <ArrowUpRight size={15} /></Link>
        {data.series.length > 1 && <div className="panel insights-panel"><Trend series={data.series} /></div>}
        <DataTable caption="Sales and expense trend" headers={['Period starts', 'Net sales', 'Operating expenses']} empty="No dated activity."
          rows={data.series.map(row => [row.date, currency(row.net_sales), currency(row.operating_expenses)])} />
        <DataTable caption="Product performance" headers={['Product', 'Net units', 'Net sales', 'Prior net sales', 'Gross profit']} empty="No product transactions in either period."
          rows={data.products.map(row => [<>{row.name}<small className="muted insight-subline">{row.sku}</small></>, quantity(row.units), currency(row.revenue), currency(row.previous_revenue), currency(row.profit)])} />
        <DataTable caption="Unusual expense entries" headers={['Category', 'Largest selected entry', 'Comparison average']} empty="No category had an entry at least three times its comparison average from at least three prior entries."
          rows={data.unusual.map(row => [row.name, currency(row.largest), currency(row.baseline)])} />
        <DataTable caption="Expense changes" headers={['Category', 'Selected', 'Comparison', 'Change']} empty="No recorded expenses in either period."
          rows={data.expenses.map(row => [row.name, currency(row.current), currency(row.previous), signed(row.delta)])} />
      </>}
      {section === 'Stock' && <>
        <p className="muted">Current balances and the last 28 complete days of demand. Suggested quantities target 14 days of demand or the reorder level, whichever is higher. Check inbound stock, availability and lead times.</p>
        <DataTable caption="Low stock and reorder estimates" headers={['Product', 'On hand', 'Reorder at', 'Selling days', 'Estimated reorder']} empty="No active tracked products at or below reorder level."
          rows={data.low.map(row => [row.name, quantity(row.stock) + ' ' + row.unit, quantity(row.reorder_at), row.selling_days, row.suggested === null ? 'Insufficient history' : quantity(row.suggested) + ' ' + row.unit])} />
        <DataTable caption="Slow-moving candidates" headers={['Product', 'On hand now', 'Selling days']} empty={data.active_days < 7 ? 'At least seven days with positive net sales are needed in the last 28 complete days.' : 'No established, in-stock products sold on at most one day.'}
          rows={data.slow.map(row => [row.name, quantity(row.stock) + ' ' + row.unit, row.selling_days])} />
      </>}
      {section === 'Payments' && <>
        <div className="panel insights-panel"><h2>Current receivables</h2><strong className="forecast-figure">{currency(data.outstanding)}</strong>
          <p className="muted">Invoice age counts days since posting. Collections are gross recorded payments during the selected period. Later payments are recorded separately from checkout.</p>
          <Link className="assistant-source" to="/customers">Open customers <ArrowUpRight size={15} /></Link>
        </div>
        <DataTable caption="Customer payment activity" headers={['Customer', 'Outstanding', 'Open sales', 'Oldest open (days)', 'Payments collected', 'Later payments', 'Latest payment']} empty="No outstanding balances or customer activity."
          rows={data.customers.map(row => [row.name, currency(row.outstanding), row.open_invoices, row.age ?? '—', currency(row.payments), row.later_payments, row.latest_payment ?? '—'])} />
      </>}
    </>}
  </div>
}

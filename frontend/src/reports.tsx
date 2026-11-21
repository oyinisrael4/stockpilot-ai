import { Activity, ArrowDownToLine, ArrowUpRight, BarChart3, Coins, PackageCheck, Printer, Receipt, Wallet } from 'lucide-react'
import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { money, quantity, tenant, useData } from './api'
import type { Business } from './api'
import { todayIn } from './finance'
import { Empty, Form, Heading, Result } from './ui'

type Metrics = {
  sale_count: number; gross_sales: string; discounts: string; sales_returns: string; refunds: string
  sales_tax: string; net_sales: string; cogs: string; gross_profit: string; gross_margin: string | null
  operating_expenses: string; operating_result: string
}
type Point = { date: string; net_sales: string; operating_expenses: string }
type Period = {
  start: string; end: string; totals: Metrics; series: Point[]
  expense_categories: { name: string; amount: string; count: number }[]
}
type RankedProduct = { id: number; name: string; unit: string; units: string }
export type FinancialReport = {
  current: Period; comparison: Period | null; outstanding: string
  inventory: { valuation: string; low_stock_count: number; low_stock: { id: number; name: string; stock: string; reorder_level: string; unit: string }[] }
  top_products: RankedProduct[]; slow_products: RankedProduct[]
}

function monthStart(date: string) { return date.slice(0, 8) + '01' }
function shiftDate(date: string, days: number) {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}
function dateLabel(date: string) {
  return new Intl.DateTimeFormat('en-NG', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${date}T00:00:00Z`))
}

function FinanceMetrics({ data, business }: { data: FinancialReport; business: Business }) {
  const totals = data.current.totals
  const previous = data.comparison?.totals
  const cards = [
    { label: 'Net sales revenue', amount: totals.net_sales, prior: previous?.net_sales, tone: 'blue', icon: Coins, note: `${totals.sale_count} posted ${totals.sale_count === 1 ? 'sale' : 'sales'}` },
    { label: 'Gross profit', amount: totals.gross_profit, prior: previous?.gross_profit, tone: 'mint', icon: Activity, note: totals.gross_margin !== null ? `${totals.gross_margin}% gross margin` : 'Gross margin unavailable' },
    { label: 'Net operating result', amount: totals.operating_result, prior: previous?.operating_result, tone: 'violet', icon: BarChart3, note: 'Gross profit less operating expenses' },
    { label: 'Operating expenses', amount: totals.operating_expenses, prior: previous?.operating_expenses, tone: 'amber', icon: Wallet, note: 'Recorded operating costs' },
  ]
  return <div className="metrics finance-metrics">{cards.map(({ label, amount, prior, tone, icon: Icon, note }) =>
    <article key={label} className={`metric ${tone}`}><span className="tile-icon"><Icon size={21} /></span><span>{label}<strong tabIndex={amount.length > 17 ? 0 : undefined} className={amount.startsWith('-') ? 'negative' : ''}>{money(amount, business)}</strong><small>{note}</small>{prior !== undefined && <small className="metric-prior">Prior <span>{money(prior, business)}</span></small>}</span></article>)}</div>
}

function Trend({ period, comparison, business, contextual = false }: { period: Period; comparison: Period | null; business: Business; contextual?: boolean }) {
  const id = useId()
  const [active, setActive] = useState<number>()
  const point = period.series[Math.min(active ?? period.series.length - 1, period.series.length - 1)]
  const all = [...period.series.flatMap(item => [item.net_sales, item.operating_expenses]), ...(comparison?.series.map(item => item.net_sales) ?? []), '0.00']
  const maximum = all.reduce((largest, value) => Number(value) > Number(largest) ? value : largest)
  const minimum = all.reduce((smallest, value) => Number(value) < Number(smallest) ? value : smallest)
  const max = Number(maximum), min = Number(minimum)
  const width = 720, left = 24, right = 696, top = 16, bottom = 162
  const x = (index: number, count: number) => left + (right - left) * index / Math.max(1, count - 1)
  const y = (value: string | number) => bottom - (bottom - top) * ((Number(value) - min) / (max - min || 1))
  const path = (values: string[]) => values.map((value, index) => `${index ? 'L' : 'M'}${x(index, values.length)},${y(value)}`).join(' ')
  const sales = period.series.map(item => item.net_sales)
  const index = active === undefined || active >= period.series.length ? period.series.length - 1 : active
  return <section className="panel trend-panel">
    <div className="panel-head"><div><h2>Sales and expense trend</h2><p>{dateLabel(period.start)} – {dateLabel(period.end)}</p></div>
      <div className="legend"><span>Net sales</span><span>Expenses</span>{comparison && <span>Comparison sales</span>}</div></div>
    <div className="trend-body">
      <div className="chart-plot">
      <div className="chart-axis" aria-label="Amount scale">{[0, 1, 2, 3, 4].map(tick => <span key={tick}>{new Intl.NumberFormat('en-NG', { style: 'currency', currency: business.currency, notation: 'compact', maximumFractionDigits: 1 }).format(max - tick * (max - min) / 4)}</span>)}</div>
      <svg viewBox={`0 0 ${width} 183`} role="img" aria-label="Net sales and operating expenses by period">
        <defs><linearGradient id={id} x2="0" y2="1"><stop stopColor="#5f73f1" stopOpacity=".28" /><stop offset="1" stopColor="#5f73f1" stopOpacity=".03" /></linearGradient></defs>
        {[0, 1, 2, 3, 4].map(tick => <line className="chart-grid" key={tick} x1={left} x2={right} y1={top + tick * (bottom - top) / 4} y2={top + tick * (bottom - top) / 4} />)}
        {sales.length > 1 && <path d={`${path(sales)} L${right},${y(0)} L${left},${y(0)} Z`} fill={`url(#${id})`} />}
        <path className="line sales-line" d={path(sales)} />
        <path className="line expense-line" d={path(period.series.map(item => item.operating_expenses))} />
        {comparison && <path className="line comparison-line" d={path(comparison.series.map(item => item.net_sales))} />}
        {point && <><line className="chart-cursor" x1={x(index, sales.length)} x2={x(index, sales.length)} y1={top} y2={bottom} />
          <circle cx={x(index, sales.length)} cy={y(point.net_sales)} r="5" fill="#4934c2" />
          <circle cx={x(index, sales.length)} cy={y(point.operating_expenses)} r="4" fill="#168290" /></>}
      </svg>
      </div>
      <div className="chart-dates" aria-hidden="true"><span>{dateLabel(period.series[0].date)}</span>{period.series.length > 1 && <span>{dateLabel(period.series.at(-1)!.date)}</span>}</div>
      {point && <div className="chart-inspector">
        <label>Inspect period<select value={index} onChange={event => setActive(Number(event.target.value))}>{period.series.map((item, index) => <option key={item.date} value={index}>{dateLabel(item.date)}</option>)}</select></label>
        <p><strong>{money(point.net_sales, business)}</strong> net sales · <strong>{money(point.operating_expenses, business)}</strong> expenses</p>
      </div>}
    </div>
    {contextual && <div className="chart-context"><div><strong>Ask about this period</strong><p>{dateLabel(period.start)} to {dateLabel(period.end)}</p></div>
      <Link className="secondary" to={'/assistant?' + new URLSearchParams({ draft: `Explain what drove operating profit from ${period.start} to ${period.end}${comparison ? ` compared with ${comparison.start} to ${comparison.end}` : ''}` })}>What changed? <ArrowUpRight size={15} /></Link></div>}
  </section>
}

export function ExpenseBreakdown({ period, business }: { period: Period; business: Business }) {
  const total = Number(period.totals.operating_expenses)
  return <section className="panel breakdown">
    <div className="panel-head"><div><h2>Expense breakdown</h2><p>{money(period.totals.operating_expenses, business)} in the selected date range</p></div><Receipt size={20} /></div>
    {period.expense_categories.length ? <div className="expense-bars">
      {period.expense_categories.map(item => <div key={item.name}><div className="line-head"><strong>{item.name}</strong><span>{money(item.amount, business)}</span></div>
        <progress aria-label={item.name} value={Number(item.amount)} max={total} /><small>{item.count} {item.count === 1 ? 'expense' : 'expenses'}</small></div>)}
    </div> : <Empty title="No expenses in this period" text="Recorded operating costs will appear here." />}
  </section>
}

const rows: { label: string; key: keyof Metrics }[] = [
  { label: 'Posted sales (count)', key: 'sale_count' }, { label: 'Gross sales', key: 'gross_sales' }, { label: 'Discounts', key: 'discounts' },
  { label: 'Sales returns excluding tax', key: 'sales_returns' }, { label: 'Net sales revenue', key: 'net_sales' },
  { label: 'Tax collected, net of returns', key: 'sales_tax' }, { label: 'Cash and other tender refunds', key: 'refunds' },
  { label: 'Cost of goods sold', key: 'cogs' }, { label: 'Gross profit', key: 'gross_profit' }, { label: 'Gross margin', key: 'gross_margin' },
  { label: 'Operating expenses', key: 'operating_expenses' }, { label: 'Net operating result', key: 'operating_result' },
]

function FinancialTable({ data, business }: { data: FinancialReport; business: Business }) {
  function format(key: keyof Metrics, value: Metrics[keyof Metrics]) {
    if (value === null) return '—'
    return key === 'sale_count' ? String(value) : key === 'gross_margin' ? `${value}%` : money(String(value), business)
  }
  return <section className="panel"><div className="panel-head"><div><h2>Period performance</h2><p>Returns and voids are recorded on their reversal date.</p></div></div>
    <div className="table-scroll"><table><thead><tr><th>Metric</th><th>{data.current.start} to {data.current.end}</th>{data.comparison && <th>{data.comparison.start} to {data.comparison.end}</th>}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.key}><td><strong>{row.label}</strong></td><td>{format(row.key, data.current.totals[row.key])}</td>{data.comparison && <td>{format(row.key, data.comparison.totals[row.key])}</td>}</tr>)}</tbody></table></div>
    <p className="report-note">Net sales deduct discounts and returns, excluding tax. Gross profit deducts cost of goods sold and reverses cost for restocked items. Net operating result also deducts recorded operating expenses. Financing, depreciation, and income tax are outside this report.</p>
  </section>
}

function ProductRanking({ title, products, empty }: { title: string; products: RankedProduct[]; empty: string }) {
  return <section className="panel"><div className="panel-head"><div><h2>{title}</h2><p>Net quantities for active products in the selected period.</p></div></div>
    {products.length ? <ol className="rank-list">{products.map(product => <li key={product.id}><span>{product.name}</span><strong>{quantity(product.units)} {product.unit}</strong></li>)}</ol> : <Empty title={empty} text="Rankings use workspace sales and returns." />}
  </section>
}

function LiveInventory({ data, business }: { data: FinancialReport; business: Business }) {
  return <section className="panel"><div className="panel-head"><div><h2>Current stock and receivables</h2><p>Live balances across the workspace.</p></div><PackageCheck size={22} /></div>
    <dl className="live-balances"><div><dt>Inventory valuation</dt><dd>{money(data.inventory.valuation, business)}</dd></div>
      <div><dt>Outstanding receivables</dt><dd>{money(data.outstanding, business)}</dd></div></dl>
    <div className="panel-head"><div><h2>Low stock</h2><p>{data.inventory.low_stock_count} at or below reorder level</p></div><Link to="/inventory?low=1">View inventory <ArrowUpRight size={15} /></Link></div>
    {data.inventory.low_stock.length > 0 && <ul className="rank-list">{data.inventory.low_stock.map(item => <li key={item.id}><span>{item.name}</span><strong>{quantity(item.stock)} {item.unit}</strong></li>)}</ul>}
  </section>
}

export function DashboardFinance({ business }: { business: Business }) {
  const today = todayIn(business.timezone)
  const [window, setWindow] = useState('month')
  const start = window === 'month' ? monthStart(today) : shiftDate(today, 1 - Number(window))
  const compareEnd = shiftDate(start, -1)
  const days = Math.round((Date.parse(today) - Date.parse(start)) / 86_400_000)
  const compareStart = shiftDate(compareEnd, -days)
  const result = useData<FinancialReport>(tenant(business, 'reports/?' + new URLSearchParams({
    start, end: today, compare_start: compareStart, compare_end: compareEnd,
  })))
  return <section className="dashboard-finance" aria-label="Financial overview">
    <div className="section-heading"><div><h2>Financial performance</h2><p className="muted">{dateLabel(start)} to {dateLabel(today)} · Prior {dateLabel(compareStart)} to {dateLabel(compareEnd)}</p></div>
      <div className="actions"><select aria-label="Overview reporting period" value={window} onChange={event => setWindow(event.target.value)}>
        <option value="month">Month to date</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option>
      </select><Link to="/reports" className="secondary">Open financial reports <ArrowUpRight size={16} /></Link></div>
    </div>
    <Result {...result} retry={result.refresh}>{result.data && <>
      <FinanceMetrics data={result.data} business={business} />
      <div className="report-grid">
        <Trend key={start} period={result.data.current} comparison={result.data.comparison} business={business} contextual />
        <LiveInventory data={result.data} business={business} />
      </div>
    </>}</Result>
  </section>
}

type Filters = { start: string; end: string; group: 'day' | 'week' | 'month'; compare_start: string; compare_end: string }

export function Reports({ business }: { business: Business }) {
  const today = todayIn(business.timezone)
  const [filters, setFilters] = useState<Filters>({ start: monthStart(today), end: today, group: 'day', compare_start: '', compare_end: '' })
  const [compare, setCompare] = useState(false)
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString()
  const result = useData<FinancialReport>(tenant(business, `reports/?${query}`))
  function preset(kind: 'day' | 'week' | 'month') {
    setFilters({ start: kind === 'day' ? today : kind === 'week' ? shiftDate(today, -6) : monthStart(today),
      end: today, group: 'day', compare_start: '', compare_end: '' })
    setCompare(false)
  }
  return <section className="report-print">
    <Heading label="Business performance" title="Reports & analytics" subtitle="Review sales, costs and stock health using recorded workspace activity.">
      {result.data && <><a className="secondary no-print" href={`/api/v1/${tenant(business, `reports/csv/?${query}`)}`}><ArrowDownToLine size={17} /> Export CSV</a>
        <button className="primary no-print" onClick={() => window.print()}><Printer size={17} /> Print / Save PDF</button></>}
    </Heading>
    <div className="panel report-filters no-print">
      <div className="actions"><button className="secondary" onClick={() => preset('day')}>Today</button><button className="secondary" onClick={() => preset('week')}>Last 7 days</button><button className="secondary" onClick={() => preset('month')}>This month</button></div>
      <Form key={query} label="Apply report dates" submit={async form => {
        const values = Object.fromEntries(form) as unknown as Filters
        if (values.start > values.end || (compare && values.compare_start > values.compare_end)) throw new Error('Each start date must be on or before its end date.')
        setFilters({ ...values, compare_start: compare ? values.compare_start : '', compare_end: compare ? values.compare_end : '' })
      }}>
        <div className="report-dates">
          <label>From<input type="date" name="start" defaultValue={filters.start} required /></label>
          <label>Through<input type="date" name="end" defaultValue={filters.end} required /></label>
          <label>Group chart by<select name="group" defaultValue={filters.group}><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></label>
        </div>
        <label className="check"><input type="checkbox" checked={compare} onChange={event => setCompare(event.target.checked)} /> Compare another period</label>
        {compare && <div className="report-dates">
          <label>Comparison from<input type="date" name="compare_start" defaultValue={filters.compare_start || shiftDate(filters.start, -30)} required /></label>
          <label>Comparison through<input type="date" name="compare_end" defaultValue={filters.compare_end || shiftDate(filters.end, -30)} required /></label>
        </div>}
      </Form>
    </div>
    <Result {...result} retry={result.refresh}>{result.data && <>
      <FinanceMetrics data={result.data} business={business} />
      <div className="report-grid">
        <Trend key={query} period={result.data.current} comparison={result.data.comparison} business={business} />
        <ExpenseBreakdown period={result.data.current} business={business} />
        <FinancialTable data={result.data} business={business} />
        <aside className="overview-rail"><LiveInventory data={result.data} business={business} />
          <div className="panel overview-assist"><h2>Understand this month</h2><p>Ask what contributed to your operating result.</p><Link to="/assistant?draft=What%20drove%20operating%20profit%20this%20month%3F">Explore with StockPilot AI <ArrowUpRight size={16} /></Link></div></aside>
        <ProductRanking title="Top-selling products" products={result.data.top_products} empty="No positive net sales" />
        <ProductRanking title="Slow-moving products" products={result.data.slow_products} empty="No active products" />
      </div>
    </>}</Result>
  </section>
}

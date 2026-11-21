import { BarChart3, Bot, History, MessageSquare, Mic, PackageSearch, Plus, Send, ShoppingCart, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, tenant, useData } from './api'
import type { Business, Page } from './api'
import { InsightCard, ProposalCard } from './assistant-cards'
import type { Card, Proposal } from './assistant-cards'
import { Heading, Result } from './ui'
import { VoiceDialog } from './assistant-voice'

type Conversation = { id: number; title: string; updated_at: string }
type Exchange = { id: number; prompt: string; answer: { text: string; mode: string; card?: Card; choices?: string[] }; proposal: Proposal | null }
function visibleProposal(proposal: Proposal, update?: Proposal) {
  return update && (update.revision > proposal.revision ||
    (update.revision === proposal.revision && proposal.status === 'pending')) ? update : proposal
}
const examples = [
  { label: 'Check my profit', detail: 'Gross profit and operating result', prompt: 'How much profit did I make this month?', icon: BarChart3, tone: 'violet' },
  { label: 'Find low stock', detail: 'Products at their reorder level', prompt: 'Which products are running low?', icon: PackageSearch, tone: 'mint' },
  { label: 'Compare sales', detail: 'This month versus last month', prompt: "Compare this month's sales with last month's sales.", icon: History, tone: 'blue' },
  { label: 'Review business insights', detail: 'Ideas based on recorded activity', prompt: 'What can I do to improve my business?', icon: Sparkles, tone: 'amber' },
]

function Thread({ business, id, send, latest, pending }: {
  business: Business; id: number; send: (value: string) => void; latest?: Exchange; pending: string
}) {
  const [page, setPage] = useState(1)
  const [updates, setUpdates] = useState<Record<number, Proposal>>({})
  const list = useData<Page<Exchange>>(tenant(business, 'assistant/conversations/' + id + '/messages/?page=' + page))
  const container = useRef<HTMLDivElement>(null)
  const existing = list.data?.results ?? []
  const messages = [...(page === 1 && latest && !existing.some(item => item.id === latest.id) ? [latest] : []), ...existing].reverse()
  const lastId = messages.at(-1)?.id
  useEffect(() => {
    if (latest) { setPage(1); list.refresh() }
  }, [latest?.id, list.refresh])
  useEffect(() => {
    if (page === 1 && container.current) container.current.scrollTop = container.current.scrollHeight
  }, [lastId, pending, page])
  return <div className="chat-scroll" ref={container} aria-label="Conversation messages" tabIndex={0}>
    <Result {...list} retry={list.refresh}>
      <div className="actions chat-pagination">
        {list.data?.next && <button className="secondary" onClick={() => setPage(page + 1)}>Older messages</button>}
        {page > 1 && <button className="secondary" onClick={() => setPage(page - 1)}>Newer messages</button>}
      </div>
      {!messages.length && !pending && <div className="chat-empty"><span className="assistant-avatar"><Bot size={28} /></span><h2>Start with a business question</h2>
        <p>Ask about your workspace or prepare a transaction for review.</p></div>}
      {messages.map(exchange => <div className="chat-turn" key={exchange.id}>
        <div className="chat-user"><p>{exchange.prompt}</p></div>
        <div className="chat-response"><span className="assistant-avatar" aria-hidden="true"><Bot size={19} /></span>
          <div className="chat-answer"><div className="chat-author">StockPilot AI {exchange.answer.mode === 'demo' && <span>Demo mode</span>}{exchange.answer.mode === 'provider' && <span>AI assisted</span>}{exchange.answer.mode === 'provider_unavailable' && <span>Assistant unavailable</span>}</div>
            <p>{exchange.proposal ? 'Use the transaction card to review the current status.' : exchange.answer.text}</p>
            {exchange.answer.card && <InsightCard card={exchange.answer.card} business={business} />}
            {exchange.proposal && <ProposalCard proposal={visibleProposal(exchange.proposal, updates[exchange.proposal.id])} business={business} update={proposal => {
              if (proposal) setUpdates(items => ({ ...items, [proposal.id]: proposal }))
              else {
                setUpdates(items => Object.fromEntries(Object.entries(items).filter(([key]) => Number(key) !== exchange.proposal?.id)))
                list.refresh()
              }
            }} />}
            {exchange.id === lastId && page === 1 && exchange.answer.choices && <div className="actions chat-choices">
              {exchange.answer.choices.map(choice => <button className="secondary" key={choice} disabled={Boolean(pending)} onClick={() => send(choice)}>{choice}</button>)}</div>}
            {exchange.id === lastId && page === 1 && exchange.answer.mode === 'provider_unavailable' && <div className="actions chat-choices">
              <button className="secondary" disabled={Boolean(pending)} onClick={() => send(exchange.prompt)}>Retry with model</button>
            </div>}
          </div>
        </div>
      </div>)}
    </Result>
    {pending && page === 1 && <div className="chat-user"><p>{pending}</p></div>}
    {pending && <div className="chat-processing" role="status"><span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span> Analysing your request…</div>}
  </div>
}

export function Assistant({ business }: { business: Business }) {
  const [params, setParams] = useSearchParams()
  const id = Number(params.get('conversation')) || undefined
  const [text, setText] = useState(() => (params.get('draft') ?? '').slice(0, 2000))
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState('')
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState<{ id?: number; key: string; text: string }>()
  const [latest, setLatest] = useState<{ id: number; exchange: Exchange }>()
  const [historyOpen, showHistory] = useState(false)
  const [ideasOpen, showIdeas] = useState(true)
  const [historyPage, setHistoryPage] = useState(1)
  const [historySearch, setHistorySearch] = useState('')
  const [voiceOpen, showVoice] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const history = useData<Page<Conversation>>(tenant(business, 'assistant/conversations/?page=' + historyPage + '&search=' + encodeURIComponent(historySearch)))
  const status = useData<{ provider_enabled: boolean; provider: 'openai' | 'ollama' | null }>(tenant(business, 'assistant/status/'))
  const enabled = status.data?.provider_enabled

  function focusComposer() { requestAnimationFrame(() => input.current?.focus()) }
  function select(conversation: number) {
    setParams({ conversation: String(conversation) })
    setText(''); setError(''); setAttempt(undefined); if (window.matchMedia("(max-width: 1099px)").matches) showHistory(false)
    focusComposer()
  }
  async function create() {
    const conversation = await api<Conversation>(tenant(business, 'assistant/conversations/'), 'POST')
    setHistoryPage(1); setHistorySearch(''); history.refresh()
    return conversation.id
  }
  async function newConversation() {
    if (busy) return
    setBusy(true); setError('')
    try { select(await create()) }
    catch (problem) { setError((problem as Error).message) }
    finally { setBusy(false) }
  }
  async function send(value: string, retry = false) {
    const prompt = value.trim()
    if (!prompt || busy) return
    const key = retry && attempt ? attempt.key : crypto.randomUUID()
    let conversation = retry ? attempt?.id : id
    setBusy(true); setError(''); setPending(prompt)
    try {
      if (!conversation) {
        conversation = await create()
        setParams({ conversation: String(conversation) })
      }
      const exchange = await api<Exchange>(tenant(business, 'assistant/conversations/' + conversation + '/messages/'), 'POST', { request_id: key, text: prompt })
      setLatest({ id: conversation, exchange }); setText(''); setAttempt(undefined)
      history.refresh()
    } catch (problem) {
      setError((problem as Error).message); setAttempt({ id: conversation, key, text: prompt })
    } finally {
      setBusy(false); setPending(''); focusComposer()
    }
  }
  return <>
    <Heading label="Workspace intelligence" title="AI Assistant" subtitle="Ask about recorded activity and prepare transactions in plain language.">
      <button className="secondary history-toggle" aria-controls="assistant-history" aria-expanded={historyOpen} onClick={() => showHistory(!historyOpen)}><History size={17} /> History</button>
      <button className="secondary" aria-controls="assistant-ideas" aria-expanded={ideasOpen} onClick={() => showIdeas(!ideasOpen)}><Sparkles size={17} /> Prompts</button>
      <button className="primary" disabled={busy} onClick={newConversation}><Plus size={17} /> New conversation</button>
    </Heading>
    <div className={`assistant-layout ${historyOpen ? "with-history" : ""} ${ideasOpen ? "with-ideas" : ""}`}>
      <aside hidden={!historyOpen} id="assistant-history" className={'panel conversation-list' + (historyOpen ? ' history-open' : '')} aria-label="Conversation history">
        <div className="panel-head"><div><h2>Conversations</h2><p>Private to your account in this workspace.</p></div><History size={19} /></div>
        <div className="history-search"><input type="search" aria-label="Search conversations" placeholder="Search titles…" value={historySearch}
          onChange={event => { setHistoryPage(1); setHistorySearch(event.target.value) }} /></div>
        <Result {...history} retry={history.refresh}>
          {history.data?.results.length ? <ul>{history.data.results.map(item => <li key={item.id}>
            <button aria-current={item.id === id ? 'true' : undefined} disabled={busy} onClick={() => select(item.id)}><MessageSquare size={16} /><span>{item.title}<time dateTime={item.updated_at}>
              {new Intl.DateTimeFormat('en-NG', { day: 'numeric', month: 'short', timeZone: business.timezone }).format(new Date(item.updated_at))}
            </time></span></button>
          </li>)}</ul> : <p className="muted history-empty">{historySearch ? 'No matching conversations.' : 'Your conversations will appear here.'}</p>}
          <div className="actions history-pages">{history.data?.previous && <button className="secondary" onClick={() => setHistoryPage(historyPage - 1)}>Newer</button>}
            {history.data?.next && <button className="secondary" onClick={() => setHistoryPage(historyPage + 1)}>Older</button>}</div>
        </Result>
      </aside>
      <section className="panel assistant-chat" aria-label="StockPilot AI chat">
        <header className="chat-header"><span className="assistant-avatar"><Bot size={22} /></span><div><h2>StockPilot AI</h2>
          <p>{status.error ? 'Connection status unavailable' : enabled === undefined ? 'Checking connection…'
            : !enabled ? 'Limited demonstration mode' : 'Ask about your business records'}</p></div>
          <details className="chat-diagnostics"><summary>Connection details</summary><small>{enabled ? status.data?.provider : "Demonstration mode"}</small></details></header>
        {id ? <Thread key={id} business={business} id={id} send={send} latest={latest?.id === id ? latest.exchange : undefined} pending={pending} /> :
          <div className="chat-empty chat-welcome"><span className="assistant-avatar"><Sparkles size={34} /></span><h2>What would you like to know?</h2>
            <p>Ask about sales, spending or stock. For transaction requests, review the preview before posting.</p>
            <button className="secondary" disabled={busy} onClick={() => send('How much profit did I make this month?')}><BarChart3 size={17} /> Check month-to-date profit</button>
          </div>}
        <div className="chat-composer">
          {error && <div className="notice error" role="alert">{error} {attempt && <button className="secondary" disabled={busy} onClick={() => send(attempt.text, true)}>Retry message</button>}</div>}
          <form onSubmit={event => { event.preventDefault(); void send(text) }}>
            <textarea aria-label="Message StockPilot AI" ref={input} rows={2} placeholder="Ask about your workspace…" value={text} onChange={event => setText(event.target.value)} maxLength={2000}
              onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(text) } }} />
            <button className="icon-btn voice-button" type="button" aria-label="Voice input" aria-haspopup="dialog" disabled={busy} onClick={() => showVoice(true)}><Mic size={19} /></button>
            <button className="primary" type="submit" aria-label="Send message" disabled={busy || !text.trim()}><Send size={18} /></button>
          </form>
          <small>Enter to send · Shift+Enter for a new line</small>
        </div>
      </section>
      <aside hidden={!ideasOpen} id="assistant-ideas" className="panel assistant-suggestions" aria-label="Suggested questions">
        <div className="panel-head"><div><h2>Try asking</h2><p>Start with your own records.</p></div><Sparkles size={19} /></div>
        {examples.map(({ label, detail, prompt, icon: Icon, tone }) => <button className={'suggestion ' + tone} key={label} disabled={busy} onClick={() => send(prompt)}>
          <span className="tile-icon"><Icon size={17} /></span><span><strong>{label}</strong><small>{detail}</small></span>
        </button>)}
        <div className="assistant-tip"><ShoppingCart size={18} /><div><strong>Prepare a transaction</strong>
          <p>Try “Sell 2 WATER-75 in cash.” Use a name or SKU from your catalog.</p>
          <button className="secondary" disabled={busy} onClick={() => { setText('Sell 2 '); focusComposer() }}>Start a sale request</button></div></div>
      </aside>
    </div>
    {voiceOpen && <VoiceDialog businessId={business.id} close={() => { showVoice(false); focusComposer() }} useTranscript={value => {
      const next = text.trim() ? text.trimEnd() + '\n' + value : value
      if (next.length > 2000) return false
      setText(next); showVoice(false); focusComposer()
      return true
    }} />}
  </>
}

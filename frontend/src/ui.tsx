import { Boxes, ChevronLeft, ChevronRight, PackageOpen, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import type { Page } from './api'

export function Brand() {
  return <span className="brand"><span className="brand-mark"><Boxes size={22} /></span>StockPilot <b>AI</b></span>
}

export function Heading({ label, title, subtitle, children }: { label: string; title: string; subtitle: string; children?: ReactNode }) {
  return <header className="page-heading"><div><span className="eyebrow">{label}</span><h1>{title}</h1><p>{subtitle}</p></div>{children && <div className="actions">{children}</div>}</header>
}

export function Result({ data, error, retry, children }: { data: unknown; error?: string; retry?: () => void; children: ReactNode }) {
  if (error) return <div className="notice error" role="alert">{error} {retry && <button className="secondary" onClick={retry}>Retry</button>}</div>
  if (data === undefined) return <div className="loading skeleton" role="status"><span>Loading workspace data…</span><div aria-hidden="true"><i /><i /><i /></div></div>
  return children
}

export function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty"><span className="tile-icon"><PackageOpen size={24} /></span><h3>{title}</h3><p>{text}</p></div>
}

export function Pager<T>({ page, setPage, data }: { page: number; setPage: (page: number) => void; data?: Page<T> }) {
  if (!data) return null
  return <footer className="pager"><span>{data.count} {data.count === 1 ? 'record' : 'records'} · Page {page}</span>
    <div className="actions"><button className="icon-btn" aria-label="Previous page" disabled={!data.previous} onClick={() => setPage(page - 1)}><ChevronLeft size={17} /></button>
    <button className="icon-btn" aria-label="Next page" disabled={!data.next} onClick={() => setPage(page + 1)}><ChevronRight size={17} /></button></div></footer>
}

export function Dialog({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const element = dialog.current!
    element.showModal()
    return () => element.close()
  }, [])
  return <dialog ref={dialog} aria-label={title} onCancel={event => { event.preventDefault(); close() }}>
    <div className="dialog-head"><h2>{title}</h2><button className="icon-btn" aria-label="Close dialog" onClick={close}><X size={18} /></button></div>
    {children}
  </dialog>
}

export function Form({ children, submit, label, danger = false }: {
  children?: ReactNode; submit: (form: FormData) => Promise<void>; label: string; danger?: boolean
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  async function handle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    setError('')
    setPending(true)
    try { await submit(new FormData(event.currentTarget)) }
    catch (problem) { setError(problem instanceof Error ? problem.message : 'Could not save. Try again.') }
    finally { setPending(false) }
  }
  return <form onSubmit={handle} className="form">
    <fieldset disabled={pending}>{children}</fieldset>
    {error && <div className="notice error" role="alert">{error}</div>}
    <button className={danger ? 'danger' : 'primary'} disabled={pending}>{pending ? 'Working…' : label}</button>
  </form>
}

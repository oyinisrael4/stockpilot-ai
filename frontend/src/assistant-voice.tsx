import { Mic, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Dialog } from './ui'

const LIMIT = 2000
const SECONDS = 45
const RATE = 16000
const denied = 'Microphone permission was denied. Allow microphone access in your browser settings or return to typing.'
type Recording = { recorder: MediaRecorder; chunks: Blob[]; timer?: number }

async function toWave(blob: Blob) {
  const decoder = new OfflineAudioContext(1, 1, RATE)
  const audio = await decoder.decodeAudioData(await blob.arrayBuffer())
  const frames = Math.min(audio.length, RATE * SECONDS)
  const wav = new DataView(new ArrayBuffer(44 + frames * 2))
  const label = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i++) wav.setUint8(offset + i, value.charCodeAt(i))
  }
  label(0, 'RIFF')
  wav.setUint32(4, 36 + frames * 2, true)
  label(8, 'WAVEfmt ')
  wav.setUint32(16, 16, true)
  wav.setUint16(20, 1, true)
  wav.setUint16(22, 1, true)
  wav.setUint32(24, RATE, true)
  wav.setUint32(28, RATE * 2, true)
  wav.setUint16(32, 2, true)
  wav.setUint16(34, 16, true)
  label(36, 'data')
  wav.setUint32(40, frames * 2, true)
  const channels = Array.from({ length: audio.numberOfChannels }, (_, index) => audio.getChannelData(index))
  for (let frame = 0; frame < frames; frame++) {
    const sample = channels.reduce((sum, channel) => sum + channel[frame], 0) / channels.length
    wav.setInt16(44 + frame * 2, Math.max(-32768, Math.min(32767, Math.round(sample * 32768))), true)
  }
  return new Blob([wav.buffer], { type: 'audio/wav' })
}

function release(recording: Recording) {
  window.clearTimeout(recording.timer)
  const { recorder } = recording
  recorder.onstop = recorder.ondataavailable = recorder.onerror = null
  if (recorder.state !== 'inactive') recorder.stop()
  recorder.stream.getTracks().forEach(track => track.stop())
}

export function VoiceDialog({ businessId, provider, close, useTranscript }: {
  businessId: number; provider?: 'offline' | 'groq'; close: () => void; useTranscript: (text: string) => boolean
}) {
  const mounted = useRef(false)
  const recording = useRef<Recording | null>(null)
  const pending = useRef<AbortController | null>(null)
  const transcriptField = useRef<HTMLTextAreaElement>(null)
  const [permission, setPermission] = useState<PermissionState>()
  const [state, setState] = useState<'idle' | 'starting' | 'recording' | 'stopping' | 'transcribing'>('idle')
  const [clip, setClip] = useState<{ blob: Blob; url: string }>()
  const [draft, setDraft] = useState('')
  const [hasTranscript, setHasTranscript] = useState(false)
  const [error, setError] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const active = state !== 'idle'
  const unavailable = !window.isSecureContext ? 'Voice input needs HTTPS or localhost.'
    : !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !window.OfflineAudioContext
      ? 'Microphone recording is unavailable in this browser.' : permission === 'denied' ? denied : ''

  useEffect(() => {
    mounted.current = true
    let disposed = false
    let status: PermissionStatus | undefined
    const update = () => setPermission(status?.state)
    navigator.permissions?.query({ name: 'microphone' as PermissionName }).then(result => {
      if (!mounted.current) return
      status = result
      update()
      result.addEventListener('change', update)
    }).catch(() => { /* getUserMedia handles permission when the query is unavailable. */ })
    return () => {
      disposed = true
      mounted.current = false
      status?.removeEventListener('change', update)
      pending.current?.abort()
      if (recording.current) release(recording.current)
      recording.current = null
    }
  }, [])

  useEffect(() => () => { if (clip) URL.revokeObjectURL(clip.url) }, [clip])

  useEffect(() => { if (hasTranscript) transcriptField.current?.focus() }, [hasTranscript])

  useEffect(() => {
    if (state !== 'recording') return
    const start = performance.now()
    const timer = window.setInterval(() => setElapsed(Math.min(SECONDS, Math.floor((performance.now() - start) / 1000))), 250)
    return () => window.clearInterval(timer)
  }, [state])

  function stop(current: Recording) {
    if (recording.current !== current || current.recorder.state === 'inactive') return
    window.clearTimeout(current.timer)
    setState('stopping')
    current.recorder.stop()
    current.recorder.stream.getTracks().forEach(track => track.stop())
  }

  async function start() {
    setError('')
    setState('starting')
    let stream: MediaStream | undefined
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current) {
        stream.getTracks().forEach(track => track.stop())
        return
      }
      const recorder = new MediaRecorder(stream)
      const current: Recording = { recorder, chunks: [] }
      recording.current = current
      recorder.ondataavailable = event => { if (event.data.size) current.chunks.push(event.data) }
      recorder.onerror = () => {
        release(current)
        recording.current = null
        setState('idle')
        setError('The microphone recording failed. Try again or return to typing.')
      }
      recorder.onstop = () => {
        const blob = new Blob(current.chunks, { type: recorder.mimeType })
        release(current)
        recording.current = null
        if (blob.size) setClip({ blob, url: URL.createObjectURL(blob) })
        else setError('No audio was captured. Try recording again.')
        setState('idle')
      }
      recorder.start()
      setClip(undefined)
      setDraft('')
      setHasTranscript(false)
      setElapsed(0)
      setState('recording')
      current.timer = window.setTimeout(() => stop(current), SECONDS * 1000)
    } catch (cause) {
      stream?.getTracks().forEach(track => track.stop())
      if (!mounted.current) return
      recording.current = null
      setState('idle')
      const name = cause instanceof DOMException ? cause.name : ''
      setError(name === 'NotAllowedError' ? denied : name === 'NotFoundError' ? 'No microphone was found.'
        : 'Could not open the microphone. Check your device or return to typing.')
    }
  }

  async function convert() {
    if (!clip) return
    const controller = new AbortController()
    pending.current = controller
    setError('')
    setState('transcribing')
    try {
      const wav = await toWave(clip.blob)
      if (controller.signal.aborted) return
      const result = await api<{ text: string }>(`businesses/${businessId}/assistant/transcribe/`, 'POST', wav, controller.signal)
      if (controller.signal.aborted) return
      setDraft(result.text)
      setHasTranscript(true)
      if (!result.text) setError('No clear speech was found. Record again or type your message.')
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Transcription failed.')
    } finally {
      if (!controller.signal.aborted) setState('idle')
      pending.current = null
    }
  }

  const status = { idle: hasTranscript ? 'Review and edit your transcript.' : clip ? 'Recording ready to preview.' : 'Ready to record.',
    starting: 'Waiting for microphone access…', recording: 'Recording. Speak now.', stopping: 'Preparing audio preview…',
    transcribing: 'Transcribing on the StockPilot server…' }[state]

  return <Dialog title="Voice input" close={close}>
    <div className="voice-dialog">
      <p className="muted">Record up to 45 seconds in English. Audio stays in this tab until you select Transcribe. {provider === 'groq' ? 'Transcribe sends this clip through StockPilot to Groq Cloud speech recognition. Avoid private information.' : provider === 'offline' ? 'StockPilot processes it on its server using offline Whisper without a cloud speech service.' : 'Check Connection details for the server speech provider before submitting sensitive audio.'}</p>
      {unavailable ? <p className="notice error" role="alert">{unavailable}</p> : <p className="voice-state" role="status">{status}</p>}
      {state === 'recording' && <div className="recording-meter" aria-hidden="true"><span /> <strong>0:{String(elapsed).padStart(2, '0')}</strong> / 0:45</div>}
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="actions">
        {state === 'recording'
          ? <button type="button" className="primary" onClick={() => { if (recording.current) stop(recording.current) }}><Square size={16} /> Stop recording</button>
          : <button type="button" className="secondary" disabled={active || Boolean(unavailable)} onClick={start}><Mic size={17} /> {clip ? 'Record again' : 'Start recording'}</button>}
        <button type="button" className="secondary" onClick={close}>{active || clip ? 'Discard recording' : 'Back to typing'}</button>
      </div>
      {clip && <div className="voice-preview">
        <span>Audio preview</span>
        <audio controls src={clip.url} aria-label="Audio preview" />
        {!hasTranscript && <button type="button" className="primary" disabled={active} onClick={convert}>
          {state === 'transcribing' ? 'Transcribing…' : 'Transcribe'}
        </button>}
      </div>}
      {hasTranscript && <label>Transcript<textarea ref={transcriptField} rows={4} maxLength={LIMIT} value={draft} onChange={event => setDraft(event.target.value)} /></label>}
      <button type="button" className="primary" disabled={active || !draft.trim()} onClick={() => {
        if (!useTranscript(draft.trim())) setError('Shorten the transcript or clear your draft to stay within 2,000 characters.')
      }}>Use transcript</button>
      <small>Review the text in chat, then send it when you’re ready.</small>
    </div>
  </Dialog>
}

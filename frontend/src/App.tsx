import { useEffect, useMemo, useRef, useState, type MouseEvent, type WheelEvent } from 'react'
import './App.css'

type TabKey = 'settings' | 'ingest' | 'traces' | 'steps' | 'admin' | 'testing'
type TraceStatus = 'success' | 'error' | 'partial'
type TraceEnvironment = 'prod' | 'staging' | 'dev' | 'critical'

type TraceSummary = {
  trace_id: string
  tenant_id: string
  environment: TraceEnvironment
  status: TraceStatus
  started_at: string
  ended_at?: string | null
  step_count: number
}

type StepSummary = {
  trace_id: string
  step_id: string
  step_type: string
  tenant_id: string
  environment: TraceEnvironment
  trace_started_at: string
  error?: string | null
}

type TenantLimits = {
  tenant_id: string
  ingest_rate_limit_rps: number
  ingest_daily_trace_quota: number
}

type ApiError = { status: number; detail: string }
type ConnectionState = 'unknown' | 'connected' | 'disconnected'
type TraceStep = {
  step_id: string
  type: string
  parent_step_id: string | null
  error: string | null
  metadata: Record<string, unknown>
}
type TraceEdge = { from: string; to: string }
type VisualNode = {
  id: string
  type: string
  hasError: boolean
  x: number
  y: number
}
type PersistedUiState = {
  baseUrl?: string
  tab?: TabKey
  traceLimit?: number
}
const UI_STATE_KEY = 'rca_ui_state_v1'

function formatRequestError(e: unknown): string {
  if (e && typeof e === 'object' && 'detail' in e && typeof (e as ApiError).detail === 'string') {
    return (e as ApiError).detail
  }
  if (e instanceof Error) {
    const msg = e.message
    if (msg === 'Failed to fetch' || msg === 'Load failed') {
      return (
        'Cannot reach the API (connection failed or timed out). ' +
        'Start the FastAPI server from backend/ (see backend/README.md), then run curl http://127.0.0.1:8000/health in a terminal. ' +
        'If you use remote SSH / Codespaces, 127.0.0.1 in the browser is your local machine — use port forwarding or change Base URL to the API you can reach.'
      )
    }
    return msg
  }
  return String(e)
}

function toIso(d: Date): string {
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

function randomTraceId(): string {
  return crypto.randomUUID()
}

function buildTrace(
  tenantId: string,
  status: TraceStatus,
  steps: Array<Record<string, unknown>>,
  environment: TraceEnvironment = 'prod',
): Record<string, unknown> {
  const started = new Date()
  const ended = new Date(started.getTime() + 1200)
  return {
    schema_version: '1.0',
    trace_id: randomTraceId(),
    tenant_id: tenantId,
    environment,
    started_at: toIso(started),
    ended_at: toIso(ended),
    status,
    steps,
    edges: [],
  }
}

async function parseResponse<T>(res: Response): Promise<T> {
  const raw = await res.text()
  const payload = raw ? JSON.parse(raw) : {}
  if (!res.ok) {
    const detail = (payload as { detail?: string }).detail ?? `Request failed (${res.status})`
    throw { status: res.status, detail } as ApiError
  }
  return payload as T
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null
}

function extractTraceSteps(traceDetail: Record<string, unknown> | null): TraceStep[] {
  if (!traceDetail) return []
  const stepsRaw = traceDetail.steps
  if (!Array.isArray(stepsRaw)) return []
  const out: TraceStep[] = []
  for (const raw of stepsRaw) {
    const rec = asRecord(raw)
    if (!rec) continue
    const stepId = String(rec.step_id ?? '').trim()
    if (!stepId) continue
    out.push({
      step_id: stepId,
      type: String(rec.type ?? 'unknown'),
      parent_step_id: rec.parent_step_id ? String(rec.parent_step_id) : null,
      error: rec.error ? String(rec.error) : null,
      metadata: asRecord(rec.metadata) ?? {},
    })
  }
  return out
}

function extractTraceEdges(traceDetail: Record<string, unknown> | null, steps: TraceStep[]): TraceEdge[] {
  const edges: TraceEdge[] = []
  const seen = new Set<string>()
  const stepIds = new Set(steps.map((s) => s.step_id))
  const pushEdge = (from: string, to: string): void => {
    if (!from || !to || !stepIds.has(from) || !stepIds.has(to)) return
    const k = `${from}=>${to}`
    if (seen.has(k)) return
    seen.add(k)
    edges.push({ from, to })
  }
  for (const s of steps) {
    if (s.parent_step_id) pushEdge(s.parent_step_id, s.step_id)
  }
  const edgesRaw = traceDetail?.edges
  if (Array.isArray(edgesRaw)) {
    for (const e of edgesRaw) {
      const rec = asRecord(e)
      if (!rec) continue
      const from = String(rec.from_step_id ?? rec.from ?? rec.source ?? '').trim()
      const to = String(rec.to_step_id ?? rec.to ?? rec.target ?? '').trim()
      if (from && to) pushEdge(from, to)
    }
  }
  return edges
}

function computeNodeDepths(steps: TraceStep[], edges: TraceEdge[]): Map<string, number> {
  const parents = new Map<string, string[]>()
  const stepIds = steps.map((s) => s.step_id)
  for (const id of stepIds) parents.set(id, [])
  for (const e of edges) {
    const bucket = parents.get(e.to)
    if (bucket) bucket.push(e.from)
  }
  const memo = new Map<string, number>()
  const visiting = new Set<string>()
  const depthOf = (id: string): number => {
    const cached = memo.get(id)
    if (cached !== undefined) return cached
    if (visiting.has(id)) return 0
    visiting.add(id)
    const p = parents.get(id) ?? []
    const depth = p.length ? Math.max(...p.map(depthOf)) + 1 : 0
    visiting.delete(id)
    memo.set(id, depth)
    return depth
  }
  for (const id of stepIds) depthOf(id)
  return memo
}

function buildVisualNodes(steps: TraceStep[], edges: TraceEdge[]): VisualNode[] {
  const depths = computeNodeDepths(steps, edges)
  const rowsByDepth = new Map<number, number>()
  return steps.map((step) => {
    const depth = depths.get(step.step_id) ?? 0
    const row = rowsByDepth.get(depth) ?? 0
    rowsByDepth.set(depth, row + 1)
    return {
      id: step.step_id,
      type: step.type,
      hasError: Boolean(step.error),
      x: 120 + depth * 180,
      y: 60 + row * 110,
    }
  })
}

function formatLatencyMs(metadata: Record<string, unknown>): string {
  const raw = metadata.latency_ms
  const n = typeof raw === 'number' ? raw : Number(raw)
  return Number.isFinite(n) && n >= 0 ? `${Math.round(n)} ms` : '-'
}

function App() {
  const [tab, setTab] = useState<TabKey>(() => {
    if (typeof window === 'undefined') return 'traces'
    try {
      const raw = window.localStorage.getItem(UI_STATE_KEY)
      if (!raw) return 'traces'
      const parsed = JSON.parse(raw) as PersistedUiState
      return parsed.tab ?? 'traces'
    } catch {
      return 'traces'
    }
  })
  const [baseUrl, setBaseUrl] = useState(() => {
    if (typeof window === 'undefined') return 'http://127.0.0.1:8000'
    try {
      const raw = window.localStorage.getItem(UI_STATE_KEY)
      if (!raw) return 'http://127.0.0.1:8000'
      const parsed = JSON.parse(raw) as PersistedUiState
      return parsed.baseUrl ?? 'http://127.0.0.1:8000'
    } catch {
      return 'http://127.0.0.1:8000'
    }
  })
  const [tenantId, setTenantId] = useState('org_demo')
  const [apiKey, setApiKey] = useState('')
  const [jwtToken, setJwtToken] = useState('')
  const [adminToken, setAdminToken] = useState('')

  const [toast, setToast] = useState('')
  const [error, setError] = useState('')
  const [health, setHealth] = useState('unknown')
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('unknown')
  const [lastConnectedAt, setLastConnectedAt] = useState<string>('')
  const toastTimerRef = useRef<number | null>(null)

  const [traceList, setTraceList] = useState<TraceSummary[]>([])
  const [traceLimit, setTraceLimit] = useState(() => {
    if (typeof window === 'undefined') return 25
    try {
      const raw = window.localStorage.getItem(UI_STATE_KEY)
      if (!raw) return 25
      const parsed = JSON.parse(raw) as PersistedUiState
      const val = Number(parsed.traceLimit ?? 25)
      return Number.isFinite(val) && val > 0 ? val : 25
    } catch {
      return 25
    }
  })
  const [traceIdLookup, setTraceIdLookup] = useState('')
  const [traceEnvironment, setTraceEnvironment] = useState<TraceEnvironment>('prod')
  const [traceDetail, setTraceDetail] = useState<Record<string, unknown> | null>(null)
  const [diagnosis, setDiagnosis] = useState<Record<string, unknown> | null>(null)
  const [selectedStepId, setSelectedStepId] = useState('')
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [lastPointer, setLastPointer] = useState<{ x: number; y: number } | null>(null)
  const graphViewportRef = useRef<HTMLDivElement | null>(null)
  const timelineRef = useRef<HTMLOListElement | null>(null)
  const zoomRef = useRef(1)
  const panRef = useRef({ x: 0, y: 0 })
  const panDragRef = useRef<{ active: boolean; startX: number; startY: number; startPanX: number; startPanY: number }>({
    active: false,
    startX: 0,
    startY: 0,
    startPanX: 0,
    startPanY: 0,
  })

  const [steps, setSteps] = useState<StepSummary[]>([])
  const [stepsType, setStepsType] = useState('')
  const [stepsDays, setStepsDays] = useState(7)
  const [stepsErrorOnly, setStepsErrorOnly] = useState<boolean | null>(true)

  const [adminTenant, setAdminTenant] = useState('org_demo')
  const [limits, setLimits] = useState<TenantLimits | null>(null)
  const [limitRps, setLimitRps] = useState(0)
  const [limitQuota, setLimitQuota] = useState(0)

  const [singleTraceBody, setSingleTraceBody] = useState(
    JSON.stringify(buildTrace('org_demo', 'success', []), null, 2),
  )
  const [batchBody, setBatchBody] = useState(
    JSON.stringify(
      {
        traces: [
          buildTrace('org_demo', 'success', []),
          buildTrace('org_demo', 'error', [
            { step_id: 's1', type: 'tool_call', input: { tool: 'search' }, output: {}, error: 'timeout', metadata: { latency_ms: 900 } },
          ]),
        ],
      },
      null,
      2,
    ),
  )

  const authSummary = useMemo(() => {
    if (jwtToken.trim()) return 'JWT bearer auth'
    if (apiKey.trim()) return 'API key auth'
    return 'X-Tenant-ID dev auth'
  }, [apiKey, jwtToken])

  const traceSteps = useMemo(() => extractTraceSteps(traceDetail), [traceDetail])
  const traceEdges = useMemo(() => extractTraceEdges(traceDetail, traceSteps), [traceDetail, traceSteps])
  const visualNodes = useMemo(() => buildVisualNodes(traceSteps, traceEdges), [traceSteps, traceEdges])
  const graphCanvas = useMemo(() => {
    const width = Math.max(680, ...visualNodes.map((n) => n.x + 160))
    const height = Math.max(240, ...visualNodes.map((n) => n.y + 110))
    return { width, height }
  }, [visualNodes])
  const graphBounds = useMemo(() => {
    if (!visualNodes.length) return { minX: 0, minY: 0, width: 680, height: 220 }
    const minX = Math.min(...visualNodes.map((n) => n.x))
    const minY = Math.min(...visualNodes.map((n) => n.y))
    const maxX = Math.max(...visualNodes.map((n) => n.x + 80))
    const maxY = Math.max(...visualNodes.map((n) => n.y + 48))
    return { minX, minY, width: maxX - minX, height: maxY - minY }
  }, [visualNodes])
  const visualNodeById = useMemo(() => {
    const m = new Map<string, VisualNode>()
    for (const n of visualNodes) m.set(n.id, n)
    return m
  }, [visualNodes])
  const selectedStep = useMemo(() => traceSteps.find((s) => s.step_id === selectedStepId) ?? null, [traceSteps, selectedStepId])

  useEffect(() => {
    if (!traceSteps.length) {
      setSelectedStepId('')
      return
    }
    setSelectedStepId((prev) => (prev && traceSteps.some((s) => s.step_id === prev) ? prev : traceSteps[0].step_id))
  }, [traceSteps])

  function centerGraphToFit(): void {
    const viewport = graphViewportRef.current
    if (!viewport || !visualNodes.length) return
    viewport.scrollLeft = 0
    viewport.scrollTop = 0
    const vw = Math.max(240, viewport.clientWidth)
    const vh = Math.max(200, viewport.clientHeight)
    const pad = 24
    const scaleX = (vw - pad * 2) / Math.max(1, graphBounds.width)
    const scaleY = (vh - pad * 2) / Math.max(1, graphBounds.height)
    const fitted = Math.min(scaleX, scaleY)
    const nextZoom = Math.max(0.45, Math.min(2.4, fitted))
    const x = (vw - graphBounds.width * nextZoom) / 2 - graphBounds.minX * nextZoom
    const y = (vh - graphBounds.height * nextZoom) / 2 - graphBounds.minY * nextZoom
    setZoom(nextZoom)
    setPan({ x, y })
  }

  useEffect(() => {
    if (!visualNodes.length) return
    requestAnimationFrame(() => {
      requestAnimationFrame(() => centerGraphToFit())
    })
    // Fit whenever graph topology changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visualNodes.length, graphCanvas.width, graphCanvas.height, graphBounds.minX, graphBounds.minY, graphBounds.width, graphBounds.height])

  useEffect(() => {
    const viewport = graphViewportRef.current
    if (!viewport) return
    const observer = new ResizeObserver(() => centerGraphToFit())
    observer.observe(viewport)
    return () => observer.disconnect()
    // Keep graph centered when viewport size changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visualNodes.length, graphCanvas.width, graphCanvas.height, graphBounds.minX, graphBounds.minY, graphBounds.width, graphBounds.height])

  useEffect(() => {
    zoomRef.current = zoom
    panRef.current = pan
  }, [zoom, pan])

  function zoomTo(targetZoom: number, anchor?: { x: number; y: number }): void {
    const viewport = graphViewportRef.current
    if (!viewport) return
    const rect = viewport.getBoundingClientRect()
    const vx = anchor?.x ?? rect.width / 2
    const vy = anchor?.y ?? rect.height / 2
    const graphX = (vx - panRef.current.x) / zoomRef.current
    const graphY = (vy - panRef.current.y) / zoomRef.current
    const nextZoom = Math.max(0.45, Math.min(2.4, targetZoom))
    setZoom(nextZoom)
    setPan({
      x: vx - graphX * nextZoom,
      y: vy - graphY * nextZoom,
    })
  }

  function centerGraphOnStep(stepId: string): void {
    const viewport = graphViewportRef.current
    const node = visualNodeById.get(stepId)
    if (!viewport || !node) return
    const vw = Math.max(240, viewport.clientWidth)
    const vh = Math.max(200, viewport.clientHeight)
    const nodeCx = node.x + 40
    const nodeCy = node.y + 24
    const currentZoom = zoomRef.current
    setPan({
      x: vw / 2 - nodeCx * currentZoom,
      y: vh / 2 - nodeCy * currentZoom,
    })
  }

  function resetViewport(): void {
    centerGraphToFit()
  }

  function onGraphWheel(e: WheelEvent<HTMLDivElement>): void {
    e.preventDefault()
    e.stopPropagation()
    const factor = Math.exp(-e.deltaY * 0.0015)
    const targetZoom = zoomRef.current * factor
    const rect = e.currentTarget.getBoundingClientRect()
    zoomTo(targetZoom, { x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  function onGraphMouseDown(e: MouseEvent<HTMLDivElement>): void {
    panDragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
    }
  }

  function onGraphMouseMove(e: MouseEvent<HTMLDivElement>): void {
    const rect = e.currentTarget.getBoundingClientRect()
    setLastPointer({ x: e.clientX - rect.left, y: e.clientY - rect.top })
    if (!panDragRef.current.active) return
    const dx = e.clientX - panDragRef.current.startX
    const dy = e.clientY - panDragRef.current.startY
    setPan({
      x: panDragRef.current.startPanX + dx,
      y: panDragRef.current.startPanY + dy,
    })
  }

  function onGraphMouseUp(): void {
    panDragRef.current.active = false
  }

  useEffect(() => {
    if (!selectedStepId || !timelineRef.current) return
    const el = timelineRef.current.querySelector<HTMLElement>(`[data-step-id="${selectedStepId}"]`)
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selectedStepId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const data: PersistedUiState = {
      baseUrl,
      tab,
      traceLimit,
    }
    window.localStorage.setItem(UI_STATE_KEY, JSON.stringify(data))
  }, [baseUrl, tab, traceLimit])

  useEffect(() => {
    void checkHealth(false)
    // Run once on initial app load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function apiFetch<T>(path: string, init?: RequestInit, includeAdminToken = false): Promise<T> {
    setError('')
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (jwtToken.trim()) headers.Authorization = `Bearer ${jwtToken.trim()}`
    else if (apiKey.trim()) headers['X-API-Key'] = apiKey.trim()
    else headers['X-Tenant-ID'] = tenantId.trim()
    if (includeAdminToken && adminToken.trim()) headers['X-Admin-Token'] = adminToken.trim()
    const res = await fetch(`${baseUrl}${path}`, { ...init, headers })
    return parseResponse<T>(res)
  }

  function notify(message: string): void {
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current)
    }
    setToast(message)
    toastTimerRef.current = window.setTimeout(() => {
      setToast('')
      toastTimerRef.current = null
    }, 3200)
  }

  async function runBusy(action: string, fn: () => Promise<void>): Promise<void> {
    if (busyAction !== null) return
    setBusyAction(action)
    try {
      await fn()
    } finally {
      setBusyAction(null)
    }
  }

  async function checkHealth(notifyOnSuccess = true): Promise<void> {
    try {
      const res = await fetch(`${baseUrl}/health`)
      const payload = await parseResponse<{ status: string }>(res)
      setHealth(payload.status)
      setConnectionState('connected')
      if (notifyOnSuccess) {
        notify('Health check successful')
      }
    } catch (e) {
      setHealth('down')
      setConnectionState('disconnected')
      setError(formatRequestError(e))
    }
  }

  async function connectBackend(): Promise<void> {
    await checkHealth(false)
    setLastConnectedAt(new Date().toLocaleString())
    notify('Connected')
  }

  async function refreshTraces(): Promise<void> {
    try {
      const payload = await apiFetch<{ items: TraceSummary[] }>(`/v1/traces?limit=${traceLimit}&offset=0`)
      setTraceList(payload.items)
      notify(`Loaded ${payload.items.length} traces`)
    } catch (e) {
      setError(formatRequestError(e))
    }
  }

  async function ingestSingleTrace(): Promise<void> {
    try {
      const data = JSON.parse(singleTraceBody)
      await apiFetch('/v1/traces', { method: 'POST', body: JSON.stringify(data) })
      notify('Single trace sent')
      await refreshTraces()
    } catch (e) {
      if (e instanceof SyntaxError) return setError('Invalid JSON in single trace body')
      setError(formatRequestError(e))
    }
  }

  async function ingestBatch(): Promise<void> {
    try {
      const data = JSON.parse(batchBody)
      await apiFetch('/v1/traces/batch', { method: 'POST', body: JSON.stringify(data) })
      notify('Batch traces sent')
      await refreshTraces()
    } catch (e) {
      if (e instanceof SyntaxError) return setError('Invalid JSON in batch body')
      setError(formatRequestError(e))
    }
  }

  async function fetchTraceDetailFor(
    traceId: string,
    env: TraceEnvironment,
    opts?: { notifyOnSuccess?: boolean },
  ): Promise<void> {
    try {
      const t = await apiFetch<Record<string, unknown>>(`/v1/traces/${traceId}?environment=${env}`)
      const d = await apiFetch<Record<string, unknown>>(`/v1/traces/${traceId}/diagnosis?environment=${env}`)
      setTraceDetail(t)
      setDiagnosis(d)
      if (opts?.notifyOnSuccess) {
        notify('Trace and diagnosis loaded')
      }
    } catch (e) {
      setError(formatRequestError(e))
      setTraceDetail(null)
      setDiagnosis(null)
    }
  }

  async function fetchTraceDetail(): Promise<void> {
    if (!traceIdLookup.trim()) return setError('Trace ID is required')
    await fetchTraceDetailFor(traceIdLookup.trim(), traceEnvironment, { notifyOnSuccess: true })
  }

  async function refreshSteps(): Promise<void> {
    try {
      const q = new URLSearchParams()
      q.set('days', String(stepsDays))
      q.set('limit', '100')
      if (stepsType.trim()) q.set('step_type', stepsType.trim().toLowerCase())
      if (stepsErrorOnly !== null) q.set('has_error', String(stepsErrorOnly))
      const payload = await apiFetch<{ items: StepSummary[] }>(`/v1/traces/steps?${q.toString()}`)
      setSteps(payload.items)
      notify(`Loaded ${payload.items.length} step records`)
    } catch (e) {
      setError(formatRequestError(e))
    }
  }

  async function fetchLimits(): Promise<void> {
    if (!adminTenant.trim()) return setError('Admin tenant is required')
    try {
      const payload = await apiFetch<TenantLimits>(`/v1/admin/tenants/${adminTenant.trim()}/limits`, undefined, true)
      setLimits(payload)
      setLimitRps(payload.ingest_rate_limit_rps)
      setLimitQuota(payload.ingest_daily_trace_quota)
      notify('Fetched admin limits')
    } catch (e) {
      setError(formatRequestError(e))
    }
  }

  async function saveLimits(): Promise<void> {
    if (!adminTenant.trim()) return setError('Admin tenant is required')
    try {
      const payload = await apiFetch<TenantLimits>(
        `/v1/admin/tenants/${adminTenant.trim()}/limits`,
        { method: 'PUT', body: JSON.stringify({ ingest_rate_limit_rps: Math.max(0, limitRps), ingest_daily_trace_quota: Math.max(0, limitQuota) }) },
        true,
      )
      setLimits(payload)
      notify('Saved tenant limits')
    } catch (e) {
      setError(formatRequestError(e))
    }
  }

  async function generateScenario(kind: 'minimal' | 'step_error' | 'empty_retrieval' | 'rag' | 'batch'): Promise<void> {
    const tenant = tenantId.trim()
    if (!tenant) return setError('Tenant ID is required')
    try {
      if (kind === 'batch') {
        await apiFetch('/v1/traces/batch', {
          method: 'POST',
          body: JSON.stringify({
            traces: [
              buildTrace(tenant, 'success', []),
              buildTrace(tenant, 'error', [{ step_id: 's1', type: 'llm_call', input: {}, output: {}, error: 'simulated error', metadata: { latency_ms: 250 } }]),
              buildTrace(tenant, 'success', [{ step_id: 's1', type: 'retrieval', input: { query: 'example' }, output: { chunks: [] }, metadata: { latency_ms: 12 } }]),
            ],
          }),
        })
      } else {
        let stepsPayload: Array<Record<string, unknown>> = []
        if (kind === 'step_error') {
          stepsPayload = [{ step_id: 's1', type: 'llm_call', input: { messages: [] }, output: {}, error: '429 rate limit exceeded', metadata: { latency_ms: 200, model: 'gpt-4' } }]
        } else if (kind === 'empty_retrieval') {
          stepsPayload = [{ step_id: 's1', type: 'retrieval', input: { query: 'anything' }, output: { chunks: [] }, error: null, metadata: { latency_ms: 12 } }]
        } else if (kind === 'rag') {
          stepsPayload = [
            { step_id: 's1', type: 'retrieval', parent_step_id: null, input: { query: 'What is the refund policy?' }, output: { chunks: [{ id: 'doc-1', text: 'Refunds within 30 days.' }] }, error: null, metadata: { latency_ms: 45 } },
            { step_id: 's2', type: 'llm_call', parent_step_id: 's1', input: { messages: [{ role: 'user', content: 'What is the refund policy?' }] }, output: { text: 'You can request a refund within 30 days of purchase.' }, error: null, metadata: { latency_ms: 820, model: 'gpt-4', tokens: { input: 120, output: 35 } } },
          ]
        }
        await apiFetch('/v1/traces', { method: 'POST', body: JSON.stringify(buildTrace(tenant, 'success', stepsPayload)) })
      }
      notify(`Generated ${kind} scenario`)
      await refreshTraces()
    } catch (e) {
      setError(formatRequestError(e))
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar glass">
        <div className="topbar-left">
          <p className="eyebrow">AI Debug RCA</p>
          <h1>Observability Console</h1>
        </div>
        <div className="topbar-right">
          <div className="status">
            <span className={`dot ${health === 'ok' ? 'ok' : health === 'down' ? 'down' : ''}`}></span>
            <span>{health === 'unknown' ? 'Not checked' : `Health: ${health}`}</span>
          </div>
          <div className={`conn-chip ${connectionState}`}>
            {connectionState === 'connected' ? 'API Reachable' : connectionState === 'disconnected' ? 'API Unreachable' : 'Connection Unknown'}
            {lastConnectedAt ? ` • ${lastConnectedAt}` : ''}
          </div>
          <nav className="tabs top-tabs">
            {[
              ['settings', 'Settings'],
              ['ingest', 'Ingest'],
              ['traces', 'Traces'],
              ['steps', 'Steps'],
              ['admin', 'Admin'],
              ['testing', 'Test Data'],
            ].map(([key, label]) => (
              <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key as TabKey)}>
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {error && <div className="alert error">{error}</div>}

      {tab === 'settings' && (
        <section className="panel">
          <article className="settings glass card">
            <h2>Connection & Auth</h2>
            <p className="muted">Credentials are session-only by default and are not stored in browser localStorage.</p>
            <div className="grid">
              <label>Backend Base URL<input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} /></label>
              <label>Tenant ID (dev mode)<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} /></label>
              <label>API Key (optional)<input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk_test_..." /></label>
              <label>JWT Bearer (optional)<input value={jwtToken} onChange={(e) => setJwtToken(e.target.value)} placeholder="eyJhbGci..." /></label>
              <label>Admin Token (admin tab)<input value={adminToken} onChange={(e) => setAdminToken(e.target.value)} /></label>
            </div>
            <div className="actions">
              <button
                onClick={() => void checkHealth()}
              >
                Check Health
              </button>
              <button
                className="secondary"
                onClick={() => void connectBackend()}
              >
                Connect
              </button>
              <div><strong>Auth mode:</strong> {authSummary}</div>
            </div>
            {toast && <div className="alert toast">{toast}</div>}
          </article>
        </section>
      )}

      {tab === 'ingest' && (
        <section className="panel grid-two">
          <article className="glass card">
            <h3>POST /v1/traces</h3>
            <textarea value={singleTraceBody} onChange={(e) => setSingleTraceBody(e.target.value)} />
            <div className="actions">
              <button
                className={busyAction === 'ingest_single' ? 'busy' : ''}
                disabled={busyAction !== null}
                onClick={() => void runBusy('ingest_single', ingestSingleTrace)}
              >
                {busyAction === 'ingest_single' ? 'Sending...' : 'Send Single Trace'}
              </button>
              <button className="secondary" onClick={() => setSingleTraceBody(JSON.stringify(buildTrace(tenantId || 'org_demo', 'success', []), null, 2))}>Reset Template</button>
            </div>
          </article>
          <article className="glass card">
            <h3>POST /v1/traces/batch</h3>
            <textarea value={batchBody} onChange={(e) => setBatchBody(e.target.value)} />
            <div className="actions">
              <button
                className={busyAction === 'ingest_batch' ? 'busy' : ''}
                disabled={busyAction !== null}
                onClick={() => void runBusy('ingest_batch', ingestBatch)}
              >
                {busyAction === 'ingest_batch' ? 'Sending...' : 'Send Batch'}
              </button>
            </div>
          </article>
        </section>
      )}

      {tab === 'traces' && (
        <section className="panel grid-two traces-layout">
          <article className="glass card">
            <h3>Trace List</h3>
            <p className="muted">Recent traces loaded: {traceList.length} · API base: {baseUrl}</p>
            <div className="grid">
              <label>List Limit<input type="number" min={1} max={200} value={traceLimit} onChange={(e) => setTraceLimit(Number(e.target.value))} /></label>
            </div>
            <div className="actions">
              <button
                className={busyAction === 'trace_overview_reload' ? 'busy' : ''}
                disabled={busyAction !== null}
                onClick={() => void runBusy('trace_overview_reload', refreshTraces)}
              >
                {busyAction === 'trace_overview_reload' ? 'Reloading...' : 'Reload Traces'}
              </button>
            </div>
            <ul className="list">
              {traceList.map((t) => (
                <li key={`${t.trace_id}-${t.environment}`}>
                  <button
                    className="link"
                    onClick={() => {
                      setTraceIdLookup(t.trace_id)
                      setTraceEnvironment(t.environment)
                      void runBusy('trace_select_fetch', async () => {
                        await fetchTraceDetailFor(t.trace_id, t.environment)
                      })
                    }}
                  >
                    {t.trace_id} • {t.environment} • {t.status}
                  </button>
                </li>
              ))}
            </ul>
          </article>
          <article className="glass card">
            <h3>Trace Detail Query</h3>
            <div className="grid">
              <label>Trace ID<input value={traceIdLookup} onChange={(e) => setTraceIdLookup(e.target.value)} /></label>
              <label>Environment
                <select value={traceEnvironment} onChange={(e) => setTraceEnvironment(e.target.value as TraceEnvironment)}>
                  <option value="prod">prod</option><option value="staging">staging</option><option value="dev">dev</option><option value="critical">critical</option>
                </select>
              </label>
            </div>
            <div className="actions">
              <button
                className={busyAction === 'trace_detail' ? 'busy' : ''}
                disabled={busyAction !== null}
                onClick={() => void runBusy('trace_detail', fetchTraceDetail)}
              >
                {busyAction === 'trace_detail' ? 'Loading...' : 'Fetch Trace + Diagnosis'}
              </button>
            </div>
            <div className="viz-grid">
              <div className="viz-panel">
                <h3>Execution Graph</h3>
                {!traceSteps.length ? (
                  <p className="muted">Load a trace to render its graph.</p>
                ) : (
                  <div>
                    <div className="graph-toolbar">
                      <div className="actions">
                        <button className="secondary" onClick={() => zoomTo(zoom / 1.12, lastPointer ?? undefined)}>Zoom Out</button>
                        <button className="secondary" onClick={resetViewport}>Reset View</button>
                        <button className="secondary" onClick={() => zoomTo(zoom * 1.12, lastPointer ?? undefined)}>Zoom In</button>
                        <span className="muted">Zoom {Math.round(zoom * 100)}%</span>
                      </div>
                    </div>
                    <div
                      ref={graphViewportRef}
                      className="graph-wrap"
                      onWheelCapture={onGraphWheel}
                      onMouseDown={onGraphMouseDown}
                      onMouseMove={onGraphMouseMove}
                      onMouseUp={onGraphMouseUp}
                      onMouseLeave={onGraphMouseUp}
                    >
                    <svg
                      className="trace-graph"
                      width={graphCanvas.width}
                      height={graphCanvas.height}
                      viewBox={`0 0 ${graphCanvas.width} ${graphCanvas.height}`}
                      role="img"
                      aria-label="Trace execution graph"
                    >
                      <defs>
                        <marker id="graph-arrow" markerWidth="6" markerHeight="6" refX="5.25" refY="3" orient="auto">
                          <path d="M 0 0 L 6 3 L 0 6 z" className="graph-arrowhead" />
                        </marker>
                      </defs>
                      <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                      {traceEdges.map((e) => {
                        const from = visualNodeById.get(e.from)
                        const to = visualNodeById.get(e.to)
                        if (!from || !to) return null
                        const x1 = from.x + 80
                        const y1 = from.y + 24
                        const x2 = to.x
                        const y2 = to.y + 24
                        const cx1 = x1 + Math.max(42, (x2 - x1) * 0.35)
                        const cx2 = x2 - Math.max(42, (x2 - x1) * 0.35)
                        return (
                          <path
                            key={`${e.from}-${e.to}`}
                            d={`M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`}
                            className="graph-edge"
                            markerEnd="url(#graph-arrow)"
                          />
                        )
                      })}
                      {visualNodes.map((n) => {
                        const isActive = selectedStepId === n.id
                        return (
                          <g
                            key={n.id}
                            onClick={() => setSelectedStepId(n.id)}
                            className={isActive ? 'graph-node active' : 'graph-node'}
                          >
                            <rect
                              x={n.x}
                              y={n.y}
                              width={80}
                              height={48}
                              rx={10}
                              className={n.hasError ? 'graph-node-rect error' : 'graph-node-rect'}
                            />
                            <text x={n.x + 8} y={n.y + 20} className="graph-node-id">{n.id}</text>
                            <text x={n.x + 8} y={n.y + 36} className="graph-node-type">{n.type}</text>
                          </g>
                        )
                      })}
                      </g>
                    </svg>
                  </div>
                  </div>
                )}
              </div>
              <div className="viz-panel">
                <h3>Step Timeline</h3>
                {!traceSteps.length ? (
                  <p className="muted">No steps yet.</p>
                ) : (
                  <ol className="timeline" ref={timelineRef}>
                    {traceSteps.map((step, idx) => {
                      const active = step.step_id === selectedStepId
                      return (
                        <li
                          key={step.step_id}
                          data-step-id={step.step_id}
                          className={active ? 'timeline-item active' : 'timeline-item'}
                          onClick={() => {
                            setSelectedStepId(step.step_id)
                            centerGraphOnStep(step.step_id)
                          }}
                        >
                          <div className="timeline-index">{idx + 1}</div>
                          <div>
                            <div className="timeline-top">
                              <strong>{step.step_id}</strong>
                              <span>{step.type}</span>
                              <span>{formatLatencyMs(step.metadata)}</span>
                            </div>
                            {step.error && <div className="timeline-error">{step.error}</div>}
                          </div>
                        </li>
                      )
                    })}
                  </ol>
                )}
                {selectedStep && (
                  <div className="selected-step">
                    <h3>Selected Step</h3>
                    <pre>{JSON.stringify(selectedStep, null, 2)}</pre>
                  </div>
                )}
              </div>
            </div>
            <h3>Trace JSON</h3>
            <pre>{traceDetail ? JSON.stringify(traceDetail, null, 2) : 'No trace loaded yet.'}</pre>
            <h3>Diagnosis JSON</h3>
            <pre>{diagnosis ? JSON.stringify(diagnosis, null, 2) : 'No diagnosis loaded yet.'}</pre>
          </article>
        </section>
      )}

      {tab === 'steps' && (
        <section className="panel grid-two">
          <article className="glass card">
            <h3>GET /v1/traces/steps</h3>
            <div className="grid">
              <label>Step Type<input value={stepsType} onChange={(e) => setStepsType(e.target.value)} placeholder="tool_call" /></label>
              <label>Days<input type="number" min={1} max={365} value={stepsDays} onChange={(e) => setStepsDays(Number(e.target.value))} /></label>
              <label>has_error
                <select value={stepsErrorOnly === null ? 'all' : String(stepsErrorOnly)} onChange={(e) => setStepsErrorOnly(e.target.value === 'all' ? null : e.target.value === 'true')}>
                  <option value="all">all</option><option value="true">true</option><option value="false">false</option>
                </select>
              </label>
            </div>
            <div className="actions">
              <button
                className={busyAction === 'steps_query' ? 'busy' : ''}
                disabled={busyAction !== null}
                onClick={() => void runBusy('steps_query', refreshSteps)}
              >
                {busyAction === 'steps_query' ? 'Running...' : 'Run Step Query'}
              </button>
            </div>
          </article>
          <article className="glass card"><h3>Step Results ({steps.length})</h3><pre>{JSON.stringify(steps, null, 2)}</pre></article>
        </section>
      )}

      {tab === 'admin' && (
        <section className="panel grid-two">
          <article className="glass card">
            <h3>Admin Tenant Limits</h3>
            <p className="muted">Requires `RCA_ADMIN_TOKEN` and `X-Admin-Token`.</p>
            <div className="grid">
              <label>Tenant ID<input value={adminTenant} onChange={(e) => setAdminTenant(e.target.value)} /></label>
              <label>ingest_rate_limit_rps<input type="number" min={0} value={limitRps} onChange={(e) => setLimitRps(Number(e.target.value))} /></label>
              <label>ingest_daily_trace_quota<input type="number" min={0} value={limitQuota} onChange={(e) => setLimitQuota(Number(e.target.value))} /></label>
            </div>
            <div className="actions">
              <button
                className={busyAction === 'limits_load' ? 'busy' : ''}
                disabled={busyAction !== null}
                onClick={() => void runBusy('limits_load', fetchLimits)}
              >
                {busyAction === 'limits_load' ? 'Loading...' : 'Load Limits'}
              </button>
              <button
                className={`secondary ${busyAction === 'limits_save' ? 'busy' : ''}`}
                disabled={busyAction !== null}
                onClick={() => void runBusy('limits_save', saveLimits)}
              >
                {busyAction === 'limits_save' ? 'Saving...' : 'Save Limits'}
              </button>
            </div>
          </article>
          <article className="glass card"><h3>Current Limits</h3><pre>{limits ? JSON.stringify(limits, null, 2) : 'No limits loaded.'}</pre></article>
        </section>
      )}

      {tab === 'testing' && (
        <section className="panel">
          <article className="glass card">
            <h3>Generate Test Data</h3>
            <p className="muted">Browser cannot execute shell scripts directly, so this reproduces script scenarios via API calls.</p>
            <div className="actions wrap">
              <button disabled={busyAction !== null} className={busyAction === 'gen_minimal' ? 'busy' : ''} onClick={() => void runBusy('gen_minimal', () => generateScenario('minimal'))}>Minimal Trace</button>
              <button disabled={busyAction !== null} className={busyAction === 'gen_step_error' ? 'busy' : ''} onClick={() => void runBusy('gen_step_error', () => generateScenario('step_error'))}>Step Error Scenario</button>
              <button disabled={busyAction !== null} className={busyAction === 'gen_empty_retrieval' ? 'busy' : ''} onClick={() => void runBusy('gen_empty_retrieval', () => generateScenario('empty_retrieval'))}>Empty Retrieval Scenario</button>
              <button disabled={busyAction !== null} className={busyAction === 'gen_rag' ? 'busy' : ''} onClick={() => void runBusy('gen_rag', () => generateScenario('rag'))}>RAG Multi-Step Scenario</button>
              <button className={`secondary ${busyAction === 'gen_batch' ? 'busy' : ''}`} disabled={busyAction !== null} onClick={() => void runBusy('gen_batch', () => generateScenario('batch'))}>Batch Scenario</button>
            </div>
          </article>
        </section>
      )}
    </div>
  )
}

export default App

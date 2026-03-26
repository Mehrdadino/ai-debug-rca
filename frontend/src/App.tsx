import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type WheelEvent } from 'react'
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

type DiagnosisEvidence = {
  rule_id: string
  step_id?: string | null
  message: string
}

type DiagnosisView = {
  primary_hypothesis: string
  confidence: number | null
  summary: string
  secondary_hypotheses: string[]
  evidence: DiagnosisEvidence[]
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
type GraphTooltipPos = { x: number; y: number }
const GRAPH_TOOLTIP_WIDTH = 220
const GRAPH_TOOLTIP_HEIGHT = 92
const GRAPH_TOOLTIP_MAX_RADIUS = 230
type PersistedUiState = {
  baseUrl?: string
  tab?: TabKey
}
const UI_STATE_KEY = 'rca_ui_state_v1'

const TAB_KEYS: TabKey[] = ['settings', 'ingest', 'traces', 'steps', 'admin', 'testing']

function readUrlSearch(): URLSearchParams {
  if (typeof window === 'undefined') return new URLSearchParams()
  return new URLSearchParams(window.location.search)
}

function parseTabParam(sp: URLSearchParams): TabKey | null {
  const raw = sp.get('tab')?.trim()
  if (!raw) return null
  return TAB_KEYS.includes(raw as TabKey) ? (raw as TabKey) : null
}

function parseTraceStatusParam(v: string | null): 'all' | TraceStatus | null {
  if (!v) return null
  if (v === 'all') return 'all'
  if (v === 'success' || v === 'error' || v === 'partial') return v
  return null
}

function parseTraceEnvParam(v: string | null): 'all' | TraceEnvironment | null {
  if (!v) return null
  if (v === 'all') return 'all'
  if (v === 'prod' || v === 'staging' || v === 'dev' || v === 'critical') return v
  return null
}

function parseDetailEnvParam(v: string | null): TraceEnvironment {
  if (v === 'staging' || v === 'dev' || v === 'critical' || v === 'prod') return v
  return 'prod'
}

function initialStepsFromUrl(): { stepsType: string; stepsDays: number; stepsErrorOnly: boolean | null } {
  if (typeof window === 'undefined') return { stepsType: '', stepsDays: 7, stepsErrorOnly: true }
  const sp = readUrlSearch()
  if (!sp.has('step_type') && !sp.has('step_days') && !sp.has('step_has_error')) {
    return { stepsType: '', stepsDays: 7, stepsErrorOnly: true }
  }
  const stepsType = sp.get('step_type') ?? ''
  const stepsDays = Math.min(365, Math.max(1, Number(sp.get('step_days')) || 7))
  const se = sp.get('step_has_error')
  let stepsErrorOnly: boolean | null = true
  if (se === 'all') stepsErrorOnly = null
  else if (se === 'true') stepsErrorOnly = true
  else if (se === 'false') stepsErrorOnly = false
  return { stepsType, stepsDays, stepsErrorOnly }
}

function readTraceDeepLinkOnce(): { traceId: string; env: TraceEnvironment; step: string | null } | null {
  const sp = readUrlSearch()
  const traceId = sp.get('trace_id')?.trim() ?? ''
  if (!traceId) return null
  return {
    traceId,
    env: parseDetailEnvParam(sp.get('detail_env')),
    step: sp.get('step_id')?.trim() || null,
  }
}
const TRACE_PAGE_SIZE = 10
const STEPS_PAGE_SIZE = 20
const TRACE_SPINNER_MIN_MS = 320

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

function detailToMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        const rec = asRecord(item)
        if (!rec) return null
        const msg = typeof rec.msg === 'string' ? rec.msg.trim() : ''
        const loc = Array.isArray(rec.loc) ? rec.loc.map((x) => String(x)).join('.') : ''
        if (!msg) return null
        return loc ? `${loc}: ${msg}` : msg
      })
      .filter((v): v is string => Boolean(v))
    if (messages.length > 0) return messages.join(' | ')
    return `Request failed (${status})`
  }
  if (detail && typeof detail === 'object') {
    const rec = detail as Record<string, unknown>
    if (typeof rec.message === 'string' && rec.message.trim()) return rec.message
    if (typeof rec.error === 'string' && rec.error.trim()) return rec.error
    if (typeof rec.detail === 'string' && rec.detail.trim()) return rec.detail
  }
  return `Request failed (${status})`
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
    const detail = detailToMessage((payload as { detail?: unknown }).detail, res.status)
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

function extractDiagnosisView(diagnosis: Record<string, unknown> | null): DiagnosisView | null {
  if (!diagnosis) return null
  const primary_hypothesis = String(diagnosis.primary_hypothesis ?? '').trim()
  if (!primary_hypothesis) return null
  const confidenceRaw = diagnosis.confidence
  const confidence = typeof confidenceRaw === 'number' && Number.isFinite(confidenceRaw) ? confidenceRaw : null
  const summary = String(diagnosis.summary ?? '').trim()
  const secondaryRaw = Array.isArray(diagnosis.secondary_hypotheses) ? diagnosis.secondary_hypotheses : []
  const secondary_hypotheses = secondaryRaw.map((v) => String(v)).filter((v) => v.length > 0)
  const evidenceRaw = Array.isArray(diagnosis.evidence) ? diagnosis.evidence : []
  const evidence: DiagnosisEvidence[] = evidenceRaw
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => ({
      rule_id: String(item.rule_id ?? ''),
      step_id: item.step_id ? String(item.step_id) : null,
      message: String(item.message ?? ''),
    }))
    .filter((item) => item.rule_id.length > 0 && item.message.length > 0)

  return {
    primary_hypothesis,
    confidence,
    summary,
    secondary_hypotheses,
    evidence,
  }
}

function formatHypothesisId(v: string): string {
  return v
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function evidenceScopeLabel(ev: DiagnosisEvidence): string {
  if (ev.step_id) return `Step ${ev.step_id}`
  return 'Whole trace'
}

/** Failure rules — backend `rules_engine.RULE_WEIGHTS` (red headers). */
const DIAGNOSIS_ERROR_RULE_IDS = new Set([
  'trace_status_error',
  'guardrail_block',
  'multiple_step_errors',
  'step_error',
  'error_after_empty_retrieval',
  'empty_tool_output',
  'empty_retrieval',
])

/** Degradation / ops signals — amber headers. */
const DIAGNOSIS_WARN_RULE_IDS = new Set(['trace_status_partial', 'high_latency_llm'])

type DiagnosisEvidenceSeverity = 'error' | 'warn' | 'neutral'

function diagnosisEvidenceSeverity(ev: DiagnosisEvidence, failedStepIds: Set<string>): DiagnosisEvidenceSeverity {
  if (DIAGNOSIS_ERROR_RULE_IDS.has(ev.rule_id)) return 'error'
  if (DIAGNOSIS_WARN_RULE_IDS.has(ev.rule_id)) return 'warn'
  if (ev.step_id != null && failedStepIds.has(ev.step_id)) return 'error'
  return 'neutral'
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
  const traceDeepLinkRef = useRef(readTraceDeepLinkOnce())

  const [tab, setTab] = useState<TabKey>(() => {
    if (typeof window === 'undefined') return 'traces'
    const sp = readUrlSearch()
    if (sp.get('trace_id')?.trim()) return 'traces'
    const fromUrl = parseTabParam(sp)
    if (fromUrl) return fromUrl
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
  const errorTimerRef = useRef<number | null>(null)

  const [traceList, setTraceList] = useState<TraceSummary[]>([])
  const [traceOffset, setTraceOffset] = useState(0)
  const [traceHasMore, setTraceHasMore] = useState(true)
  const [traceLoadingMore, setTraceLoadingMore] = useState(false)
  const traceListRef = useRef<HTMLUListElement | null>(null)
  const [traceStatusFilter, setTraceStatusFilter] = useState<'all' | TraceStatus>(() => {
    if (typeof window === 'undefined') return 'all'
    return parseTraceStatusParam(readUrlSearch().get('trace_status')) ?? 'all'
  })
  const [traceEnvFilter, setTraceEnvFilter] = useState<'all' | TraceEnvironment>(() => {
    if (typeof window === 'undefined') return 'all'
    return parseTraceEnvParam(readUrlSearch().get('trace_env')) ?? 'all'
  })
  const [traceIdLookup, setTraceIdLookup] = useState(() => {
    if (typeof window === 'undefined') return ''
    return readUrlSearch().get('trace_id')?.trim() ?? ''
  })
  const [traceEnvironment, setTraceEnvironment] = useState<TraceEnvironment>(() => {
    if (typeof window === 'undefined') return 'prod'
    return parseDetailEnvParam(readUrlSearch().get('detail_env'))
  })
  const [traceDetail, setTraceDetail] = useState<Record<string, unknown> | null>(null)
  const [diagnosis, setDiagnosis] = useState<Record<string, unknown> | null>(null)
  const [graphFocusMode, setGraphFocusMode] = useState(false)
  const [showTimelineRail, setShowTimelineRail] = useState(true)
  const [selectedStepId, setSelectedStepId] = useState('')
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [graphViewportSize, setGraphViewportSize] = useState({ width: 0, height: 0 })
  const [lastPointer, setLastPointer] = useState<{ x: number; y: number } | null>(null)
  const [tooltipPos, setTooltipPos] = useState<GraphTooltipPos | null>(null)
  const [tooltipStepId, setTooltipStepId] = useState('')
  const graphViewportRef = useRef<HTMLDivElement | null>(null)
  const graphSvgRef = useRef<SVGSVGElement | null>(null)
  const timelineRef = useRef<HTMLOListElement | null>(null)
  /** When opening a trace from the Steps tab, select this step after load (consumed in traceSteps effect). */
  const pendingGraphFocusRef = useRef<string | null>(null)
  const stepRowNavTimerRef = useRef<number | null>(null)
  const zoomRef = useRef(1)
  const panRef = useRef({ x: 0, y: 0 })
  const panDragRef = useRef<{ active: boolean; startX: number; startY: number; startPanX: number; startPanY: number }>({
    active: false,
    startX: 0,
    startY: 0,
    startPanX: 0,
    startPanY: 0,
  })
  const tooltipDragRef = useRef<{ active: boolean; startX: number; startY: number; startTooltipX: number; startTooltipY: number }>({
    active: false,
    startX: 0,
    startY: 0,
    startTooltipX: 0,
    startTooltipY: 0,
  })

  const [steps, setSteps] = useState<StepSummary[]>([])
  const [stepsOffset, setStepsOffset] = useState(0)
  const [stepsHasMore, setStepsHasMore] = useState(false)
  const [stepsLoadingMore, setStepsLoadingMore] = useState(false)
  const [stepsEverQueried, setStepsEverQueried] = useState(false)
  const [stepsListLoading, setStepsListLoading] = useState(false)
  const stepsListRef = useRef<HTMLDivElement | null>(null)
  const initialSteps = initialStepsFromUrl()
  const [stepsType, setStepsType] = useState(initialSteps.stepsType)
  const [stepsDays, setStepsDays] = useState(initialSteps.stepsDays)
  const [stepsErrorOnly, setStepsErrorOnly] = useState<boolean | null>(initialSteps.stepsErrorOnly)

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
  const diagnosisView = useMemo(() => extractDiagnosisView(diagnosis), [diagnosis])
  const failedStepIds = useMemo(
    () => new Set(traceSteps.filter((s) => Boolean(s.error)).map((s) => s.step_id)),
    [traceSteps],
  )
  const traceEdges = useMemo(() => extractTraceEdges(traceDetail, traceSteps), [traceDetail, traceSteps])
  const visualNodes = useMemo(() => buildVisualNodes(traceSteps, traceEdges), [traceSteps, traceEdges])
  const graphCanvas = useMemo(() => {
    const width = Math.max(680, graphViewportSize.width, ...visualNodes.map((n) => n.x + 160))
    const height = Math.max(240, graphViewportSize.height, ...visualNodes.map((n) => n.y + 110))
    return { width, height }
  }, [visualNodes, graphViewportSize.width, graphViewportSize.height])
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
  const tooltipNode = useMemo(() => visualNodeById.get(tooltipStepId) ?? null, [visualNodeById, tooltipStepId])

  useEffect(() => {
    if (!traceSteps.length) {
      setSelectedStepId('')
      setTooltipPos(null)
      setTooltipStepId('')
      return
    }
    const pending = pendingGraphFocusRef.current
    if (pending && traceSteps.some((s) => s.step_id === pending)) {
      setSelectedStepId(pending)
      pendingGraphFocusRef.current = null
      requestAnimationFrame(() => {
        centerGraphOnStep(pending)
        openTooltipForStep(pending)
      })
      return
    }
    setSelectedStepId((prev) => (prev && traceSteps.some((s) => s.step_id === prev) ? prev : traceSteps[0].step_id))
  }, [traceSteps])

  function openTooltipForStep(stepId: string): void {
    const node = visualNodeById.get(stepId)
    if (!node) return
    setTooltipStepId(stepId)
    const placed = placeTooltipNearStep(stepId)
    setTooltipPos(placed)
  }

  function clampTooltipPos(pos: GraphTooltipPos): GraphTooltipPos {
    const viewport = graphViewportRef.current
    if (!viewport) return pos
    const currentZoom = zoomRef.current
    const currentPan = panRef.current
    const vw = Math.max(240, viewport.clientWidth)
    const vh = Math.max(200, viewport.clientHeight)
    const margin = 8
    const minX = (margin - currentPan.x) / currentZoom
    const maxX = (vw - margin - GRAPH_TOOLTIP_WIDTH * currentZoom - currentPan.x) / currentZoom
    const minY = (margin - currentPan.y) / currentZoom
    const maxY = (vh - margin - GRAPH_TOOLTIP_HEIGHT * currentZoom - currentPan.y) / currentZoom
    return {
      x: Math.min(Math.max(pos.x, minX), Math.max(minX, maxX)),
      y: Math.min(Math.max(pos.y, minY), Math.max(minY, maxY)),
    }
  }

  function rectsOverlap(
    a: { x: number; y: number; w: number; h: number },
    b: { x: number; y: number; w: number; h: number },
  ): boolean {
    return !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y)
  }

  function overlapArea(
    a: { x: number; y: number; w: number; h: number },
    b: { x: number; y: number; w: number; h: number },
  ): number {
    const xOverlap = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x))
    const yOverlap = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y))
    return xOverlap * yOverlap
  }

  function clampTooltipToRadius(pos: GraphTooltipPos, node: VisualNode): GraphTooltipPos {
    const nodeCx = node.x + 40
    const nodeCy = node.y + 24
    const tipCx = pos.x + GRAPH_TOOLTIP_WIDTH / 2
    const tipCy = pos.y + GRAPH_TOOLTIP_HEIGHT / 2
    const dx = tipCx - nodeCx
    const dy = tipCy - nodeCy
    const dist = Math.hypot(dx, dy)
    if (dist <= GRAPH_TOOLTIP_MAX_RADIUS || dist === 0) return pos
    const scale = GRAPH_TOOLTIP_MAX_RADIUS / dist
    return {
      x: nodeCx + dx * scale - GRAPH_TOOLTIP_WIDTH / 2,
      y: nodeCy + dy * scale - GRAPH_TOOLTIP_HEIGHT / 2,
    }
  }

  function enforceNoOwnStepOverlap(pos: GraphTooltipPos, node: VisualNode): GraphTooltipPos {
    const tip = { x: pos.x, y: pos.y, w: GRAPH_TOOLTIP_WIDTH, h: GRAPH_TOOLTIP_HEIGHT }
    const own = { x: node.x, y: node.y, w: 80, h: 48 }
    if (!rectsOverlap(tip, own)) return pos

    const candidates: GraphTooltipPos[] = [
      { x: node.x + 94, y: node.y - 8 },
      { x: node.x - GRAPH_TOOLTIP_WIDTH - 14, y: node.y - 8 },
      { x: node.x - (GRAPH_TOOLTIP_WIDTH - 80) / 2, y: node.y - GRAPH_TOOLTIP_HEIGHT - 14 },
      { x: node.x - (GRAPH_TOOLTIP_WIDTH - 80) / 2, y: node.y + 48 + 14 },
    ]
    for (const c of candidates) {
      const v = clampTooltipPos(clampTooltipToRadius(c, node))
      const t = { x: v.x, y: v.y, w: GRAPH_TOOLTIP_WIDTH, h: GRAPH_TOOLTIP_HEIGHT }
      if (!rectsOverlap(t, own)) return v
    }
    return pos
  }

  function scoreTooltipPos(pos: GraphTooltipPos, node: VisualNode): number {
    const tip = { x: pos.x, y: pos.y, w: GRAPH_TOOLTIP_WIDTH, h: GRAPH_TOOLTIP_HEIGHT }
    const own = { x: node.x, y: node.y, w: 80, h: 48 }
    let score = 0
    if (rectsOverlap(tip, own)) score += 1_000_000

    for (const n of visualNodes) {
      if (n.id === node.id) continue
      const r = { x: n.x, y: n.y, w: 80, h: 48 }
      score += overlapArea(tip, r) * 3
    }

    const nodeCx = node.x + 40
    const nodeCy = node.y + 24
    const tipCx = pos.x + GRAPH_TOOLTIP_WIDTH / 2
    const tipCy = pos.y + GRAPH_TOOLTIP_HEIGHT / 2
    const dist = Math.hypot(tipCx - nodeCx, tipCy - nodeCy)
    score += dist
    if (dist > GRAPH_TOOLTIP_MAX_RADIUS) score += (dist - GRAPH_TOOLTIP_MAX_RADIUS) * 200
    return score
  }

  function placeTooltipNearStep(stepId: string): GraphTooltipPos {
    const node = visualNodeById.get(stepId)
    if (!node) return { x: 0, y: 0 }
    const candidates: GraphTooltipPos[] = [
      { x: node.x + 94, y: node.y - 8 },
      { x: node.x - GRAPH_TOOLTIP_WIDTH - 14, y: node.y - 8 },
      { x: node.x - (GRAPH_TOOLTIP_WIDTH - 80) / 2, y: node.y - GRAPH_TOOLTIP_HEIGHT - 14 },
      { x: node.x - (GRAPH_TOOLTIP_WIDTH - 80) / 2, y: node.y + 48 + 14 },
      { x: node.x + 94, y: node.y - GRAPH_TOOLTIP_HEIGHT + 24 },
      { x: node.x - GRAPH_TOOLTIP_WIDTH - 14, y: node.y - GRAPH_TOOLTIP_HEIGHT + 24 },
      { x: node.x + 54, y: node.y + 58 },
      { x: node.x - GRAPH_TOOLTIP_WIDTH + 26, y: node.y + 58 },
    ]
    let best = clampTooltipPos(clampTooltipToRadius(candidates[0], node))
    best = enforceNoOwnStepOverlap(best, node)
    let bestScore = scoreTooltipPos(best, node)

    for (const c of candidates.slice(1)) {
      let p = clampTooltipPos(clampTooltipToRadius(c, node))
      p = enforceNoOwnStepOverlap(p, node)
      const s = scoreTooltipPos(p, node)
      if (s < bestScore) {
        best = p
        bestScore = s
      }
    }
    return best
  }

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
    const syncViewportSize = () => {
      setGraphViewportSize({
        width: Math.max(0, Math.floor(viewport.clientWidth)),
        height: Math.max(0, Math.floor(viewport.clientHeight)),
      })
      centerGraphToFit()
    }
    syncViewportSize()
    const observer = new ResizeObserver(syncViewportSize)
    observer.observe(viewport)
    return () => observer.disconnect()
    // Keep graph centered when viewport size changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visualNodes.length, graphCanvas.width, graphCanvas.height, graphBounds.minX, graphBounds.minY, graphBounds.width, graphBounds.height])

  useEffect(() => {
    zoomRef.current = zoom
    panRef.current = pan
  }, [zoom, pan])

  /**
   * Pointer in SVG user space (viewBox coords). Required because width/height can differ from
   * viewBox (min graph height 360), so CSS pixels are not 1:1 with pan/zoom units.
   */
  function pointerInGraphSvg(e: { clientX: number; clientY: number }): { x: number; y: number } | null {
    const svg = graphSvgRef.current
    if (!svg) return null
    const ctm = svg.getScreenCTM()
    if (!ctm) return null
    const pt = svg.createSVGPoint()
    pt.x = e.clientX
    pt.y = e.clientY
    const loc = pt.matrixTransform(ctm.inverse())
    return { x: loc.x, y: loc.y }
  }

  /** Center of the graph viewport wrapper, in SVG user space (matches pan units). */
  function viewportCenterInGraphSvg(): { x: number; y: number } | null {
    const svg = graphSvgRef.current
    const viewport = graphViewportRef.current
    if (!svg || !viewport) return null
    const ctm = svg.getScreenCTM()
    if (!ctm) return null
    const r = viewport.getBoundingClientRect()
    const pt = svg.createSVGPoint()
    pt.x = r.left + r.width / 2
    pt.y = r.top + r.height / 2
    const loc = pt.matrixTransform(ctm.inverse())
    return { x: loc.x, y: loc.y }
  }

  function zoomTo(targetZoom: number, anchor?: { x: number; y: number }): void {
    const viewport = graphViewportRef.current
    if (!viewport) return
    const svg = graphSvgRef.current
    let vx: number
    let vy: number
    if (anchor) {
      vx = anchor.x
      vy = anchor.y
    } else if (svg) {
      vx = graphCanvas.width / 2
      vy = graphCanvas.height / 2
    } else {
      const rect = viewport.getBoundingClientRect()
      vx = rect.width / 2
      vy = rect.height / 2
    }
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
    const node = visualNodeById.get(stepId)
    if (!node) return
    const center = viewportCenterInGraphSvg()
    if (!center) return
    const nodeCx = node.x + 40
    const nodeCy = node.y + 24
    const currentZoom = zoomRef.current
    setPan({
      x: center.x - nodeCx * currentZoom,
      y: center.y - nodeCy * currentZoom,
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
    const p = pointerInGraphSvg(e)
    if (!p) return
    zoomTo(targetZoom, p)
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
    const p = pointerInGraphSvg(e)
    if (p) setLastPointer(p)
    if (tooltipDragRef.current.active) {
      const dx = (e.clientX - tooltipDragRef.current.startX) / zoomRef.current
      const dy = (e.clientY - tooltipDragRef.current.startY) / zoomRef.current
      const node = visualNodeById.get(tooltipStepId)
      let nextPos = clampTooltipPos({
        x: tooltipDragRef.current.startTooltipX + dx,
        y: tooltipDragRef.current.startTooltipY + dy,
      })
      if (node) {
        nextPos = clampTooltipToRadius(nextPos, node)
        nextPos = clampTooltipPos(nextPos)
        nextPos = enforceNoOwnStepOverlap(nextPos, node)
      }
      setTooltipPos(nextPos)
      return
    }
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
    tooltipDragRef.current.active = false
  }

  function onTooltipMouseDown(e: MouseEvent<SVGGElement>): void {
    if (!tooltipPos) return
    e.stopPropagation()
    tooltipDragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      startTooltipX: tooltipPos.x,
      startTooltipY: tooltipPos.y,
    }
  }

  useEffect(() => {
    if (!selectedStepId || !timelineRef.current) return
    if (graphFocusMode && !showTimelineRail) return
    const el = timelineRef.current.querySelector<HTMLElement>(`[data-step-id="${selectedStepId}"]`)
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selectedStepId, graphFocusMode, showTimelineRail])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const data: PersistedUiState = {
      baseUrl,
      tab,
    }
    window.localStorage.setItem(UI_STATE_KEY, JSON.stringify(data))
  }, [baseUrl, tab])

  useEffect(() => {
    void checkHealth(false)
    // Run once on initial app load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!error) return
    if (errorTimerRef.current !== null) {
      window.clearTimeout(errorTimerRef.current)
    }
    errorTimerRef.current = window.setTimeout(() => {
      setError('')
      errorTimerRef.current = null
    }, 4800)
  }, [error])

  useEffect(() => {
    return () => {
      if (errorTimerRef.current !== null) {
        window.clearTimeout(errorTimerRef.current)
        errorTimerRef.current = null
      }
      if (stepRowNavTimerRef.current !== null) {
        window.clearTimeout(stepRowNavTimerRef.current)
        stepRowNavTimerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (tab !== 'steps' && stepRowNavTimerRef.current !== null) {
      window.clearTimeout(stepRowNavTimerRef.current)
      stepRowNavTimerRef.current = null
    }
  }, [tab])

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

  async function refreshTraces(reset = true): Promise<void> {
    const startedAt = Date.now()
    try {
      const nextOffset = reset ? 0 : traceOffset
      if (!reset) setTraceLoadingMore(true)
      const q = new URLSearchParams()
      q.set('limit', String(TRACE_PAGE_SIZE))
      q.set('offset', String(nextOffset))
      if (traceStatusFilter !== 'all') q.set('status', traceStatusFilter)
      if (traceEnvFilter !== 'all') q.set('environment', traceEnvFilter)
      const payload = await apiFetch<{ items: TraceSummary[]; has_more?: boolean; limit?: number; offset?: number }>(
        `/v1/traces?${q.toString()}`,
      )
      if (reset) {
        setTraceList(payload.items)
      } else {
        setTraceList((prev) => {
          const seen = new Set(prev.map((t) => `${t.trace_id}:${t.environment}`))
          const merged = [...prev]
          for (const item of payload.items) {
            const k = `${item.trace_id}:${item.environment}`
            if (!seen.has(k)) {
              seen.add(k)
              merged.push(item)
            }
          }
          return merged
        })
      }
      const loadedCount = payload.items.length
      const hasMore = Boolean(payload.has_more ?? loadedCount === TRACE_PAGE_SIZE)
      setTraceHasMore(hasMore)
      setTraceOffset(nextOffset + loadedCount)
      notify(reset ? `Loaded ${payload.items.length} traces` : `Loaded ${payload.items.length} more traces`)
    } catch (e) {
      setError(formatRequestError(e))
    } finally {
      if (!reset) {
        const elapsed = Date.now() - startedAt
        const wait = Math.max(0, TRACE_SPINNER_MIN_MS - elapsed)
        if (wait > 0) {
          await new Promise((resolve) => setTimeout(resolve, wait))
        }
        setTraceLoadingMore(false)
      }
    }
  }

  async function ingestSingleTrace(): Promise<void> {
    try {
      const data = JSON.parse(singleTraceBody)
      await apiFetch('/v1/traces', { method: 'POST', body: JSON.stringify(data) })
      notify('Single trace sent')
      await refreshTraces(true)
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
      await refreshTraces(true)
    } catch (e) {
      if (e instanceof SyntaxError) return setError('Invalid JSON in batch body')
      setError(formatRequestError(e))
    }
  }

  function tracePayloadHasStepId(payload: Record<string, unknown>, stepId: string): boolean {
    const stepsRaw = payload.steps
    if (!Array.isArray(stepsRaw)) return false
    for (const raw of stepsRaw) {
      const rec = asRecord(raw)
      if (rec && String(rec.step_id ?? '').trim() === stepId) return true
    }
    return false
  }

  async function fetchTraceDetailFor(
    traceId: string,
    env: TraceEnvironment,
    opts?: { notifyOnSuccess?: boolean; focusStepId?: string | null },
  ): Promise<void> {
    const wantFocus = opts?.focusStepId?.trim() ?? ''
    if (!wantFocus) pendingGraphFocusRef.current = null
    try {
      const t = await apiFetch<Record<string, unknown>>(`/v1/traces/${traceId}?environment=${env}`)
      const d = await apiFetch<Record<string, unknown>>(`/v1/traces/${traceId}/diagnosis?environment=${env}`)
      let openedWithStep = false
      if (wantFocus) {
        openedWithStep = tracePayloadHasStepId(t, wantFocus)
        pendingGraphFocusRef.current = openedWithStep ? wantFocus : null
      }
      setTraceDetail(t)
      setDiagnosis(d)
      if (opts?.notifyOnSuccess) {
        notify(openedWithStep ? 'Trace opened with selected step' : 'Trace and diagnosis loaded')
      }
    } catch (e) {
      pendingGraphFocusRef.current = null
      const msg = formatRequestError(e)
      const normalized = msg.toLowerCase()
      if (normalized.includes('path.trace_id') || normalized.includes('valid uuid') || normalized.includes('trace not found')) {
        setError('Trace ID not found')
      } else {
        setError(msg)
      }
      setTraceDetail(null)
      setDiagnosis(null)
    }
  }

  const fetchTraceDetailForRef = useRef(fetchTraceDetailFor)
  fetchTraceDetailForRef.current = fetchTraceDetailFor

  const hydrateFromSearchParams = useCallback((sp: URLSearchParams) => {
    if (sp.get('trace_id')?.trim()) {
      setTab('traces')
    } else {
      const t = parseTabParam(sp)
      if (t) setTab(t)
    }
    const ts = parseTraceStatusParam(sp.get('trace_status'))
    const te = parseTraceEnvParam(sp.get('trace_env'))
    if (ts) setTraceStatusFilter(ts)
    if (te) setTraceEnvFilter(te)
    if (sp.has('trace_id')) {
      const tid = sp.get('trace_id')?.trim() ?? ''
      setTraceIdLookup(tid)
      if (tid) setTraceEnvironment(parseDetailEnvParam(sp.get('detail_env')))
    } else if (parseTabParam(sp) === 'traces') {
      setTraceIdLookup('')
    }
    if (sp.has('step_id')) {
      setSelectedStepId(sp.get('step_id')?.trim() ?? '')
    } else if (sp.get('trace_id')?.trim()) {
      setSelectedStepId('')
    }
    if (sp.has('step_type')) setStepsType(sp.get('step_type') ?? '')
    if (sp.has('step_days')) {
      const n = Number(sp.get('step_days'))
      if (Number.isFinite(n)) setStepsDays(Math.min(365, Math.max(1, n)))
    }
    if (sp.has('step_has_error')) {
      const se = sp.get('step_has_error')
      if (se === 'all') setStepsErrorOnly(null)
      else if (se === 'true') setStepsErrorOnly(true)
      else if (se === 'false') setStepsErrorOnly(false)
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const sp = new URLSearchParams()
    sp.set('tab', tab)
    if (tab === 'traces') {
      sp.set('trace_status', traceStatusFilter)
      sp.set('trace_env', traceEnvFilter)
      const tid = traceIdLookup.trim()
      if (tid) {
        sp.set('trace_id', tid)
        sp.set('detail_env', traceEnvironment)
        if (selectedStepId.trim()) sp.set('step_id', selectedStepId.trim())
      }
    }
    if (tab === 'steps') {
      sp.set('step_type', stepsType)
      sp.set('step_days', String(stepsDays))
      sp.set('step_has_error', stepsErrorOnly === null ? 'all' : String(stepsErrorOnly))
    }
    const next = `${window.location.pathname}?${sp.toString()}`
    const cur = `${window.location.pathname}${window.location.search}`
    if (next !== cur) {
      window.history.replaceState({}, '', next)
    }
  }, [tab, traceStatusFilter, traceEnvFilter, traceIdLookup, traceEnvironment, selectedStepId, stepsType, stepsDays, stepsErrorOnly])

  useEffect(() => {
    const onPop = () => {
      hydrateFromSearchParams(new URLSearchParams(window.location.search))
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [hydrateFromSearchParams])

  useEffect(() => {
    const link = traceDeepLinkRef.current
    traceDeepLinkRef.current = null
    if (!link || tab !== 'traces') return
    void fetchTraceDetailForRef.current(link.traceId, link.env, {
      focusStepId: link.step,
      notifyOnSuccess: false,
    })
  }, [tab])

  async function fetchTraceDetail(): Promise<void> {
    if (!traceIdLookup.trim()) return setError('Trace ID is required')
    await fetchTraceDetailFor(traceIdLookup.trim(), traceEnvironment, { notifyOnSuccess: true })
  }

  async function openTraceFromStepSummary(item: StepSummary): Promise<void> {
    setTab('traces')
    setTraceIdLookup(item.trace_id)
    setTraceEnvironment(item.environment)
    await fetchTraceDetailFor(item.trace_id, item.environment, {
      notifyOnSuccess: true,
      focusStepId: item.step_id,
    })
  }

  function handleStepRowClick(row: StepSummary, e: MouseEvent<HTMLTableRowElement>): void {
    if (e.button !== 0) return
    if (window.getSelection()?.toString().trim()) return
    if (e.detail >= 2) {
      if (stepRowNavTimerRef.current !== null) {
        window.clearTimeout(stepRowNavTimerRef.current)
        stepRowNavTimerRef.current = null
      }
      return
    }
    if (stepRowNavTimerRef.current !== null) window.clearTimeout(stepRowNavTimerRef.current)
    stepRowNavTimerRef.current = window.setTimeout(() => {
      stepRowNavTimerRef.current = null
      if (window.getSelection()?.toString().trim()) return
      void runBusy('steps_open_trace', () => openTraceFromStepSummary(row))
    }, 280)
  }

  function handleStepRowDoubleClick(): void {
    if (stepRowNavTimerRef.current !== null) {
      window.clearTimeout(stepRowNavTimerRef.current)
      stepRowNavTimerRef.current = null
    }
  }

  async function refreshSteps(reset = true): Promise<void> {
    const startedAt = Date.now()
    if (reset) setStepsListLoading(true)
    try {
      const nextOffset = reset ? 0 : stepsOffset
      if (!reset) setStepsLoadingMore(true)
      const q = new URLSearchParams()
      q.set('days', String(stepsDays))
      q.set('limit', String(STEPS_PAGE_SIZE))
      q.set('offset', String(nextOffset))
      if (stepsType.trim()) q.set('step_type', stepsType.trim().toLowerCase())
      if (stepsErrorOnly !== null) q.set('has_error', String(stepsErrorOnly))
      const payload = await apiFetch<{ items: StepSummary[]; has_more?: boolean }>(`/v1/traces/steps?${q.toString()}`)
      if (reset) {
        setSteps(payload.items)
      } else {
        setSteps((prev) => {
          const seen = new Set(prev.map((s) => `${s.trace_id}:${s.step_id}:${s.trace_started_at}`))
          const merged = [...prev]
          for (const item of payload.items) {
            const k = `${item.trace_id}:${item.step_id}:${item.trace_started_at}`
            if (!seen.has(k)) {
              seen.add(k)
              merged.push(item)
            }
          }
          return merged
        })
      }
      const loadedCount = payload.items.length
      const hasMore = Boolean(payload.has_more ?? loadedCount === STEPS_PAGE_SIZE)
      setStepsHasMore(hasMore)
      setStepsOffset(nextOffset + loadedCount)
      notify(reset ? `Loaded ${payload.items.length} steps` : `Loaded ${payload.items.length} more steps`)
    } catch (e) {
      setError(formatRequestError(e))
    } finally {
      if (reset) {
        setStepsListLoading(false)
        setStepsEverQueried(true)
      } else {
        const elapsed = Date.now() - startedAt
        const wait = Math.max(0, TRACE_SPINNER_MIN_MS - elapsed)
        if (wait > 0) {
          await new Promise((resolve) => setTimeout(resolve, wait))
        }
        setStepsLoadingMore(false)
      }
    }
  }

  function onStepsListScroll(): void {
    const el = stepsListRef.current
    if (!el || stepsLoadingMore || !stepsHasMore || busyAction !== null) return
    const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 40
    if (nearBottom) {
      void refreshSteps(false)
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
      await refreshTraces(true)
    } catch (e) {
      setError(formatRequestError(e))
    }
  }

  function onTraceListScroll(): void {
    const el = traceListRef.current
    if (!el || traceLoadingMore || !traceHasMore) return
    const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 40
    if (nearBottom) {
      void refreshTraces(false)
    }
  }

  useEffect(() => {
    if (tab !== 'traces') return
    void refreshTraces(true)
    // refresh when entering traces tab or filters change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, traceStatusFilter, traceEnvFilter])

  useEffect(() => {
    if (tab !== 'steps') return
    void refreshSteps(true)
    // refresh when entering steps tab or filters change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, stepsType, stepsDays, stepsErrorOnly])

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
        <section className={`panel traces-page traces-layout ${graphFocusMode ? 'focus-graph' : ''}`}>
          <div className="traces-page-top">
          {!graphFocusMode && (
          <article className="glass card trace-list-card">
            <h3>Trace List</h3>
            <p className="muted">Showing {traceList.length} trace{traceList.length === 1 ? '' : 's'}.</p>
            <div className="grid">
              <label>Status
                <select value={traceStatusFilter} onChange={(e) => setTraceStatusFilter(e.target.value as 'all' | TraceStatus)}>
                  <option value="all">all</option>
                  <option value="success">success</option>
                  <option value="error">error</option>
                  <option value="partial">partial</option>
                </select>
              </label>
              <label>Environment
                <select value={traceEnvFilter} onChange={(e) => setTraceEnvFilter(e.target.value as 'all' | TraceEnvironment)}>
                  <option value="all">all</option>
                  <option value="prod">prod</option>
                  <option value="staging">staging</option>
                  <option value="dev">dev</option>
                  <option value="critical">critical</option>
                </select>
              </label>
            </div>
            <ul className="list" ref={traceListRef} onScroll={onTraceListScroll}>
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
              {traceLoadingMore && (
                <li className="loading-row">
                  <span className="spinner"></span>
                  <span>Loading more traces...</span>
                </li>
              )}
              {!traceHasMore && traceList.length > 0 && <li className="muted">End of trace list.</li>}
            </ul>
          </article>
          )}
          <article className="glass card trace-detail-main">
            <div className="trace-detail-header">
              <h3>Trace Detail Query</h3>
            </div>
            <p className="muted trace-detail-hint">
              The query string updates as you change tab, filters, trace, and step — copy the browser URL to share this view.
            </p>
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
                  <p className="muted">
                    {traceDetail
                      ? 'This trace is loaded, but it has no steps to visualize.'
                      : 'Load a trace to render its graph.'}
                  </p>
                ) : (
                  <div>
                    <div className="graph-toolbar">
                      <div className="actions">
                        <button className="secondary" onClick={() => setGraphFocusMode((v) => !v)}>
                          {graphFocusMode ? 'Exit Focus Graph' : 'Focus Graph'}
                        </button>
                        <button className="secondary" onClick={() => zoomTo(zoom / 1.12, lastPointer ?? undefined)}>Zoom Out</button>
                        <button className="secondary" onClick={resetViewport}>Reset View</button>
                        <button className="secondary" onClick={() => zoomTo(zoom * 1.12, lastPointer ?? undefined)}>Zoom In</button>
                        {graphFocusMode && (
                          <button className="secondary" onClick={() => setShowTimelineRail((v) => !v)}>
                            {showTimelineRail ? 'Hide Timeline' : 'Show Timeline'}
                          </button>
                        )}
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
                      ref={graphSvgRef}
                      className="trace-graph"
                      width={graphCanvas.width}
                      height={Math.max(graphCanvas.height, 360)}
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
                            onClick={() => {
                              setSelectedStepId(n.id)
                              const isSame = tooltipPos !== null && tooltipStepId === n.id
                              if (isSame) {
                                setTooltipPos(null)
                                setTooltipStepId('')
                              } else {
                                openTooltipForStep(n.id)
                              }
                            }}
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
                      {selectedStep && tooltipPos && tooltipNode && tooltipStepId === selectedStep.step_id && (
                        <g className="graph-tooltip" onMouseDown={onTooltipMouseDown}>
                          <line
                            x1={tooltipNode.x + 40}
                            y1={tooltipNode.y + 24}
                            x2={tooltipPos.x}
                            y2={tooltipPos.y + 24}
                            className="graph-tooltip-link"
                          />
                          <rect x={tooltipPos.x} y={tooltipPos.y} width={GRAPH_TOOLTIP_WIDTH} height={GRAPH_TOOLTIP_HEIGHT} rx={10} className="graph-tooltip-box" />
                          <text x={tooltipPos.x + 10} y={tooltipPos.y + 18} className="graph-tooltip-title">{selectedStep.step_id}</text>
                          <text x={tooltipPos.x + 10} y={tooltipPos.y + 36} className="graph-tooltip-line">type: {selectedStep.type}</text>
                          <text x={tooltipPos.x + 10} y={tooltipPos.y + 52} className="graph-tooltip-line">latency: {formatLatencyMs(selectedStep.metadata)}</text>
                          <text x={tooltipPos.x + 10} y={tooltipPos.y + 68} className="graph-tooltip-line">
                            {selectedStep.error ? `error: ${selectedStep.error}` : 'status: ok'}
                          </text>
                          <text x={tooltipPos.x + 10} y={tooltipPos.y + 84} className="graph-tooltip-hint">drag to move</text>
                        </g>
                      )}
                      </g>
                    </svg>
                  </div>
                  </div>
                )}
              </div>
              {(!graphFocusMode || showTimelineRail) && (
              <div className="viz-panel timeline-panel">
                <h3>Step Timeline</h3>
                {!traceSteps.length ? (
                  <p className="muted">
                    {traceDetail
                      ? 'This trace is loaded, but it has no steps for the timeline.'
                      : 'Load a trace to view its step timeline.'}
                  </p>
                ) : (
                  <ol className="timeline" ref={timelineRef}>
                    {traceSteps.map((step, idx) => {
                      const active = step.step_id === selectedStepId
                      return (
                        <li
                          key={step.step_id}
                          data-step-id={step.step_id}
                          className={`timeline-item${active ? ' active' : ''}${step.error ? ' has-error' : ''}`}
                          onClick={() => {
                            setSelectedStepId(step.step_id)
                            centerGraphOnStep(step.step_id)
                            openTooltipForStep(step.step_id)
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
              )}
            </div>
          </article>
          </div>          
          <div className="glass card traces-diagnosis-section">
            <h2 className="traces-diagnosis-title">Diagnosis</h2>
            <p className="diagnosis-intro muted">
              Rule-based readout of this trace: each line below is a deterministic check (not an LLM guess). Use the graph and timeline above to see where each step ran.
            </p>
            {diagnosisView ? (
              <div className="diagnosis-overview diagnosis-overview-wide">
                <div className="diagnosis-title-row">
                  <div>
                    <p className="diagnosis-field-label">Primary explanation</p>
                    <h4>{formatHypothesisId(diagnosisView.primary_hypothesis)}</h4>
                    <p className="muted diagnosis-rule-id mono">Internal id: {diagnosisView.primary_hypothesis}</p>
                  </div>
                  <div
                    className="diagnosis-confidence-pill"
                    title="Score from rule weights (0–1). Higher means a stronger match to the primary explanation."
                  >
                    Confidence {diagnosisView.confidence === null ? 'n/a' : diagnosisView.confidence.toFixed(3)}
                  </div>
                </div>
                <p className="diagnosis-summary-text">{diagnosisView.summary || 'No deterministic summary available yet.'}</p>
                {diagnosisView.secondary_hypotheses.length > 0 && (
                  <div className="diagnosis-secondary">
                    <p className="diagnosis-field-label">Also considered</p>
                    <div className="diagnosis-tags">
                      {diagnosisView.secondary_hypotheses.map((h) => (
                        <span key={h} className="diagnosis-tag mono">{h}</span>
                      ))}
                    </div>
                  </div>
                )}
                {diagnosisView.evidence.length > 0 ? (
                  <>
                    <p className="diagnosis-field-label">Evidence checks</p>
                    <ol className="diagnosis-evidence-list diagnosis-evidence-list-scroll">
                      {diagnosisView.evidence.slice(0, 20).map((ev, idx) => {
                        const severity = diagnosisEvidenceSeverity(ev, failedStepIds)
                        const ruleHeaderClass =
                          severity === 'error' ? 'diagnosis-rule-error' : severity === 'warn' ? 'diagnosis-rule-warn' : ''
                        return (
                          <li key={`${ev.rule_id}-${ev.step_id ?? 'trace'}-${idx}`} className="diagnosis-evidence-item">
                            <div className="diagnosis-evidence-head">
                              <div className="diagnosis-evidence-rule-wrap">
                                <span className={['mono', ruleHeaderClass].filter(Boolean).join(' ')} title="Deterministic diagnosis rule id">{ev.rule_id}</span>
                                {severity !== 'neutral' && (
                                  <span className={severity === 'error' ? 'diagnosis-severity-pill error' : 'diagnosis-severity-pill warn'}>
                                    {severity === 'error' ? 'Failure' : 'Warning'}
                                  </span>
                                )}
                              </div>
                              <span className="muted diagnosis-evidence-scope">Scope: {evidenceScopeLabel(ev)}</span>
                            </div>
                            <div className="diagnosis-evidence-message">{ev.message}</div>
                          </li>
                        )
                      })}
                    </ol>
                  </>
                ) : (
                  <p className="muted">No evidence items for this diagnosis.</p>
                )}
              </div>
            ) : (
              <p className="muted">No diagnosis loaded yet. Fetch a trace above, or ingest a trace first.</p>
            )}
          </div>
          <details className="glass card trace-raw-json-details">
            <summary className="trace-raw-json-summary">Raw trace & diagnosis JSON (for debugging)</summary>
            <div className="trace-raw-json-body">
              <h3 className="detail-section-heading">Trace JSON</h3>
              <pre>{traceDetail ? JSON.stringify(traceDetail, null, 2) : 'No trace loaded yet.'}</pre>
              <h3 className="detail-section-heading">Diagnosis JSON</h3>
              <pre>{diagnosis ? JSON.stringify(diagnosis, null, 2) : 'No diagnosis loaded yet.'}</pre>
            </div>
          </details>
        </section>
      )}

      {tab === 'steps' && (
        <section className="panel grid-two steps-layout">
          <article className="glass card steps-query-card">
            <h3>GET /v1/traces/steps</h3>
            <div className="steps-query-fields">
              <label>Step Type<input value={stepsType} onChange={(e) => setStepsType(e.target.value)} placeholder="tool_call" /></label>
              <label>Days<input type="number" min={1} max={365} value={stepsDays} onChange={(e) => setStepsDays(Number(e.target.value))} /></label>
              <label>has_error
                <select value={stepsErrorOnly === null ? 'all' : String(stepsErrorOnly)} onChange={(e) => setStepsErrorOnly(e.target.value === 'all' ? null : e.target.value === 'true')}>
                  <option value="all">all</option><option value="true">true</option><option value="false">false</option>
                </select>
              </label>
            </div>
          </article>
          <article className="glass card step-results-card">
            <h3>Step Results ({steps.length})</h3>
            <p className="muted">
              Click a row to open that trace on the Traces tab with the step selected.
            </p>
            {steps.length === 0 ? (
              <p className="muted">
                {stepsListLoading ? 'Loading…' : stepsEverQueried ? 'No steps matched your filters.' : 'Loading…'}
              </p>
            ) : (
              <div className="step-results-scroll" ref={stepsListRef} onScroll={onStepsListScroll}>
                <table className="step-results-table">
                  <thead>
                    <tr>
                      <th>trace_id</th>
                      <th>step_id</th>
                      <th>type</th>
                      <th>env</th>
                      <th>started</th>
                      <th>error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {steps.map((row) => (
                      <tr
                        key={`${row.trace_id}-${row.step_id}-${row.trace_started_at}`}
                        className="step-results-row"
                        tabIndex={0}
                        onClick={(e) => handleStepRowClick(row, e)}
                        onDoubleClick={handleStepRowDoubleClick}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            void runBusy('steps_open_trace', () => openTraceFromStepSummary(row))
                          }
                        }}
                      >
                        <td className="mono">{row.trace_id}</td>
                        <td className="mono">{row.step_id}</td>
                        <td>{row.step_type}</td>
                        <td>{row.environment}</td>
                        <td>{row.trace_started_at}</td>
                        <td className={row.error ? 'step-error-cell' : 'step-error-cell empty'}>{row.error ?? ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {stepsLoadingMore && (
                  <div className="loading-row steps-loading-more">
                    <span className="spinner"></span>
                    <span>Loading more steps...</span>
                  </div>
                )}
                {!stepsHasMore && steps.length > 0 && (
                  <p className="muted steps-end-note">End of results.</p>
                )}
              </div>
            )}
          </article>
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

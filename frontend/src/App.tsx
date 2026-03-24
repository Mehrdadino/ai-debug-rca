import { useMemo, useState } from 'react'
import './App.css'

type TabKey = 'dashboard' | 'ingest' | 'traces' | 'steps' | 'admin' | 'testing'
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

function App() {
  const [tab, setTab] = useState<TabKey>('dashboard')
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:8000')
  const [tenantId, setTenantId] = useState('org_demo')
  const [apiKey, setApiKey] = useState('')
  const [jwtToken, setJwtToken] = useState('')
  const [adminToken, setAdminToken] = useState('')

  const [toast, setToast] = useState('')
  const [error, setError] = useState('')
  const [health, setHealth] = useState('unknown')

  const [traceList, setTraceList] = useState<TraceSummary[]>([])
  const [traceLimit, setTraceLimit] = useState(25)
  const [traceIdLookup, setTraceIdLookup] = useState('')
  const [traceEnvironment, setTraceEnvironment] = useState<TraceEnvironment>('prod')
  const [traceDetail, setTraceDetail] = useState<Record<string, unknown> | null>(null)
  const [diagnosis, setDiagnosis] = useState<Record<string, unknown> | null>(null)

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
    setToast(message)
    window.setTimeout(() => setToast(''), 2200)
  }

  async function checkHealth(): Promise<void> {
    try {
      const res = await fetch(`${baseUrl}/health`)
      const payload = await parseResponse<{ status: string }>(res)
      setHealth(payload.status)
      notify('Health check successful')
    } catch (e) {
      setHealth('down')
      setError(formatRequestError(e))
    }
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

  async function fetchTraceDetail(): Promise<void> {
    if (!traceIdLookup.trim()) return setError('Trace ID is required')
    try {
      const t = await apiFetch<Record<string, unknown>>(`/v1/traces/${traceIdLookup.trim()}?environment=${traceEnvironment}`)
      const d = await apiFetch<Record<string, unknown>>(`/v1/traces/${traceIdLookup.trim()}/diagnosis?environment=${traceEnvironment}`)
      setTraceDetail(t)
      setDiagnosis(d)
      notify('Trace and diagnosis loaded')
    } catch (e) {
      setError(formatRequestError(e))
      setTraceDetail(null)
      setDiagnosis(null)
    }
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
        <div>
          <p className="eyebrow">AI Debug RCA</p>
          <h1>Observability Console</h1>
        </div>
        <div className="status">
          <span className={`dot ${health === 'ok' ? 'ok' : health === 'down' ? 'down' : ''}`}></span>
          <span>{health === 'unknown' ? 'Not checked' : `Health: ${health}`}</span>
        </div>
      </header>

      <section className="settings glass">
        <h2>Connection & Auth</h2>
        <div className="grid">
          <label>Backend Base URL<input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} /></label>
          <label>Tenant ID (dev mode)<input value={tenantId} onChange={(e) => setTenantId(e.target.value)} /></label>
          <label>API Key (optional)<input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk_test_..." /></label>
          <label>JWT Bearer (optional)<input value={jwtToken} onChange={(e) => setJwtToken(e.target.value)} placeholder="eyJhbGci..." /></label>
          <label>Admin Token (admin tab)<input value={adminToken} onChange={(e) => setAdminToken(e.target.value)} /></label>
        </div>
        <div className="actions">
          <button onClick={() => void checkHealth()}>Check Health</button>
          <button className="secondary" onClick={() => void refreshTraces()}>Refresh Traces</button>
          <div><strong>Auth mode:</strong> {authSummary}</div>
        </div>
      </section>

      <nav className="tabs">
        {[
          ['dashboard', 'Dashboard'],
          ['ingest', 'Ingest'],
          ['traces', 'Trace Explorer'],
          ['steps', 'Steps'],
          ['admin', 'Admin'],
          ['testing', 'Test Data'],
        ].map(([key, label]) => (
          <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key as TabKey)}>{label}</button>
        ))}
      </nav>

      {error && <div className="alert error">{error}</div>}
      {toast && <div className="alert toast">{toast}</div>}

      {tab === 'dashboard' && (
        <section className="panel grid-two">
          <article className="glass card">
            <h3>Quick Overview</h3>
            <p>Recent traces loaded: {traceList.length}</p>
            <p>Current tenant: {tenantId || 'n/a'}</p>
            <p>API base: {baseUrl}</p>
            <div className="actions">
              <button onClick={() => void refreshTraces()}>Reload Traces</button>
              <button className="secondary" onClick={() => void checkHealth()}>Ping Health</button>
            </div>
          </article>
          <article className="glass card">
            <h3>Last 10 Traces</h3>
            <ul className="list">
              {traceList.slice(0, 10).map((t) => (
                <li key={`${t.trace_id}-${t.environment}`}>
                  <button className="link" onClick={() => { setTraceIdLookup(t.trace_id); setTraceEnvironment(t.environment); setTab('traces') }}>
                    {t.trace_id.slice(0, 8)}... ({t.status}, {t.step_count} steps)
                  </button>
                </li>
              ))}
            </ul>
          </article>
        </section>
      )}

      {tab === 'ingest' && (
        <section className="panel grid-two">
          <article className="glass card">
            <h3>POST /v1/traces</h3>
            <textarea value={singleTraceBody} onChange={(e) => setSingleTraceBody(e.target.value)} />
            <div className="actions">
              <button onClick={() => void ingestSingleTrace()}>Send Single Trace</button>
              <button className="secondary" onClick={() => setSingleTraceBody(JSON.stringify(buildTrace(tenantId || 'org_demo', 'success', []), null, 2))}>Reset Template</button>
            </div>
          </article>
          <article className="glass card">
            <h3>POST /v1/traces/batch</h3>
            <textarea value={batchBody} onChange={(e) => setBatchBody(e.target.value)} />
            <div className="actions"><button onClick={() => void ingestBatch()}>Send Batch</button></div>
          </article>
        </section>
      )}

      {tab === 'traces' && (
        <section className="panel grid-two">
          <article className="glass card">
            <h3>Trace Query</h3>
            <div className="grid">
              <label>Trace ID<input value={traceIdLookup} onChange={(e) => setTraceIdLookup(e.target.value)} /></label>
              <label>Environment
                <select value={traceEnvironment} onChange={(e) => setTraceEnvironment(e.target.value as TraceEnvironment)}>
                  <option value="prod">prod</option><option value="staging">staging</option><option value="dev">dev</option><option value="critical">critical</option>
                </select>
              </label>
              <label>List Limit<input type="number" min={1} max={200} value={traceLimit} onChange={(e) => setTraceLimit(Number(e.target.value))} /></label>
            </div>
            <div className="actions">
              <button onClick={() => void fetchTraceDetail()}>Fetch Trace + Diagnosis</button>
              <button className="secondary" onClick={() => void refreshTraces()}>Refresh Trace List</button>
            </div>
            <ul className="list">
              {traceList.map((t) => (
                <li key={`${t.trace_id}-${t.environment}`}>
                  <button className="link" onClick={() => { setTraceIdLookup(t.trace_id); setTraceEnvironment(t.environment) }}>
                    {t.trace_id} • {t.environment} • {t.status}
                  </button>
                </li>
              ))}
            </ul>
          </article>
          <article className="glass card">
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
            <div className="actions"><button onClick={() => void refreshSteps()}>Run Step Query</button></div>
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
              <button onClick={() => void fetchLimits()}>Load Limits</button>
              <button className="secondary" onClick={() => void saveLimits()}>Save Limits</button>
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
              <button onClick={() => void generateScenario('minimal')}>Minimal Trace</button>
              <button onClick={() => void generateScenario('step_error')}>Step Error Scenario</button>
              <button onClick={() => void generateScenario('empty_retrieval')}>Empty Retrieval Scenario</button>
              <button onClick={() => void generateScenario('rag')}>RAG Multi-Step Scenario</button>
              <button className="secondary" onClick={() => void generateScenario('batch')}>Batch Scenario</button>
            </div>
          </article>
        </section>
      )}
    </div>
  )
}

export default App

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { NavLink, Route, Routes, useParams } from 'react-router-dom'
import { BrowserRouter } from 'react-router-dom'
import {
  ArrowRight,
  BrainCircuit,
  Briefcase,
  CheckCircle,
  Compass,
  Edit3,
  FileText,
  History,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  XCircle,
} from 'lucide-react'
import './App.css'

const API_BASE =
  typeof window !== 'undefined' && window.location.port === '5173'
    ? `http://${window.location.hostname || 'localhost'}:8000/api`
    : '/api'

// =========================================================================
// TYPES
// =========================================================================

type SystemStatus = {
  gemini: { available: boolean; model: string; configured: boolean }
  mongodb: { connected: boolean; is_mock: boolean; database: string; message: string }
  hindsight: { available: boolean; state: string; message: string }
  organization_id: string
}

type ContractItem = {
  id: string
  name: string
  vendor: string
  status: string
  risk_score: number
  summary?: string
  upload_date?: string
}

type MemoryEvidence = {
  content: string
  topic?: string
  contract_id?: string
  clause_id?: string
  historical_decision?: string
  confidence?: string
  final_wording?: string
  date?: string
}

type ClauseItem = {
  clause_id: string
  category: string
  title: string
  original_text: string
  location?: string
  risk_level: string
  risk_reason?: string
  risk_factors?: string[]
  contract_facts?: string[]
  ai_inference?: string[]
  analysis_source?: string
  memory_status?: string
  exception_detected?: boolean
  exception_evidence?: boolean
  suggested_text: string
  reason: string
  why_suggestion?: string
  memory_evidence: MemoryEvidence[]
  confidence: string
  human_decision?: string
  recommended_action?: string
}

type DashboardData = {
  kpis: {
    contracts_reviewed: number
    clauses_analyzed: number
    recommendations: number
    high_risk_clauses: number
    memory_backed_recommendations: number
    accepted: number
    modified: number
    rejected: number
    memories_retained: number
    preferences_learned: number
    exceptions_detected: number
    hindsight_status: { available: boolean; state: string; message: string }
    mongodb_status: { connected: boolean; is_mock: boolean; message: string }
    gemini_status: { available: boolean; model: string }
  }
  learning_progress: Array<{ interaction: string; status: string; timestamp?: string }>
  recent_contracts: ContractItem[]
}

type DecisionAuditItem = {
  contract_id: string
  clause_id: string
  clause_type: string
  decision: string
  original_text?: string
  ai_proposal?: string
  final_text?: string
  reason?: string
  created_at?: string
  timestamp?: string
  memory_action?: string
  hindsight_memory_id?: string
}

type PlaybookItem = {
  clause_type: string
  organizational_position: string
  historical_evidence: string
  accepted_count: number
  modified_count: number
  rejected_count: number
  exceptions: string
  support_level: string
  last_updated: string
  supporting_memories?: Array<{ contract_id: string; clause_id: string; decision: string; text: string }>
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'Unknown error'
}

async function readResponseError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') return payload.detail
  } catch {
    return `${fallback} (${response.status}).`
  }
  return `${fallback} (${response.status}).`
}

// =========================================================================
// LAYOUT & HEADER WITH SYSTEM STATUS
// =========================================================================

function AppLayout() {
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/system/status`)
      .then((res) => res.ok ? res.json() : null)
      .then((data: SystemStatus | null) => { if (data) setSysStatus(data) })
      .catch(() => {})
  }, [])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-badge"><BrainCircuit size={22} /></div>
          <div>
            <div className="brand-title">ContractMind AI</div>
            <div className="brand-subtitle">Every contract teaches the agent how your organization negotiates.</div>
          </div>
        </div>

        {sysStatus ? (
          <div className="system-status-bar" title="Live status of reasoning, persistence, and memory engines">
            <span className="status-indicator">
              <span className={sysStatus.gemini.available ? 'dot-green' : 'dot-amber'} />
              Gemini: {sysStatus.gemini.available ? sysStatus.gemini.model : 'Fallback Rules'}
            </span>
            <span>•</span>
            <span className="status-indicator">
              <span className={sysStatus.mongodb.connected ? 'dot-green' : 'dot-amber'} />
              MongoDB: {sysStatus.mongodb.is_mock ? 'In-Memory' : 'Connected'}
            </span>
            <span>•</span>
            <span className="status-indicator">
              <span className={sysStatus.hindsight.available ? 'dot-green' : 'dot-amber'} />
              Hindsight: {sysStatus.hindsight.state}
            </span>
          </div>
        ) : null}

        <nav className="nav">
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/dashboard">Dashboard</NavLink>
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/contracts">Contracts</NavLink>
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/memory">Memory Explorer</NavLink>
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/reflect">What We've Learned</NavLink>
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/playbook">Playbook</NavLink>
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/history">Timeline & Audit</NavLink>
          <NavLink className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} to="/demo">Demo</NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/review/:id" element={<ReviewPage />} />
        <Route path="/memory" element={<MemoryExplorerPage />} />
        <Route path="/reflect" element={<ReflectPage />} />
        <Route path="/playbook" element={<PlaybookPage />} />
        <Route path="/preferences" element={<PlaybookPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/demo" element={<DemoPage />} />
      </Routes>

      <footer className="legal-disclaimer">
        AI-generated contract analysis and redline suggestions are provided for review assistance only. Final contract decisions must be made by an authorized legal professional.
      </footer>
    </div>
  )
}

// =========================================================================
// DASHBOARD PAGE
// =========================================================================

function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/dashboard`)
      .then((res) => {
        if (!res.ok) throw new Error(`Dashboard unavailable (${res.status}).`)
        return res.json() as Promise<DashboardData>
      })
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)))
  }, [])

  const kpis = data?.kpis
  const cards = [
    { label: 'Contracts Reviewed', value: kpis?.contracts_reviewed ?? '—', trend: 'In organizational repository' },
    { label: 'Clauses Analyzed', value: kpis?.clauses_analyzed ?? '—', trend: 'Structured risk reviews' },
    { label: 'High Risk Clauses', value: kpis?.high_risk_clauses ?? '—', trend: 'Identified by Gemini reasoning' },
    { label: 'Memory-Backed Suggestions', value: kpis?.memory_backed_recommendations ?? '—', trend: 'Informed by Hindsight recall' },
    { label: 'Approved (Accepted)', value: kpis?.accepted ?? '—', trend: 'Confirmed standard positions' },
    { label: 'Modified (Edited)', value: kpis?.modified ?? '—', trend: 'Learned teacher signals' },
    { label: 'Rejected', value: kpis?.rejected ?? '—', trend: 'Negotiated exceptions' },
    { label: 'Memories Retained', value: kpis?.memories_retained ?? '—', trend: 'Confirmed Hindsight RETAIN' },
  ]

  return (
    <div>
      <section className="dashboard-grid">
        {cards.map((card) => (
          <div key={card.label} className="stat-card">
            <div className="stat-label">{card.label}</div>
            <div className="stat-value">{card.value}</div>
            <div className="stat-trend">{card.trend}</div>
          </div>
        ))}
      </section>

      {error ? <div className="notice error">{error}</div> : null}
      {!data && !error ? <div className="notice">Loading dashboard metrics…</div> : null}

      <section className="panel workflow-panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">The ContractMind Learning Loop</div>
            <p className="workflow-intro">Every contract teaches the agent how your organization negotiates.</p>
          </div>
          <Sparkles size={22} color="#2563eb" />
        </div>
        <div className="workflow-phases">
          <div className="workflow-phase">
            <div className="workflow-phase-label">01 · Understand</div>
            <ol>
              <li>DOCX / Text Parsing</li>
              <li>Clause Boundary Detection</li>
              <li>Gemini Risk Analysis</li>
            </ol>
            <NavLink to="/contracts" className="workflow-link">Upload contract <ArrowRight size={14} /></NavLink>
          </div>
          <div className="workflow-phase">
            <div className="workflow-phase-label">02 · Recall</div>
            <ol>
              <li>Hindsight RECALL query</li>
              <li>Retrieve similar lawyer decisions</li>
              <li>Surface memory evidence</li>
            </ol>
            <NavLink to="/memory" className="workflow-link">Explore memory <ArrowRight size={14} /></NavLink>
          </div>
          <div className="workflow-phase">
            <div className="workflow-phase-label">03 · Reason & Review</div>
            <ol>
              <li>Gemini redline synthesis</li>
              <li>Lawyer review workspace</li>
              <li>Accept / Edit / Reject</li>
            </ol>
            <NavLink to="/contracts" className="workflow-link">Open review <ArrowRight size={14} /></NavLink>
          </div>
          <div className="workflow-phase">
            <div className="workflow-phase-label">04 · Retain & Reflect</div>
            <ol>
              <li>Hindsight RETAIN decision</li>
              <li>Save audit trace in MongoDB</li>
              <li>Reflect on emerging patterns</li>
            </ol>
            <NavLink to="/reflect" className="workflow-link">What we've learned <ArrowRight size={14} /></NavLink>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Recent Contracts</div>
            <Briefcase size={18} color="#2563eb" />
          </div>
          <div className="contract-list">
            {(data?.recent_contracts ?? []).map((contract) => (
              <NavLink key={contract.id} className="contract-row" to={`/review/${contract.id}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong>{contract.name}</strong>
                  <span className={`badge ${contract.risk_score > 75 ? 'badge-high' : contract.risk_score > 50 ? 'badge-medium' : 'badge-low'}`}>
                    Risk {contract.risk_score}
                  </span>
                </div>
                <div className="contract-meta" style={{ marginTop: '4px', fontSize: '0.8rem', color: '#64748b' }}>
                  {contract.vendor} • Status: {contract.status}
                </div>
              </NavLink>
            ))}
            {data && !data.recent_contracts?.length ? <div className="empty-state">No contracts uploaded yet.</div> : null}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div className="panel-title">Recent Learning Progress</div>
            <History size={18} color="#2563eb" />
          </div>
          <div className="timeline">
            {(data?.learning_progress ?? []).map((item, idx) => (
              <div key={idx} className="timeline-item" style={{ padding: '8px 0', borderBottom: '1px solid #f1f5f9' }}>
                <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>{item.interaction}</div>
                <div style={{ color: '#475569', fontSize: '0.8rem', marginTop: '2px' }}>{item.status}</div>
              </div>
            ))}
            {data && !data.learning_progress?.length ? <div className="empty-state">No learning events recorded yet.</div> : null}
          </div>
        </div>
      </section>
    </div>
  )
}

// =========================================================================
// CONTRACTS & UPLOAD PAGE
// =========================================================================

function ContractsPage() {
  const [contracts, setContracts] = useState<ContractItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploadTab, setUploadTab] = useState<'file' | 'paste'>('file')

  const [name, setName] = useState('')
  const [vendor, setVendor] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [pastedText, setPastedText] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')

  const loadContracts = async () => {
    try {
      const res = await fetch(`${API_BASE}/contracts`)
      if (!res.ok) throw new Error(await readResponseError(res, 'Could not load contracts'))
      setContracts(await res.json() as ContractItem[])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadContracts().catch((err) => setError(getErrorMessage(err)))
  }, [])

  const handleUpload = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setUploading(true)
    setError('')
    setUploadMessage('')

    try {
      const body = new FormData()
      body.append('name', name.trim())
      body.append('vendor', vendor.trim())

      if (uploadTab === 'file') {
        if (!file) throw new Error('Please select a DOCX, PDF, or TXT file.')
        body.append('file', file)
      } else {
        if (!pastedText.trim()) throw new Error('Please enter or paste contract text.')
        body.append('pasted_text', pastedText.trim())
      }

      const res = await fetch(`${API_BASE}/contracts/upload`, { method: 'POST', body })
      if (!res.ok) throw new Error(await readResponseError(res, 'Upload failed'))
      const payload = await res.json()

      setUploadMessage(`Contract '${payload.name}' uploaded successfully. Ready for Gemini clause review!`)
      setName('')
      setVendor('')
      setFile(null)
      setPastedText('')
      await loadContracts()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="panel full-panel">
      <div className="panel-header">
        <div className="panel-title">Contract Repository</div>
        <FileText size={20} color="#2563eb" />
      </div>

      <div style={{ background: '#f8fafc', padding: '20px', borderRadius: '14px', border: '1px solid #e2e8f0' }}>
        <h4 style={{ margin: '0 0 14px', color: '#0f172a' }}>New Contract Review</h4>

        <div className="tab-selector">
          <button
            type="button"
            className={`tab-btn ${uploadTab === 'file' ? 'active' : ''}`}
            onClick={() => setUploadTab('file')}
          >
            Upload DOCX / PDF Document
          </button>
          <button
            type="button"
            className={`tab-btn ${uploadTab === 'paste' ? 'active' : ''}`}
            onClick={() => setUploadTab('paste')}
          >
            Paste Contract Text
          </button>
        </div>

        <form onSubmit={handleUpload}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
            <label>
              <strong>Contract Title</strong>
              <input
                required
                style={{ width: '100%', padding: '9px', borderRadius: '8px', border: '1px solid #cbd5e1', marginTop: '4px' }}
                placeholder="e.g. Master Services Agreement"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              <strong>Counterparty / Vendor</strong>
              <input
                required
                style={{ width: '100%', padding: '9px', borderRadius: '8px', border: '1px solid #cbd5e1', marginTop: '4px' }}
                placeholder="e.g. CloudScale Technologies"
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
              />
            </label>
          </div>

          {uploadTab === 'file' ? (
            <label style={{ display: 'block', marginBottom: '14px' }}>
              <strong>Select Document (DOCX, PDF, or TXT)</strong>
              <input
                type="file"
                accept=".docx,.pdf,.txt"
                style={{ display: 'block', marginTop: '6px' }}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          ) : (
            <label style={{ display: 'block', marginBottom: '14px' }}>
              <strong>Paste Full Contract Text</strong>
              <textarea
                rows={6}
                style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #cbd5e1', marginTop: '4px', font: 'inherit' }}
                placeholder="Paste contract provisions here..."
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
              />
            </label>
          )}

          <button className="primary-btn" type="submit" disabled={uploading}>
            {uploading ? 'Processing Contract…' : 'Add to Review Queue'}
          </button>
        </form>

        {error ? <div className="notice error">{error}</div> : null}
        {uploadMessage ? <div className="notice success">{uploadMessage}</div> : null}
      </div>

      <div style={{ marginTop: '28px' }}>
        <h3>Uploaded Contracts ({contracts.length})</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Contract Name</th>
              <th>Vendor</th>
              <th>Status</th>
              <th>Risk Score</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? <tr><td colSpan={6}>Loading contract repository…</td></tr> : null}
            {contracts.map((c) => (
              <tr key={c.id}>
                <td><code>{c.id}</code></td>
                <td><strong>{c.name}</strong></td>
                <td>{c.vendor}</td>
                <td><span className="badge badge-pending">{c.status.toUpperCase()}</span></td>
                <td>
                  <span className={`badge ${c.risk_score > 75 ? 'badge-high' : c.risk_score > 50 ? 'badge-medium' : 'badge-low'}`}>
                    {c.risk_score}
                  </span>
                </td>
                <td><NavLink className="link-btn" to={`/review/${c.id}`}>Open Review</NavLink></td>
              </tr>
            ))}
            {!loading && contracts.length === 0 ? <tr><td colSpan={6}>No contracts found.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// =========================================================================
// MAIN REVIEW WORKSPACE (3-PANEL LAYOUT)
// =========================================================================

function ReviewPage() {
  const { id } = useParams()
  const [contract, setContract] = useState<ContractItem | null>(null)
  const [clauses, setClauses] = useState<ClauseItem[]>([])
  const [selectedClauseId, setSelectedClauseId] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisStep, setAnalysisStep] = useState('')
  const [error, setError] = useState('')
  const [decisionFeedback, setDecisionFeedback] = useState('')

  // Editing state
  const [isEditing, setIsEditing] = useState(false)
  const [editedText, setEditedText] = useState('')

  // Rejection state
  const [isRejecting, setIsRejecting] = useState(false)
  const [rejectionReason, setRejectionReason] = useState('')

  const [savingDecision, setSavingDecision] = useState(false)

  // Chat state
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [sendingChat, setSendingChat] = useState(false)

  const loadContractAndClauses = useCallback(async () => {
    try {
      const [cRes, clRes] = await Promise.all([
        fetch(`${API_BASE}/contracts/${id}`),
        fetch(`${API_BASE}/contracts/${id}/clauses`),
      ])
      if (cRes.ok) setContract(await cRes.json() as ContractItem)
      if (clRes.ok) {
        const loadedClauses = await clRes.json() as ClauseItem[]
        setClauses(loadedClauses)
        if (loadedClauses.length > 0 && !selectedClauseId) {
          setSelectedClauseId(loadedClauses[0].clause_id)
        }
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [id, selectedClauseId])

  useEffect(() => {
    loadContractAndClauses()
  }, [loadContractAndClauses])

  // Load chat messages from MongoDB
  const loadChat = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations/${id}/messages`)
      if (res.ok) {
        const data = await res.json()
        setChatMessages(data.messages || [])
      }
    } catch {}
  }, [id])

  useEffect(() => {
    if (chatOpen) loadChat()
  }, [chatOpen, loadChat])

  const sendChatMessage = async (e: FormEvent) => {
    e.preventDefault()
    if (!chatInput.trim() || sendingChat) return
    const text = chatInput.trim()
    setChatInput('')
    setSendingChat(true)

    // Optimistic user bubble
    const userMsg: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    setChatMessages((prev) => [...prev, userMsg])

    try {
      const res = await fetch(`${API_BASE}/conversations/${id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      if (res.ok) {
        const data = await res.json()
        setChatMessages((prev) => [
          ...prev,
          { id: `reply-${Date.now()}`, role: 'assistant', content: data.reply, timestamp: data.timestamp },
        ])
      }
    } catch {
      setChatMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: 'assistant', content: 'Could not contact AI assistant.', timestamp: new Date().toISOString() },
      ])
    } finally {
      setSendingChat(false)
    }
  }

  const handleAnalyze = async () => {
    setAnalyzing(true)
    setError('')
    setDecisionFeedback('')
    setAnalysisStep('Reading contract document…')

    try {
      setAnalysisStep('Extracting clauses & checking boundaries…')
      const res = await fetch(`${API_BASE}/contracts/${id}/analyze`, { method: 'POST' })
      if (!res.ok) throw new Error(await readResponseError(res, 'Analysis failed'))
      setAnalysisStep('Querying Hindsight memory & generating Gemini redlines…')
      await loadContractAndClauses()
      setDecisionFeedback('Analysis complete! Review the suggested redlines and memory evidence.')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setAnalyzing(false)
      setAnalysisStep('')
    }
  }

  const activeClause = clauses.find((c) => c.clause_id === selectedClauseId) || clauses[0]

  const submitDecision = async (
    decision: 'accept' | 'modify' | 'reject',
    customText?: string,
    reason?: string,
  ) => {
    if (!activeClause) return
    setSavingDecision(true)
    setError('')
    setDecisionFeedback('')

    try {
      const payload = {
        decision,
        ...(customText ? { edited_text: customText } : {}),
        ...(reason ? { reason } : {}),
      }

      const res = await fetch(`${API_BASE}/clauses/${activeClause.clause_id}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(await readResponseError(res, 'Could not save decision'))
      const result = await res.json()

      setIsEditing(false)
      setIsRejecting(false)
      setRejectionReason('')
      setDecisionFeedback(result.message || 'Decision recorded.')
      await loadContractAndClauses()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSavingDecision(false)
    }
  }

  const handleRetryMemory = async () => {
    if (!activeClause) return
    setSavingDecision(true)
    try {
      const res = await fetch(`${API_BASE}/clauses/${activeClause.clause_id}/retry-memory`, { method: 'POST' })
      if (!res.ok) throw new Error(await readResponseError(res, 'Retry failed'))
      const payload = await res.json()
      setDecisionFeedback(payload.message || 'Memory save retried.')
      await loadContractAndClauses()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setSavingDecision(false)
    }
  }

  return (
    <div>
      {/* Top Banner */}
      <div className="panel full-panel" style={{ padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ margin: 0, fontSize: '1.4rem' }}>{contract?.name || `Contract ${id}`}</h2>
            <span className={`badge ${contract && contract.risk_score > 75 ? 'badge-high' : contract && contract.risk_score > 50 ? 'badge-medium' : 'badge-low'}`}>
              Risk {contract?.risk_score ?? 0}
            </span>
            <span className="badge badge-pending">{contract?.status?.toUpperCase()}</span>
          </div>
          <div style={{ color: '#64748b', fontSize: '0.85rem', marginTop: '4px' }}>
            Vendor: <strong>{contract?.vendor || 'Unknown'}</strong> • Clauses: {clauses.length}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button className="action-btn modify" onClick={handleAnalyze} disabled={analyzing}>
            <RefreshCw size={15} className={analyzing ? 'spin' : ''} />
            {analyzing ? 'Analyzing with Gemini…' : 'Analyze / Re-Analyze'}
          </button>
          <button className="tab-btn" onClick={() => setChatOpen(!chatOpen)}>
            <MessageSquare size={15} />
            {chatOpen ? 'Hide Chat' : 'Contract Chat'}
          </button>
        </div>
      </div>

      {analysisStep ? (
        <div className="localized-progress">
          <RefreshCw size={16} className="spin" />
          <span>{analysisStep}</span>
        </div>
      ) : null}

      {error ? <div className="notice error">{error}</div> : null}
      {decisionFeedback ? <div className="notice success">{decisionFeedback}</div> : null}

      {/* Main 3-Panel Workspace */}
      <div className="review-workspace">
        {/* Left Panel: Clause List */}
        <aside className="clause-sidebar">
          <div className="clause-sidebar-title">Contract Clauses ({clauses.length})</div>
          {loading ? <div>Loading clauses…</div> : null}
          {clauses.map((cl) => {
            const isSelected = cl.clause_id === (activeClause?.clause_id ?? '')
            return (
              <button
                key={cl.clause_id}
                type="button"
                className={`clause-nav-item ${isSelected ? 'active' : ''}`}
                onClick={() => {
                  setSelectedClauseId(cl.clause_id)
                  setIsEditing(false)
                  setIsRejecting(false)
                  setError('')
                  setDecisionFeedback('')
                }}
              >
                <div className="clause-nav-header">
                  <span className="clause-nav-category">{cl.category}</span>
                  <span className={`badge badge-${cl.risk_level.toLowerCase()}`}>{cl.risk_level}</span>
                </div>
                <div className="clause-nav-location">{cl.location || 'Document'}</div>
                <div className="clause-nav-preview">{cl.original_text}</div>
                <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className={`badge ${cl.human_decision ? `badge-${cl.human_decision}` : 'badge-pending'}`}>
                    {cl.human_decision ? cl.human_decision.toUpperCase() : 'PENDING'}
                  </span>
                  {cl.analysis_source === 'MEMORY_INFORMED' ? (
                    <span style={{ fontSize: '0.68rem', color: '#2563eb', fontWeight: 700 }}>● Memory Precedent</span>
                  ) : null}
                </div>
              </button>
            )
          })}
          {!loading && clauses.length === 0 ? (
            <div className="empty-state">No clauses extracted. Click "Analyze / Re-Analyze" above.</div>
          ) : null}
        </aside>

        {/* Center Panel: Review & Redline */}
        <main className="review-center">
          {activeClause ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0 }}>{activeClause.title || activeClause.category}</h3>
                  <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{activeClause.location}</div>
                </div>
                <span className={`badge badge-${activeClause.risk_level.toLowerCase()}`}>{activeClause.risk_level} Risk</span>
              </div>

              {/* Original Clause */}
              <div style={{ marginTop: '16px' }}>
                <span className="stat-label">Original Clause Text</span>
                <div className="quote-box">{activeClause.original_text}</div>
              </div>

              {/* Facts vs AI Inferences */}
              {activeClause.contract_facts?.length || activeClause.ai_inference?.length ? (
                <div className="facts-inferences">
                  <div className="facts-col">
                    <h5>Current Contract Facts</h5>
                    <ul>
                      {activeClause.contract_facts?.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  </div>
                  <div className="inferences-col">
                    <h5>AI Legal Inference</h5>
                    <ul>
                      {activeClause.ai_inference?.map((inf, i) => <li key={i}>{inf}</li>)}
                    </ul>
                  </div>
                </div>
              ) : null}

              {/* Suggested Redline */}
              <div className="redline-box">
                <div className="redline-header">
                  <span className="redline-title">
                    {activeClause.analysis_source === 'MEMORY_INFORMED'
                      ? 'Memory-Informed Redline Proposal'
                      : 'AI Recommended Protective Redline'}
                  </span>
                  <span className="badge badge-low">
                    {activeClause.confidence ? `${activeClause.confidence} Confidence` : 'AI Suggested'}
                  </span>
                </div>
                <div className="redline-text">{activeClause.suggested_text || 'Standard commercial position.'}</div>
                <div style={{ marginTop: '10px', fontSize: '0.82rem', color: '#166534' }}>
                  <strong>Rationale:</strong> {activeClause.reason}
                </div>
              </div>

              {/* Edit Mode */}
              {isEditing ? (
                <div style={{ marginTop: '16px', background: '#eff6ff', padding: '16px', borderRadius: '12px', border: '1px solid #bfdbfe' }}>
                  <label htmlFor="edit-text">
                    <strong>Lawyer Redline Modification</strong>
                    <p style={{ margin: '4px 0 10px', fontSize: '0.8rem', color: '#1e40af' }}>
                      Edit the wording below. When you click <em>EDIT & TEACH</em>, this difference will be stored in MongoDB and retained in Hindsight to teach future contract reviews.
                    </p>
                  </label>
                  <textarea
                    id="edit-text"
                    rows={5}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #93c5fd', font: 'inherit' }}
                    value={editedText}
                    onChange={(e) => setEditedText(e.target.value)}
                  />
                  <div className="action-row">
                    <button
                      className="action-btn accept"
                      onClick={() => submitDecision('modify', editedText)}
                      disabled={savingDecision || !editedText.trim()}
                    >
                      <CheckCircle size={15} />
                      {savingDecision ? 'Saving…' : 'CONFIRM EDIT & TEACH'}
                    </button>
                    <button className="tab-btn" onClick={() => setIsEditing(false)}>Cancel</button>
                  </div>
                </div>
              ) : null}

              {/* Reject Mode */}
              {isRejecting ? (
                <div style={{ marginTop: '16px', background: '#fef2f2', padding: '16px', borderRadius: '12px', border: '1px solid #fecaca' }}>
                  <label htmlFor="reject-reason">
                    <strong>Rejection Reason (Negotiated Exception)</strong>
                    <p style={{ margin: '4px 0 10px', fontSize: '0.8rem', color: '#991b1b' }}>
                      Explaining why this recommendation is rejected allows Hindsight to learn enterprise exceptions.
                    </p>
                  </label>
                  <textarea
                    id="reject-reason"
                    rows={3}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #fca5a5', font: 'inherit' }}
                    placeholder="e.g. Approved 24-month cap as a strategic exception for tier-1 vendor..."
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                  />
                  <div className="action-row">
                    <button
                      className="action-btn reject"
                      onClick={() => submitDecision('reject', undefined, rejectionReason)}
                      disabled={savingDecision}
                    >
                      <XCircle size={15} />
                      {savingDecision ? 'Saving…' : 'CONFIRM REJECT & TEACH'}
                    </button>
                    <button className="tab-btn" onClick={() => setIsRejecting(false)}>Cancel</button>
                  </div>
                </div>
              ) : null}

              {/* Action Buttons Row */}
              {!isEditing && !isRejecting ? (
                <div className="action-row">
                  <button
                    className="action-btn accept"
                    onClick={() => submitDecision('accept', activeClause.suggested_text)}
                    disabled={savingDecision}
                  >
                    <CheckCircle size={16} />
                    ACCEPT & TEACH
                  </button>
                  <button
                    className="action-btn modify"
                    onClick={() => {
                      setIsEditing(true)
                      setIsRejecting(false)
                      setEditedText(activeClause.suggested_text || activeClause.original_text)
                    }}
                    disabled={savingDecision}
                  >
                    <Edit3 size={16} />
                    EDIT & TEACH
                  </button>
                  <button
                    className="action-btn reject"
                    onClick={() => {
                      setIsRejecting(true)
                      setIsEditing(false)
                    }}
                    disabled={savingDecision}
                  >
                    <XCircle size={16} />
                    REJECT & TEACH
                  </button>
                  {activeClause.memory_status === 'error' || activeClause.memory_status === 'failed' ? (
                    <button className="action-btn retry" onClick={handleRetryMemory} disabled={savingDecision}>
                      <RefreshCw size={15} />
                      RETRY MEMORY SAVE
                    </button>
                  ) : null}
                </div>
              ) : null}

              {/* Interactive Chat Drawer */}
              {chatOpen ? (
                <div className="chat-drawer">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>Contract Assistant (Stored in MongoDB)</strong>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Context: {contract?.name}</span>
                  </div>
                  <div className="chat-messages">
                    {chatMessages.length === 0 ? (
                      <div className="empty-state">Ask any question about this contract, clauses, or risks.</div>
                    ) : null}
                    {chatMessages.map((m) => (
                      <div key={m.id} className={`chat-bubble ${m.role}`}>
                        {m.content}
                      </div>
                    ))}
                    {sendingChat ? <div className="chat-bubble assistant">Thinking…</div> : null}
                  </div>
                  <form onSubmit={sendChatMessage} className="chat-form">
                    <input
                      className="chat-input"
                      placeholder="Ask the legal assistant about this clause..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                    />
                    <button className="primary-btn" type="submit" disabled={sendingChat}>Send</button>
                  </form>
                </div>
              ) : null}
            </>
          ) : (
            <div>Please select a clause to review.</div>
          )}
        </main>

        {/* Right Panel: Risk & Memory Evidence */}
        <aside className="review-right">
          {/* Risk Card */}
          <div className="risk-card">
            <div className="risk-header">
              <span className="risk-title">Risk Assessment</span>
              <ShieldAlert size={18} color="#dc2626" />
            </div>
            <div style={{ marginBottom: '8px' }}>
              <span className={`badge badge-${(activeClause?.risk_level || 'low').toLowerCase()}`}>
                {activeClause?.risk_level || 'Low'}
              </span>
            </div>
            <p style={{ margin: '6px 0', fontSize: '0.85rem', color: '#334155' }}>
              <strong>Why Risky:</strong> {activeClause?.risk_reason || 'Standard commercial provision.'}
            </p>
            {activeClause?.risk_factors?.length ? (
              <ul className="risk-concerns">
                {activeClause.risk_factors.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            ) : null}
            {activeClause?.recommended_action ? (
              <div style={{ marginTop: '10px', fontSize: '0.8rem', color: '#475569' }}>
                <strong>Recommended Action:</strong> {activeClause.recommended_action}
              </div>
            ) : null}
          </div>

          {/* Memory Evidence Card */}
          <div className="memory-card">
            <div className="memory-header">
              <span className="memory-title">Hindsight Memory</span>
              <BrainCircuit size={18} color="#2563eb" />
            </div>

            <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '8px' }}>
              {activeClause?.memory_evidence?.length
                ? `${activeClause.memory_evidence.length} historical decision(s) retrieved`
                : 'NO RELEVANT ORGANIZATIONAL MEMORY FOUND'}
            </div>

            {/* Why This Suggestion Banner */}
            <div style={{ padding: '10px', background: '#eff6ff', borderRadius: '8px', fontSize: '0.8rem', color: '#1e40af', marginBottom: '10px' }}>
              <strong>WHY THIS SUGGESTION?</strong>
              <div style={{ marginTop: '3px' }}>
                {activeClause?.why_suggestion || 'No relevant organizational memory found.'}
              </div>
            </div>

            {/* List Historical Matches */}
            {activeClause?.memory_evidence?.map((item, idx) => (
              <div key={idx} className="memory-match-item">
                <div className="memory-match-meta">
                  <span className={`badge ${item.historical_decision === 'ACCEPTED' ? 'badge-accepted' : item.historical_decision === 'EDITED' ? 'badge-edited' : 'badge-rejected'}`}>
                    {item.historical_decision || 'PRECEDENT'}
                  </span>
                  <span>{item.date ? item.date.slice(0, 10) : 'Past Decision'}</span>
                </div>
                <div className="memory-match-text">
                  <strong>Final wording:</strong> {item.final_wording || item.content}
                </div>
              </div>
            ))}

            {activeClause && (!activeClause.memory_evidence || activeClause.memory_evidence.length === 0) ? (
              <div className="empty-state">
                No past lawyer decisions match this clause type yet. Approving a redline will teach the agent for next time!
              </div>
            ) : null}
          </div>
        </aside>
      </div>
    </div>
  )
}

// =========================================================================
// MEMORY EXPLORER PAGE
// =========================================================================

function MemoryExplorerPage() {
  const [decisions, setDecisions] = useState<DecisionAuditItem[]>([])
  const [filterClause, setFilterClause] = useState('')
  const [filterDecision, setFilterDecision] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams()
    if (filterClause) params.append('clause_type', filterClause)
    if (filterDecision) params.append('decision', filterDecision)

    fetch(`${API_BASE}/memory/decisions?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        setDecisions(data.decisions || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [filterClause, filterDecision])

  const clauseTypes = [
    'Limitation of Liability',
    'Payment Terms',
    'Termination',
    'Confidentiality',
    'Indemnification',
    'Intellectual Property',
    'Data Protection',
    'Warranty',
    'Governing Law',
  ]

  return (
    <div className="panel full-panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Memory Explorer</div>
          <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Inspect historical decisions retained in Hindsight long-term organizational memory.
          </div>
        </div>
        <BrainCircuit size={22} color="#2563eb" />
      </div>

      {/* Filter Bar */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', margin: '14px 0 20px' }}>
        <select
          value={filterClause}
          onChange={(e) => setFilterClause(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
        >
          <option value="">All Clause Categories</option>
          {clauseTypes.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <select
          value={filterDecision}
          onChange={(e) => setFilterDecision(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
        >
          <option value="">All Decisions (Accept / Edit / Reject)</option>
          <option value="ACCEPT">Accepted</option>
          <option value="EDITED">Edited</option>
          <option value="REJECTED">Rejected</option>
        </select>
      </div>

      {loading ? <div>Loading organizational memory…</div> : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '16px' }}>
        {decisions.map((d, i) => (
          <article key={i} className="panel" style={{ padding: '16px', border: '1px solid #e2e8f0', background: '#ffffff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <strong>{d.clause_type}</strong>
              <span className={`badge ${d.decision === 'ACCEPT' || d.decision === 'ACCEPTED' ? 'badge-accepted' : d.decision === 'EDITED' || d.decision === 'MODIFY' ? 'badge-edited' : 'badge-rejected'}`}>
                {d.decision}
              </span>
            </div>
            <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '8px' }}>
              Contract: <strong>{d.contract_id}</strong> • {d.created_at?.slice(0, 10) || d.timestamp?.slice(0, 10)}
            </div>
            {d.final_text ? (
              <div style={{ background: '#f8fafc', padding: '10px', borderRadius: '6px', fontSize: '0.84rem', color: '#1e293b' }}>
                <strong>Approved Wording:</strong> {d.final_text}
              </div>
            ) : null}
            {d.reason ? (
              <div style={{ marginTop: '8px', fontSize: '0.8rem', color: '#b91c1c' }}>
                <strong>Reason / Exception:</strong> {d.reason}
              </div>
            ) : null}
            <div style={{ marginTop: '10px', fontSize: '0.74rem', color: '#059669' }}>
              Hindsight: {d.memory_action === 'retained' ? '✓ Retained as long-term preference' : 'Decision recorded in MongoDB'}
            </div>
          </article>
        ))}
        {!loading && decisions.length === 0 ? (
          <div className="empty-state">No historical decisions found matching the selected filters.</div>
        ) : null}
      </div>
    </div>
  )
}

// =========================================================================
// WHAT WE'VE LEARNED (HINDSIGHT REFLECT) PAGE
// =========================================================================

function ReflectPage() {
  const [reflection, setReflection] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<any>(null)
  const [error, setError] = useState('')

  const fetchReflection = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/memory/reflect`, { method: 'POST' })
      const data = await res.json()
      if (data.summary) {
        setReflection(data.summary)
      } else {
        setReflection(data.message || 'No organizational reflection available yet.')
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetch(`${API_BASE}/memory`)
      .then((res) => res.json())
      .then((data) => {
        setStatus(data.status)
        if (data.reflection) setReflection(data.reflection)
      })
      .catch(() => {})
  }, [])

  return (
    <div className="panel full-panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">What We've Learned</div>
          <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Hindsight Reflect identifies recurring positions, inconsistent positions, and negotiated exceptions.
          </div>
        </div>
        <button className="primary-btn" onClick={fetchReflection} disabled={loading}>
          {loading ? 'Reflecting…' : 'Trigger Hindsight Reflect'}
        </button>
      </div>

      {status ? (
        <div className="notice" style={{ marginBottom: '18px' }}>
          <strong>Hindsight Cloud Status:</strong> {status.state} — {status.message}
        </div>
      ) : null}

      {error ? <div className="notice error">{error}</div> : null}

      <div style={{ background: '#f8fafc', padding: '24px', borderRadius: '16px', border: '1px solid #e2e8f0' }}>
        <h3 style={{ margin: '0 0 12px', color: '#0f172a' }}>Organizational Reflection Summary</h3>
        {reflection ? (
          <div style={{ fontSize: '0.95rem', lineHeight: '1.7', color: '#1e293b', whiteSpace: 'pre-wrap' }}>
            {reflection}
          </div>
        ) : (
          <div className="empty-state">
            {status?.available
              ? 'No reflection recorded yet. Click "Trigger Hindsight Reflect" above to synthesize organizational lessons.'
              : 'Organizational memory reflection is unavailable until Hindsight Cloud credentials are configured.'}
          </div>
        )}
      </div>

      <div style={{ marginTop: '28px', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        <div className="panel" style={{ padding: '16px' }}>
          <h4>Recurring Positions</h4>
          <p style={{ fontSize: '0.84rem', color: '#475569' }}>
            Identifies positions that have received unanimous acceptance across multiple vendor negotiations (e.g. 12-month liability caps).
          </p>
        </div>
        <div className="panel" style={{ padding: '16px' }}>
          <h4>Inconsistent Positions</h4>
          <p style={{ fontSize: '0.84rem', color: '#475569' }}>
            Highlights clause categories where lawyers have edited AI proposals into differing language across departments.
          </p>
        </div>
        <div className="panel" style={{ padding: '16px' }}>
          <h4>Negotiated Exceptions</h4>
          <p style={{ fontSize: '0.84rem', color: '#475569' }}>
            Captures reasons given when proposals were rejected (e.g. strategic partner custom tiers or multi-year terms).
          </p>
        </div>
      </div>
    </div>
  )
}

// =========================================================================
// NEGOTIATION PLAYBOOK PAGE
// =========================================================================

function PlaybookPage() {
  const [playbook, setPlaybook] = useState<PlaybookItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/playbook`)
      .then((res) => res.json())
      .then((data) => {
        setPlaybook(data.playbook || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div className="panel full-panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Negotiation Playbook</div>
          <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Organization's canonical positions and evidence synthesized from lawyer decisions.
          </div>
        </div>
        <Compass size={22} color="#2563eb" />
      </div>

      {loading ? <div>Loading organizational playbook…</div> : null}

      <div className="playbook-grid">
        {playbook.map((item) => (
          <div key={item.clause_type} className="playbook-card">
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="stat-label">{item.clause_type}</span>
                <span className={`badge ${item.support_level === 'High' ? 'badge-low' : item.support_level === 'Medium' ? 'badge-medium' : 'badge-pending'}`}>
                  {item.support_level} Support
                </span>
              </div>
              <h4 style={{ margin: '0 0 10px', fontSize: '1.05rem', color: '#0f172a' }}>
                {item.organizational_position}
              </h4>
              <div style={{ fontSize: '0.82rem', color: '#475569', margin: '6px 0' }}>
                <strong>Evidence:</strong> {item.historical_evidence}
              </div>
              <div style={{ fontSize: '0.82rem', color: '#b45309', margin: '6px 0' }}>
                <strong>Exceptions:</strong> {item.exceptions}
              </div>
            </div>
            <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', color: '#64748b' }}>
              <span>Accepted: {item.accepted_count} · Edited: {item.modified_count}</span>
              <span>Updated: {item.last_updated?.slice(0, 10) || '—'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// =========================================================================
// LEARNING TIMELINE & AUDIT PAGE
// =========================================================================

function HistoryPage() {
  const [history, setHistory] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_BASE}/history`)
      .then((res) => res.json())
      .then((data) => {
        setHistory(data)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div className="panel full-panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Learning Timeline & Decision Audit</div>
          <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Traceable audit trail of every recall, AI inference, lawyer decision, and memory retention event.
          </div>
        </div>
        <History size={22} color="#2563eb" />
      </div>

      {loading ? <div>Loading audit logs…</div> : null}

      {/* Visual Learning Timeline */}
      <h3 style={{ marginTop: '12px' }}>Organizational Learning Progression</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', margin: '14px 0 28px' }}>
        <div className="panel" style={{ padding: '16px', background: '#f8fafc' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>Contract #1 (C001)</strong>
            <span className="badge badge-synthetic">DEMO DATA — SYNTHETIC</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>No Prior Memory</div>
          <p style={{ fontSize: '0.84rem', margin: '8px 0 0', color: '#334155' }}>
            Generic protective recommendation. Lawyer approves 12-month cap, teaching the agent.
          </p>
        </div>
        <div className="panel" style={{ padding: '16px', background: '#eff6ff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>Contract #2 (C005)</strong>
            <span className="badge badge-synthetic">DEMO DATA — SYNTHETIC</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#1d4ed8', marginTop: '4px' }}>Precedent Recalled</div>
          <p style={{ fontSize: '0.84rem', margin: '8px 0 0', color: '#1e3a8a' }}>
            Hindsight recalls C001 decision. Agent suggests 12-month cap with memory evidence.
          </p>
        </div>
        <div className="panel" style={{ padding: '16px', background: '#f0fdf4' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>Contract #3 (C015)</strong>
            <span className="badge badge-synthetic">DEMO DATA — SYNTHETIC</span>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#15803d', marginTop: '4px' }}>Exception Detected</div>
          <p style={{ fontSize: '0.84rem', margin: '8px 0 0', color: '#14532d' }}>
            Enterprise tier clause triggers custom review. Learned exception retained in Hindsight.
          </p>
        </div>
      </div>

      {/* Decision Audit Trail */}
      <h3>Decision Audit Trail</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {(history?.decisions ?? []).map((d: any, idx: number) => (
          <div key={idx} style={{ padding: '14px', background: 'white', border: '1px solid #e2e8f0', borderRadius: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong>{d.contract_id}</strong> • {d.clause_type} • <span className={`badge ${d.decision === 'accept' ? 'badge-accepted' : d.decision === 'modify' ? 'badge-edited' : 'badge-rejected'}`}>{(d.decision || '').toUpperCase()}</span>
              </div>
              <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{d.timestamp}</span>
            </div>
            {d.final_text ? (
              <div style={{ marginTop: '6px', fontSize: '0.84rem', color: '#1e293b' }}>
                <strong>Approved wording:</strong> {d.final_text}
              </div>
            ) : null}
            {d.rejection_reason ? (
              <div style={{ marginTop: '6px', fontSize: '0.84rem', color: '#b91c1c' }}>
                <strong>Reason:</strong> {d.rejection_reason}
              </div>
            ) : null}
            <div style={{ marginTop: '6px', fontSize: '0.75rem', color: '#64748b' }}>
              Hindsight RETAIN: <strong>{d.memory_action}</strong> {d.memory_status ? `(${d.memory_status})` : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// =========================================================================
// DEMO RUNNER PAGE
// =========================================================================

function DemoPage() {
  const [status, setStatus] = useState('Ready to run guided demo.')
  const [loading, setLoading] = useState(false)
  const [hasRun, setHasRun] = useState(false)

  const handleRun = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/demo/run`, { method: 'POST' })
      const data = await res.json()
      setStatus(data.message || 'Demo initiated.')
      setHasRun(true)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/demo/reset`, { method: 'POST' })
      const data = await res.json()
      setStatus(data.message || 'Demo reset.')
      setHasRun(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel full-panel">
      <div className="panel-header">
        <div>
          <div className="panel-title">Interactive Demo Sequence</div>
          <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
            Walk through the ContractMind organizational learning loop in 3 guided steps.
          </div>
        </div>
        <ArrowRight size={22} color="#2563eb" />
      </div>

      <div className="notice" style={{ lineHeight: '1.6', marginBottom: '20px' }}>
        <strong>Demo Walkthrough:</strong>
        <ol style={{ margin: '8px 0 0', paddingLeft: '20px' }}>
          <li><strong>Step 1 (C001):</strong> Review NovaCloud contract with uncapped liability. Propose and approve a 12-month cap. (Hindsight RETAIN saves the decision).</li>
          <li><strong>Step 2 (C005):</strong> Open Apex contract. Hindsight RECALL retrieves the C001 precedent, and Gemini automatically applies the organizational position!</li>
          <li><strong>Step 3 (C015):</strong> Review BluePeak contract. Detect a 24-month strategic enterprise exception.</li>
        </ol>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button className="primary-btn" onClick={handleRun} disabled={loading}>
          {loading ? 'Starting…' : 'Start Guided Demo'}
        </button>
        <button className="tab-btn" onClick={handleReset} disabled={loading}>
          Reset Demo Data
        </button>
      </div>

      <div style={{ marginTop: '16px', fontWeight: 600, color: '#1e40af' }}>{status}</div>

      {hasRun ? (
        <div style={{ marginTop: '24px', padding: '16px', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
          <h4>Start Reviewing:</h4>
          <div style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
            <NavLink className="link-btn" to="/review/C001">Step 1: Open C001</NavLink>
            <NavLink className="link-btn" to="/review/C005">Step 2: Open C005</NavLink>
            <NavLink className="link-btn" to="/review/C015">Step 3: Open C015</NavLink>
            <NavLink className="link-btn" to="/history">View Audit Timeline</NavLink>
          </div>
        </div>
      ) : null}
    </div>
  )
}

// =========================================================================
// MAIN APP COMPONENT
// =========================================================================

function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  )
}

export default App

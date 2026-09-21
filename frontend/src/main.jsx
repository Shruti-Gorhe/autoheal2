import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity, GitBranch, ShieldCheck, BrainCircuit, Wrench, Play,
  CheckCircle2, AlertTriangle, UserCheck, Search, FlaskConical,
  ExternalLink, FileCode2, Terminal, RefreshCw,
  ChevronDown, ChevronUp
} from 'lucide-react';
import './styles.css';

const API = 'http://localhost:8000';
const PHOENIX = 'http://localhost:6006';

const agents = [
  { name: 'Pipeline Agent', icon: GitBranch, key: 'pipeline' },
  { name: 'RAG Retrieval', icon: Search, key: 'rag' },
  { name: 'RCA Agent', icon: BrainCircuit, key: 'rca' },
  { name: 'Fix Agent', icon: Wrench, key: 'fix' },
  { name: 'Validation', icon: FlaskConical, key: 'validation' },
  { name: 'Release Decision', icon: ShieldCheck, key: 'release' },
];

const scenarios = [
  ['test_failure', 'Test failure'],
  ['dependency_failure', 'Dependency failure'],
  ['config_failure', 'Config failure'],
  ['deployment_failure', 'Deployment failure'],
  ['success', 'Successful pipeline'],
];

function safePercent(value) {
  return Math.round(Number(value || 0) * 100);
}

function clipText(value, max = 1600) {
  if (value === null || value === undefined) return '';
  const text = String(value);
  if (text.length <= max) return text;
  const half = Math.floor(max / 2);
  return text.slice(0, half) +
    '\n\n...[middle truncated]...\n\n' +
    text.slice(-half);
}

function statusClass(status) {
  const value = String(status || '').toLowerCase();
  if (value.includes('pass') || value.includes('approv') ||
      value === 'success' || value === 'completed') return 'status-success';
  if (value.includes('fail') || value.includes('reject') ||
      value.includes('error')) return 'status-failure';
  if (value.includes('review') || value.includes('pending') ||
      value.includes('process')) return 'status-warning';
  return 'status-neutral';
}

function prettyStatus(status) {
  if (!status) return 'UNKNOWN';
  return String(status).replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function AgentCard({ agent, state }) {
  const Icon = agent.icon;
  return (
    <div className={`card agent ${state.className || ''}`}>
      <div className="icon"><Icon size={19} /></div>
      <div className="agent-copy">
        <b>{agent.name}</b>
        <small>{state.label}</small>
      </div>
      <span className={`agent-dot ${state.dotClass || ''}`} />
    </div>
  );
}

function Metric({ label, value, icon: Icon }) {
  return (
    <div className="metric">
      {Icon && <div className="metric-icon"><Icon size={16} /></div>}
      <div><small>{label}</small><b>{value}</b></div>
    </div>
  );
}

function App() {
  const [scenario, setScenario] = useState('test_failure');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [evalData, setEvalData] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [showRag, setShowRag] = useState(false);
  const [showValidationOutput, setShowValidationOutput] = useState(false);

  async function run() {
    setLoading(true);
    setMessage('');
    setData(null);
    setShowLogs(false);
    setShowRag(false);
    setShowValidationOutput(false);

    try {
      const response = await fetch(`${API}/api/pipelines/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
      });
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      setData(await response.json());
    } catch (error) {
      console.error(error);
      setMessage('Backend unavailable. Start FastAPI on port 8000 and try again.');
    } finally {
      setLoading(false);
    }
  }

  async function evaluate() {
    setEvalLoading(true);
    setMessage('');
    try {
      const response = await fetch(`${API}/api/evaluation/run`, { method: 'POST' });
      if (!response.ok) throw new Error(`Evaluation returned ${response.status}`);
      setEvalData(await response.json());
      setMessage('RAG evaluation completed.');
    } catch (error) {
      console.error(error);
      setMessage('Evaluation failed. Make sure the backend and evaluation dependencies are running.');
    } finally {
      setEvalLoading(false);
    }
  }

  async function hitl(action) {
    if (!data?.pipeline_id) return;
    try {
      setMessage('');
      const response = await fetch(
        `${API}/api/pipelines/${data.pipeline_id}/decision`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action }),
        }
      );
      if (!response.ok) throw new Error(`HITL returned ${response.status}`);
      setData(await response.json());
      setMessage(action === 'approve'
        ? 'Release approved by human.'
        : 'Release rejected by human.');
    } catch (error) {
      console.error(error);
      setMessage('Unable to submit the human decision.');
    }
  }

  const pipelineStatus = data?.pipeline?.status || 'waiting';
  const validation = data?.validation || data?.validation_result || {};
  const github = data?.github || {};
  const rca = data?.rca || {};
  const fix = data?.fix || {};
  const hitlState = data?.hitl || {};

  const testPassed = validation.tests_passed === true || validation.passed === true;
  const patchApplied = validation.patch_applied === true;
  const testExecutionSuccess =
    validation.test_execution_success === true || validation.success === true;

  const changedFiles = Array.isArray(validation.changed_files) ? validation.changed_files : [];
  const likelyFiles = Array.isArray(rca.likely_files) ? rca.likely_files : [];
  const evidence = Array.isArray(rca.evidence) ? rca.evidence : [];

  const agentStates = useMemo(() => {
    if (!data) {
      return Object.fromEntries(agents.map(agent => [agent.key, {
        label: 'Waiting for run', dotClass: ''
      }]));
    }

    return {
      pipeline: {
        label: github.run_id ? `GitHub run #${github.run_id} processed` : 'Pipeline processed',
        dotClass: 'success'
      },
      rag: {
        label: data.rag_context ? 'Context retrieved' : 'Retrieval completed',
        dotClass: 'success'
      },
      rca: {
        label: rca.confidence ? `${safePercent(rca.confidence)}% confidence` : 'Analysis completed',
        dotClass: 'success'
      },
      fix: {
        label: fix.patch ? `${changedFiles.length || 1} candidate file change` : 'No patch proposed',
        dotClass: fix.patch ? 'success' : ''
      },
      validation: {
        label: validation.attempted
          ? (testPassed ? 'All configured tests passed'
            : testExecutionSuccess ? 'Tests executed with failures'
            : 'Validation did not complete')
          : 'Not run',
        dotClass: validation.attempted ? (testPassed ? 'success' : 'warning') : ''
      },
      release: {
        label: data.decision ? prettyStatus(data.decision) : 'Decision pending',
        dotClass: data.decision === 'APPROVED_FOR_RELEASE' ? 'success' : 'warning'
      }
    };
  }, [data, github.run_id, rca.confidence, fix.patch, changedFiles.length,
      validation.attempted, testPassed, testExecutionSuccess]);

  const steps = [
    { label: 'GitHub Pipeline', done: Boolean(data), failed: pipelineStatus === 'failed' },
    { label: 'RAG Retrieval', done: Boolean(data?.rag_context), failed: false },
    { label: 'RCA', done: Boolean(data?.rca), failed: false },
    { label: 'Fix', done: Boolean(data?.fix?.patch), failed: false },
    { label: 'Validation', done: Boolean(validation.attempted), failed: Boolean(validation.attempted && !testPassed) },
    { label: 'Release', done: Boolean(data?.decision), failed: data?.decision === 'REJECTED' },
    {
      label: 'HITL',
      done: ['approved', 'rejected', 'not_required'].includes(hitlState.status),
      failed: hitlState.status === 'rejected',
      pending: hitlState.status === 'pending'
    }
  ];

  return (
    <div className="app">
      <header>
        <div>
          <span className="eyebrow">AI DEVOPS LAB</span>
          <h1>AutoHeal <span>CI/CD</span></h1>
          <p>GitHub Actions → agents → local Llama 3.2 → RAG → isolated validation → human approval.</p>
        </div>
        <div className="header-actions">
          <a className="phoenix-link" href={PHOENIX} target="_blank" rel="noreferrer">
            <Activity size={15} /> Phoenix <ExternalLink size={13} />
          </a>
          <div className="status"><Activity size={16} /> OTEL READY</div>
        </div>
      </header>

      <main>
        <section className="hero">
          <div>
            <span className="eyebrow">CONTROL CENTER</span>
            <h2>Self-healing pipeline control center</h2>
            <p>Run a local scenario now, or use the GitHub webhook to process real workflow runs and CI logs.</p>
          </div>
          <div className="runbox">
            <select value={scenario} onChange={e => setScenario(e.target.value)} aria-label="Pipeline scenario">
              {scenarios.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
            </select>
            <button onClick={run} disabled={loading}>
              {loading ? <RefreshCw className="spin" size={17} /> : <Play size={17} />}
              {loading ? 'Running…' : 'Run Pipeline'}
            </button>
          </div>
        </section>

        {message && <div className="notice">{message}</div>}

        {data && (
          <>
            <section className="summary-grid">
              <Metric label="PIPELINE" value={prettyStatus(pipelineStatus)} icon={Activity} />
              <Metric label="RUN ID" value={github.run_id || data.pipeline_id} icon={GitBranch} />
              <Metric label="BRANCH" value={github.branch || data.pipeline?.branch || 'local'} icon={GitBranch} />
              <Metric label="RCA CONFIDENCE" value={`${safePercent(rca.confidence)}%`} icon={BrainCircuit} />
              <Metric label="VALIDATION" value={validation.attempted ? (testPassed ? 'PASSED' : 'FAILED') : 'NOT RUN'} icon={FlaskConical} />
              <Metric label="DECISION" value={prettyStatus(data.decision)} icon={ShieldCheck} />
            </section>

            <section className="card pipeline-card">
              <div className="sectiontitle">
                <div><span className="eyebrow">EXECUTION GRAPH</span><h3>Agent pipeline</h3></div>
                <span className={`pill ${statusClass(data.decision || pipelineStatus)}`}>
                  {prettyStatus(data.decision || pipelineStatus)}
                </span>
              </div>

              <div className="agent-grid">
                {agents.map(agent => <AgentCard key={agent.key} agent={agent} state={agentStates[agent.key]} />)}
              </div>

              <div className="steps">
                {steps.map((step, index) => (
                  <React.Fragment key={step.label}>
                    <div className="step">
                      <div className={`stepdot ${step.failed ? 'fail' : ''} ${step.pending ? 'pending' : ''} ${step.done && !step.failed ? 'complete' : ''}`}>
                        {step.failed ? '!' : step.pending ? '…' : step.done ? '✓' : '•'}
                      </div>
                      <span>{step.label}</span>
                    </div>
                    {index < steps.length - 1 && <div className="step-line" />}
                  </React.Fragment>
                ))}
              </div>
            </section>

            {github.run_id && (
              <section className="card github-card">
                <div className="github-heading">
                  <div className="github-title">
                    <div className="github-icon"><GitBranch size={19} /></div>
                    <div><span className="eyebrow">GITHUB ACTIONS</span><h3>Real workflow execution</h3></div>
                  </div>
                  {github.html_url && (
                    <a className="secondary-button" href={github.html_url} target="_blank" rel="noreferrer">
                      Open GitHub Run <ExternalLink size={14} />
                    </a>
                  )}
                </div>
                <div className="github-meta">
                  <span><b>Run</b> #{github.run_id}</span>
                  <span><b>Branch</b> {github.branch || 'main'}</span>
                  <span><b>Conclusion</b> <span className={statusClass(github.conclusion)}>{prettyStatus(github.conclusion)}</span></span>
                  <span><b>Commit</b> <code>{(github.head_sha || data.pipeline?.commit || '').slice(0, 10)}</code></span>
                </div>
              </section>
            )}

            <section className="twocol">
              <div className="card">
                <div className="sectiontitle">
                  <div><span className="eyebrow">ROOT CAUSE ANALYSIS</span><h3>{rca.confidence ? `${safePercent(rca.confidence)}% confidence` : 'Analysis'}</h3></div>
                  <BrainCircuit size={20} className="section-icon" />
                </div>
                <p className="main-copy">{rca.summary || 'No RCA summary was returned.'}</p>

                {evidence.length > 0 && (
                  <div className="detail-block">
                    <span className="detail-label">EVIDENCE</span>
                    <ul className="evidence-list">
                      {evidence.map((item, index) => (
                        <li key={`${item}-${index}`}><CheckCircle2 size={15} /><span>{item}</span></li>
                      ))}
                    </ul>
                  </div>
                )}

                {likelyFiles.length > 0 && (
                  <div className="detail-block">
                    <span className="detail-label">LIKELY FILES</span>
                    <div className="file-list">
                      {likelyFiles.map(file => <span className="file-chip" key={file}><FileCode2 size={14} />{file}</span>)}
                    </div>
                  </div>
                )}
              </div>

              <div className="card">
                <div className="sectiontitle">
                  <div><span className="eyebrow">RAG CONTEXT</span><h3>{data.rag_context ? 'Retrieved knowledge' : 'No context'}</h3></div>
                  <Search size={20} className="section-icon" />
                </div>
                <p className="main-copy">Troubleshooting context is retrieved before RCA and supplied to the remediation workflow.</p>
                {data.rag_context && (
                  <>
                    <button className="text-button" onClick={() => setShowRag(v => !v)}>
                      {showRag ? 'Hide retrieved context' : 'View retrieved context'}
                      {showRag ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                    {showRag && <pre className="code-panel rag-panel">{clipText(data.rag_context, 2200)}</pre>}
                  </>
                )}
              </div>
            </section>

            <section className="card fix-card">
              <div className="sectiontitle">
                <div><span className="eyebrow">FIX AGENT</span><h3>Proposed remediation</h3></div>
                <Wrench size={20} className="section-icon" />
              </div>
              <p className="main-copy">{fix.proposal || 'No remediation proposal was returned.'}</p>
              {fix.patch ? (
                <div className="diff-wrapper">
                  <div className="code-header"><span><FileCode2 size={14} /> Candidate unified diff</span><span className="code-badge">ISOLATED</span></div>
                  <pre className="code-panel diff-panel">{fix.patch}</pre>
                </div>
              ) : <div className="empty-state">No candidate patch was generated for this run.</div>}
              {fix.validation_plan && (
                <div className="validation-plan">
                  <span className="detail-label">VALIDATION PLAN</span>
                  <p>{fix.validation_plan}</p>
                </div>
              )}
            </section>

            <section className="card validation-card">
              <div className="sectiontitle">
                <div><span className="eyebrow">ISOLATED VALIDATION</span><h3>Patch verification & test execution</h3></div>
                <div className={`validation-badge ${testPassed ? 'good' : 'warn'}`}>
                  {testPassed ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
                  {testPassed ? 'PASSED' : 'REVIEW'}
                </div>
              </div>

              <div className="validation-metrics">
                <div><span>Patch applied</span><b className={patchApplied ? 'text-success' : 'text-warning'}>{patchApplied ? 'YES' : 'NO'}</b></div>
                <div><span>Test execution</span><b className={testExecutionSuccess ? 'text-success' : 'text-warning'}>{testExecutionSuccess ? 'COMPLETED' : 'NOT COMPLETED'}</b></div>
                <div><span>Tests</span><b className={testPassed ? 'text-success' : 'text-warning'}>{testPassed ? 'ALL PASSED' : 'FAILURES PRESENT'}</b></div>
                <div><span>Exit code</span><b>{validation.exit_code ?? '—'}</b></div>
              </div>

              {changedFiles.length > 0 && (
                <div className="detail-block">
                  <span className="detail-label">CHANGED FILES</span>
                  <div className="file-list">{changedFiles.map(file => <span className="file-chip" key={file}><FileCode2 size={14} />{file}</span>)}</div>
                </div>
              )}

              {validation.patch_error && (
                <div className="error-box">
                  <AlertTriangle size={16} />
                  <div><b>Patch / validation message</b><p>{validation.patch_error}</p></div>
                </div>
              )}

              {(validation.stdout || validation.stderr) && (
                <>
                  <button className="text-button" onClick={() => setShowValidationOutput(v => !v)}>
                    <Terminal size={14} />
                    {showValidationOutput ? 'Hide test output' : 'View test output'}
                    {showValidationOutput ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                  {showValidationOutput && (
                    <pre className="code-panel terminal-panel">
                      {clipText([validation.stdout, validation.stderr].filter(Boolean).join('\n'), 5000)}
                    </pre>
                  )}
                </>
              )}
            </section>

            <section className="card decision">
              <div>
                <span className="eyebrow">RELEASE DECISION</span>
                <h2>{prettyStatus(data.decision)}</h2>
                <p>
                  {data.decision === 'APPROVED_FOR_RELEASE'
                    ? 'The release gate returned an approval.'
                    : data.decision === 'REJECTED'
                      ? 'The release gate rejected this remediation.'
                      : 'The proposed change requires human review before release.'}
                </p>
              </div>
              <div className="telemetry">
                <span><b>6</b> stages</span><span><b>1</b> trace</span><span><b>OTLP</b> ready</span>
              </div>
            </section>

            {hitlState.status === 'pending' && (
              <section className="card hitl">
                <div>
                  <span className="eyebrow">HUMAN-IN-THE-LOOP</span>
                  <h3>Approval required</h3>
                  <p>Automated analysis and isolated validation are complete. A human must decide whether the proposed remediation may proceed.</p>
                </div>
                <div className="hitlactions">
                  <button onClick={() => hitl('approve')}><CheckCircle2 size={17} />Approve</button>
                  <button className="danger" onClick={() => hitl('reject')}><AlertTriangle size={17} />Reject</button>
                </div>
              </section>
            )}

            {hitlState.status && hitlState.status !== 'pending' && hitlState.status !== 'not_required' && (
              <section className="card approved">
                <UserCheck size={18} />
                <div><span className="eyebrow">HUMAN DECISION</span><b>{prettyStatus(hitlState.status)}</b></div>
              </section>
            )}

            {data.pipeline?.failure_summary && (
              <section className="card logs-card">
                <button className="logs-toggle" onClick={() => setShowLogs(v => !v)}>
                  <div><span className="eyebrow">CI LOGS</span><h3>Workflow failure evidence</h3></div>
                  <span className="toggle-icon">{showLogs ? <ChevronUp size={18} /> : <ChevronDown size={18} />}</span>
                </button>
                {showLogs && <pre className="code-panel terminal-panel">{clipText(data.pipeline.failure_summary, 5000)}</pre>}
              </section>
            )}
          </>
        )}

        <section className="evaluation card">
          <div className="evaluation-header">
            <div>
              <span className="eyebrow">RAG EVALUATION</span>
              <h2>Measure whether retrieval helps</h2>
              <p>Runs the evaluation dataset with and without retrieved knowledge and reports retrieval and RCA metrics.</p>
            </div>
            <button onClick={evaluate} disabled={evalLoading}>
              {evalLoading ? <RefreshCw className="spin" size={16} /> : <FlaskConical size={16} />}
              {evalLoading ? 'Evaluating…' : 'Run Evaluation'}
            </button>
          </div>

          {evalData && (
            <div className="evalgrid">
              <div><b>{evalData.dataset_size}</b><small>dataset cases</small></div>
              <div><b>{safePercent(evalData.retrieval?.recall_at_k)}%</b><small>Recall@4</small></div>
              <div><b>{Number(evalData.retrieval?.mrr || 0).toFixed(2)}</b><small>MRR</small></div>
              <div><b>{safePercent(evalData.without_rag?.rca_keyword_accuracy)}%</b><small>RCA without RAG</small></div>
              <div><b>{safePercent(evalData.with_rag?.rca_keyword_accuracy)}%</b><small>RCA with RAG</small></div>
              <div><b>{(Number(evalData.improvement?.rca_keyword_accuracy_delta || 0) * 100).toFixed(1)} pp</b><small>RAG improvement</small></div>
            </div>
          )}
        </section>
      </main>

      <footer>Local-first • Google ADK • Llama 3.2 • RAG • GitHub Actions • OpenTelemetry • Phoenix • FastAPI • React</footer>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);

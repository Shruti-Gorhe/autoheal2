import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Activity,GitBranch,ShieldCheck,BrainCircuit,Wrench,Play,CheckCircle2,AlertTriangle,UserCheck} from 'lucide-react';
import './styles.css';

const API='http://localhost:8000';
const agents=[['Pipeline Agent',GitBranch],['RCA Agent',BrainCircuit],['Fix Agent',Wrench],['Release Agent',ShieldCheck]];

function App(){
 const [scenario,setScenario]=useState('test_failure');
 const [data,setData]=useState(null);
 const [loading,setLoading]=useState(false);
 const [message,setMessage]=useState('');
 const [evalData,setEvalData]=useState(null);
 const [evalLoading,setEvalLoading]=useState(false);
 async function run(){
   setLoading(true); setMessage('');
   try{const r=await fetch(`${API}/api/pipelines/run`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario})});setData(await r.json())}
   catch(e){setMessage('Backend unavailable. Start FastAPI on port 8000.')}
   finally{setLoading(false)}
 }
 async function evaluate(){
   setEvalLoading(true); setMessage('');
   try{const r=await fetch(`${API}/api/evaluation/run`,{method:'POST'});const x=await r.json();setEvalData(x);setMessage('Evaluation completed.');}
   catch(e){setMessage('Evaluation failed. Make sure backend dependencies are installed.');}
   finally{setEvalLoading(false)}
 }
 async function hitl(action){
   if(!data?.pipeline_id)return;
   const r=await fetch(`${API}/api/pipelines/${data.pipeline_id}/decision`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
   const next=await r.json(); setData(next); setMessage(action==='approve'?'Release approved by human.':'Release rejected by human.');
 }
 return <div className="app">
  <header><div><span className="eyebrow">AI DEVOPS LAB</span><h1>AutoHeal <span>CI/CD</span></h1><p>GitHub → agents → Llama 3.2 → isolated validation → human approval.</p></div><div className="status"><Activity size={16}/> OTEL READY</div></header>
  <main>
   <section className="hero"><div><h2>Self-healing pipeline control center</h2><p>Run a local simulation now, or connect GitHub Actions to the webhook for real logs and workflow runs.</p></div><div className="runbox"><select value={scenario} onChange={e=>setScenario(e.target.value)}><option value="test_failure">Test failure</option><option value="dependency_failure">Dependency failure</option><option value="config_failure">Config failure</option><option value="deployment_failure">Deployment failure</option><option value="success">Successful pipeline</option></select><button onClick={run} disabled={loading}><Play size={17}/>{loading?'Running…':'Run Pipeline'}</button></div></section>
   <section className="grid">{agents.map(([name,Icon])=><div className="card agent" key={name}><div className="icon"><Icon size={19}/></div><div><b>{name}</b><small>{data? 'Executed in trace':'Waiting for run'}</small></div><span className={data?'dot live':'dot'}></span></div>)}</section>
   {message&&<div className="notice">{message}</div>}
   {data&&<section className="results">
    <div className="card wide"><div className="sectiontitle"><div><span className="eyebrow">PIPELINE</span><h3>{data.pipeline_id}</h3></div><span className={data.pipeline.status==='passed'?'pill ok':'pill bad'}>{data.pipeline.status}</span></div><div className="steps">{['Build','Test','RCA','Fix','Decision'].map((s,i)=><div className="step" key={s}><div className={(i===1&&data.pipeline.status==='failed')?'stepdot fail':'stepdot'}>{i===1&&data.pipeline.status==='failed'?'!':'✓'}</div><span>{s}</span></div>)}</div></div>
    <div className="twocol"><div className="card"><span className="eyebrow">ROOT CAUSE</span><h3>{Math.round((data.rca?.confidence||0)*100)}% confidence</h3><p>{data.rca?.summary}</p></div><div className="card"><span className="eyebrow">REMEDIATION</span><h3>Proposed action</h3><p>{data.fix?.proposal}</p>{data.fix?.validation&&<small className="validation">Isolated tests: {data.fix.validation.tests_passed?'PASSED':'NOT PASSED / NOT RUN'}</small>}</div></div>
    <div className="card decision"><div><span className="eyebrow">RELEASE DECISION</span><h2>{data.decision}</h2></div><div className="telemetry"><span><b>4</b> agents</span><span><b>1</b> trace</span><span><b>OTLP</b> ready</span></div></div>
    {data.hitl?.status==='pending'&&<div className="card hitl"><div><span className="eyebrow">HUMAN-IN-THE-LOOP</span><h3>Approval required</h3><p>The agents have finished analysis. A human must approve the release decision.</p></div><div className="hitlactions"><button onClick={()=>hitl('approve')}><CheckCircle2 size={17}/> Approve</button><button className="danger" onClick={()=>hitl('reject')}><AlertTriangle size={17}/> Reject</button></div></div>}
    {data.hitl?.status&&data.hitl.status!=='pending'&&data.hitl.status!=='not_required'&&<div className="card approved"><UserCheck size={18}/><b>Human decision: {data.hitl.status}</b></div>}
   </section>}
  <section className="evaluation card"><div><span className="eyebrow">RAG EVALUATION</span><h2>Measure whether retrieval helps</h2><p>Runs the dataset twice: RCA without retrieved knowledge and RCA with top-k RAG context.</p></div><button onClick={evaluate} disabled={evalLoading}>{evalLoading?'Evaluating…':'Run Evaluation'}</button>{evalData&&<div className="evalgrid"><div><b>{evalData.dataset_size}</b><small>dataset cases</small></div><div><b>{Math.round(evalData.retrieval.recall_at_k*100)}%</b><small>Recall@4</small></div><div><b>{evalData.retrieval.mrr.toFixed(2)}</b><small>MRR</small></div><div><b>{Math.round(evalData.without_rag.rca_keyword_accuracy*100)}%</b><small>RCA without RAG</small></div><div><b>{Math.round(evalData.with_rag.rca_keyword_accuracy*100)}%</b><small>RCA with RAG</small></div><div><b>{(evalData.improvement.rca_keyword_accuracy_delta*100).toFixed(1)} pp</b><small>RAG improvement</small></div></div>}</section>
  </main><footer>Local-first • Google ADK • Llama 3.2 • RAG • GitHub Actions • OpenTelemetry • FastAPI • React</footer>
 </div>
}
createRoot(document.getElementById('root')).render(<App/>);

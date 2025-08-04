import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";

const DEFAULT_BASE_URL = "http://localhost:8080";

const initialEndpoints = [
  { method: "GET", path: "/api/v1/health/ready", enabled: true },
  { method: "GET", path: "/api/v1/health/detailed", enabled: true },
  { method: "GET", path: "/api/v1/health/metrics", enabled: true },
  { method: "GET", path: "/api/v1/health/database-status", enabled: true },
  { method: "GET", path: "/api/v1/health/performance", enabled: true },
  { method: "GET", path: "/api/v1/health/config-validation", enabled: true },
  { method: "GET", path: "/api/v1/health/startup-validation", enabled: true },
  { method: "GET", path: "/api/v1/enhanced/system", enabled: true },
  { method: "GET", path: "/api/v1/enhanced/processor", enabled: true },
  { method: "GET", path: "/api/v1/enhanced/embedding", enabled: true },
  { method: "GET", path: "/api/v1/index/repositories", enabled: true },
  { method: "POST", path: "/api/v1/embeddings/validate", enabled: false, body: {} },
];

function App() {
  const [baseURL, setBaseURL] = useState(DEFAULT_BASE_URL);
  const [endpoints, setEndpoints] = useState(initialEndpoints);
  const [selected, setSelected] = useState(new Set(endpoints.filter(e => e.enabled).map(e => e.path)));
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState(null);
  const [elapsed, setElapsed] = useState(null);
  const [headers, setHeaders] = useState('{\n  "Content-Type": "application/json"\n}');
  const client = useMemo(() => axios.create({ baseURL, timeout: 15000 }), [baseURL]);

  const toggle = (path) => {
    const next = new Set(selected);
    if (next.has(path)) next.delete(path); else next.add(path);
    setSelected(next);
  };

  const runOne = async (ep) => {
    const start = performance.now();
    try {
      const hdrs = JSON.parse(headers || "{}");
      const cfg = { headers: hdrs, validateStatus: () => true };
      let resp;
      if (ep.method === "GET") resp = await client.get(ep.path, cfg);
      else if (ep.method === "POST") resp = await client.post(ep.path, ep.body ?? {}, cfg);
      const ms = Math.round(performance.now() - start);
      setElapsed(ms);
      setStatus({ status: resp.status, ok: resp.status >= 200 && resp.status < 300 });
      setResult({ endpoint: ep, data: resp.data, status: resp.status, ms });
    } catch (e) {
      const ms = Math.round(performance.now() - start);
      setElapsed(ms);
      setStatus({ status: e.response?.status ?? "ERR", ok: false });
      setResult({ endpoint: ep, error: e.message, response: e.response?.data, ms });
    }
  };

  const runSelected = async () => {
    setRunning(true);
    setResult(null);
    const list = endpoints.filter(e => selected.has(e.path));
    const outputs = [];
    const startAll = performance.now();
    for (const ep of list) {
      const t0 = performance.now();
      try {
        const hdrs = JSON.parse(headers || "{}");
        const cfg = { headers: hdrs, validateStatus: () => true };
        let resp;
        if (ep.method === "GET") resp = await client.get(ep.path, cfg);
        else if (ep.method === "POST") resp = await client.post(ep.path, ep.body ?? {}, cfg);
        outputs.push({ path: ep.path, method: ep.method, status: resp.status, ms: Math.round(performance.now()-t0), data: resp.data });
      } catch (e) {
        outputs.push({ path: ep.path, method: ep.method, status: e.response?.status ?? "ERR", ms: Math.round(performance.now()-t0), error: e.message, data: e.response?.data });
      }
    }
    const totalMs = Math.round(performance.now() - startAll);
    setRunning(false);
    setElapsed(totalMs);
    setStatus({ status: "BATCH", ok: outputs.every(o => typeof o.status === "number" && o.status >= 200 && o.status < 300) });
    setResult({ batch: outputs, totalMs });
  };

  const setAll = (on) => {
    setSelected(new Set(on ? endpoints.map(e => e.path) : []));
  };

  return (
    <div className="container">
      <div className="left">
        <div className="card">
          <header>Configuration</header>
          <div className="body">
            <div className="row">
              <div>
                <label>Base URL</label>
                <input value={baseURL} onChange={e=>setBaseURL(e.target.value)} placeholder="http://localhost:8080" />
              </div>
              <div>
                <label>Headers (JSON)</label>
                <textarea rows={4} value={headers} onChange={e=>setHeaders(e.target.value)} />
              </div>
            </div>
            <div className="controls">
              <button className="btn" onClick={()=>setAll(true)}>Select All</button>
              <button className="btn" onClick={()=>setAll(false)}>Clear</button>
              <button className="btn primary" disabled={running} onClick={runSelected}>Run Selected</button>
            </div>
          </div>
        </div>

        <div className="card" style={{marginTop:12}}>
          <header>Endpoints</header>
          <div className="body endpoints">
            {endpoints.map(ep => (
              <div className="endpoint-row" key={ep.path}>
                <input type="checkbox" checked={selected.has(ep.path)} onChange={()=>toggle(ep.path)} />
                <div className={["method", ep.method].join(' ')}>{ep.method}</div>
                <div style={{flex:1, fontFamily:'ui-monospace'}}>{ep.path}</div>
                <button className="btn" disabled={running} onClick={()=>runOne(ep)}>Run</button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="right">
        <div className="card">
          <header>Result</header>
          <div className="body">
            <div className="controls">
              <div>Elapsed: <span className="status">{elapsed ?? '-'} ms</span></div>
              {status && (<div>Status: <span className={["status", status.ok? 'pass':'fail'].join(' ')}>{String(status.status)}</span></div>)}
            </div>
            <pre>{result ? JSON.stringify(result, null, 2) : "// run an endpoint to see raw output here"}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
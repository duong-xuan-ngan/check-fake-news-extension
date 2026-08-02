"use client";

import { useMemo, useState } from "react";

type Tab =
  | "Overview"
  | "Analyses"
  | "Users"
  | "Feedback"
  | "Sources"
  | "AI & Pipeline"
  | "System Health"
  | "Database"
  | "Settings";

const tabs: { label: Tab; icon: string }[] = [
  { label: "Overview", icon: "⌂" },
  { label: "Analyses", icon: "◎" },
  { label: "Users", icon: "♙" },
  { label: "Feedback", icon: "◇" },
  { label: "Sources", icon: "◉" },
  { label: "AI & Pipeline", icon: "✦" },
  { label: "System Health", icon: "⌁" },
  { label: "Database", icon: "▰" },
  { label: "Settings", icon: "⚙" },
];

const analyses = [
  { id: "AN-8F21", time: "12:42", claim: "WHO confirms a new global health emergency...", verdict: "UNVERIFIED", confidence: "LOW", latency: "2.8s", source: "facebook.com", status: "Review" },
  { id: "AN-8E94", time: "12:31", claim: "Vietnam’s GDP grew 7.09% during 2024", verdict: "TRUE", confidence: "HIGH", latency: "1.2s", source: "vnexpress.net", status: "Complete" },
  { id: "AN-8DB0", time: "12:18", claim: "Scientists confirm 5G causes COVID-19", verdict: "FALSE", confidence: "HIGH", latency: "0.3s", source: "threads.net", status: "Cached" },
  { id: "AN-8C72", time: "11:56", claim: "The central bank will replace all cash next month", verdict: "NOT_SURE", confidence: "LOW", latency: "5.1s", source: "facebook.com", status: "Review" },
  { id: "AN-8B19", time: "11:32", claim: "Solar power is now the cheapest source of energy", verdict: "TRUE", confidence: "MEDIUM", latency: "1.8s", source: "reddit.com", status: "Complete" },
  { id: "AN-89D4", time: "10:49", claim: "A viral image shows flooding in central Hanoi today", verdict: "FALSE", confidence: "MEDIUM", latency: "2.1s", source: "x.com", status: "Complete" },
];

const sourceRows = [
  { domain: "vnexpress.net", score: 0.85, category: "National News", checks: "1,842", updated: "Jul 26, 2026" },
  { domain: "tuoitre.vn", score: 0.85, category: "National News", checks: "1,291", updated: "Jul 26, 2026" },
  { domain: "vtv.vn", score: 0.8, category: "State Broadcast", checks: "975", updated: "Jul 25, 2026" },
  { domain: "reuters.com", score: 0.92, category: "Manual / trusted", checks: "823", updated: "Jul 25, 2026" },
  { domain: "kenh14.vn", score: 0.6, category: "Entertainment", checks: "764", updated: "Jul 24, 2026" },
  { domain: "tinhhoa.net", score: 0.2, category: "Manual / high risk", checks: "311", updated: "Jul 24, 2026" },
];

const productSignals = [
  {
    label: "Highlights",
    kind: "Usage",
    value: "18,642",
    change: "+14.2%",
    note: "selected-text events",
    icon: "✎",
    tone: "blue",
    points: [34, 42, 38, 49, 46, 57, 54, 68, 63, 74, 71, 82],
  },
  {
    label: "Average rating",
    kind: "Feedback",
    value: "4.3 / 5",
    change: "+0.2",
    note: "286 star ratings",
    icon: "★",
    tone: "amber",
    points: [61, 63, 62, 66, 65, 68, 70, 69, 72, 74, 75, 78],
  },
  {
    label: "Extension uninstalls",
    kind: "Lagging indicator",
    value: "96",
    change: "−8.6%",
    note: "1.8% uninstall rate",
    icon: "↘",
    tone: "red",
    points: [78, 76, 71, 74, 68, 65, 66, 61, 58, 55, 52, 49],
  },
  {
    label: "7-day return rate",
    kind: "Behavioral",
    value: "41.7%",
    change: "+3.4 pp",
    note: "returning installations",
    icon: "↻",
    tone: "violet",
    points: [42, 44, 48, 47, 51, 54, 55, 59, 61, 64, 66, 70],
  },
];

const databaseRows = [
  { domain: "vnexpress.net", score: "0.85", category: "National News", updated: "2026-07-26" },
  { domain: "tuoitre.vn", score: "0.85", category: "National News", updated: "2026-07-26" },
  { domain: "thanhnien.vn", score: "0.82", category: "National News", updated: "2026-07-26" },
  { domain: "dantri.com.vn", score: "0.78", category: "National News", updated: "2026-07-26" },
  { domain: "vietnamnet.vn", score: "0.78", category: "National News", updated: "2026-07-26" },
  { domain: "tinhhoa.net", score: "0.20", category: "Low Credibility", updated: "2026-07-26" },
];

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}

function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="section-heading">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function MetricCard({ label, value, trend, caption, icon, accent }: { label: string; value: string; trend: string; caption: string; icon: string; accent: string }) {
  return (
    <Panel className="metric-card">
      <div className={`metric-icon metric-${accent}`}>{icon}</div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">
        <span className={trend.startsWith("+") ? "positive" : trend === "Stable" ? "muted" : "negative"}>{trend}</span>
        <span>{caption}</span>
      </div>
    </Panel>
  );
}

function SignalSparkline({ points }: { points: number[] }) {
  const coordinates = points.map((point, index) => `${(index / (points.length - 1)) * 100},${100 - point}`).join(" ");
  return (
    <svg className="signal-sparkline" viewBox="0 0 100 52" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={coordinates} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function ProductSignals() {
  return (
    <Panel className="product-signals-panel">
      <SectionHeader
        title="Extension product signals"
        subtitle="Usage, feedback, retention, and churn indicators for the selected reporting period"
        action={<Badge tone="info">PREVIEW DATA</Badge>}
      />
      <div className="product-signal-grid">
        {productSignals.map((signal) => (
          <article className={`product-signal signal-${signal.tone}`} key={signal.label}>
            <div className="signal-topline">
              <span className="signal-icon">{signal.icon}</span>
              <Badge>{signal.kind}</Badge>
            </div>
            <span className="signal-label">{signal.label}</span>
            <div className="signal-value-row"><strong>{signal.value}</strong><span>{signal.change}</span></div>
            <span className="signal-note">{signal.note}</span>
            <SignalSparkline points={signal.points} />
          </article>
        ))}
      </div>
      <div className="signal-definitions">
        <span><b>Highlights</b> count completed text selections.</span>
        <span><b>Rating</b> is the mean submitted 1–5 star score.</span>
        <span><b>Uninstall rate</b> is uninstall callbacks ÷ installs at period start.</span>
        <span><b>Return rate</b> is prior active installs seen again within 7 days.</span>
      </div>
    </Panel>
  );
}

function MiniLineChart() {
  const points = [22, 28, 25, 36, 31, 43, 38, 52, 48, 59, 55, 68, 64, 78];
  return (
    <div className="chart">
      <div className="chart-ylabels"><span>1.5k</span><span>1.0k</span><span>500</span><span>0</span></div>
      <div className="chart-area">
        <div className="grid-lines"><i /><i /><i /><i /></div>
        <div className="chart-bars" aria-label="Analysis volume over 14 days">
          {points.map((point, index) => (
            <div key={index} className="chart-column">
              <div className="chart-bar" style={{ height: `${point}%` }} />
              {(index === 0 || index === 4 || index === 8 || index === 12) && <span>Jul {13 + index}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Donut() {
  return (
    <div className="donut-wrap">
      <div className="donut"><div><strong>12.4k</strong><span>Total</span></div></div>
      <div className="legend">
        <div><i className="dot true" /><span>True</span><strong>42%</strong></div>
        <div><i className="dot false" /><span>False</span><strong>31%</strong></div>
        <div><i className="dot unsure" /><span>Not sure</span><strong>18%</strong></div>
        <div><i className="dot unverified" /><span>Unverified</span><strong>9%</strong></div>
      </div>
    </div>
  );
}

function Overview({ onNavigate }: { onNavigate: (tab: Tab) => void }) {
  return (
    <>
      <div className="demo-note"><span>●</span> Preview data — connect the admin API to replace these metrics with live production data.</div>
      <div className="metrics-grid">
        <MetricCard label="Analyses today" value="1,284" trend="+12.5%" caption="vs. yesterday" icon="◎" accent="blue" />
        <MetricCard label="Active users" value="836" trend="+8.2%" caption="last 24 hours" icon="♙" accent="violet" />
        <MetricCard label="Success rate" value="96.8%" trend="+1.1%" caption="completed checks" icon="✓" accent="green" />
        <MetricCard label="P95 latency" value="3.2s" trend="-0.4s" caption="faster this week" icon="↯" accent="amber" />
      </div>
      <ProductSignals />
      <div className="overview-grid">
        <Panel className="volume-panel">
          <SectionHeader title="Analysis volume" subtitle="Daily fact-check requests over the last 14 days" action={<button className="text-button" onClick={() => onNavigate("Analyses")}>View all →</button>} />
          <MiniLineChart />
        </Panel>
        <Panel>
          <SectionHeader title="Verdict mix" subtitle="Distribution for the last 30 days" />
          <Donut />
        </Panel>
      </div>
      <div className="overview-grid lower">
        <Panel>
          <SectionHeader title="Pipeline performance" subtitle="Median stage latency and health" action={<button className="text-button" onClick={() => onNavigate("AI & Pipeline")}>Details →</button>} />
          <div className="pipeline-list">
            {[
              ["Preprocess", "84 ms", 12, "healthy"],
              ["Web search", "680 ms", 57, "healthy"],
              ["Source filter", "142 ms", 25, "healthy"],
              ["Content fetch", "1.1 s", 79, "warning"],
              ["LLM synthesis", "940 ms", 69, "healthy"],
            ].map(([name, time, width, state]) => (
              <div className="pipeline-row" key={name}>
                <span>{name}</span><div className="progress"><i className={String(state)} style={{ width: `${width}%` }} /></div><strong>{time}</strong>
              </div>
            ))}
          </div>
        </Panel>
        <Panel>
          <SectionHeader title="Infrastructure" subtitle="Live service availability" action={<button className="text-button" onClick={() => onNavigate("System Health")}>Open health →</button>} />
          <div className="service-grid">
            {[
              ["API", "Operational", "99.99%"],
              ["PostgreSQL", "Operational", "99.98%"],
              ["Redis", "Operational", "100%"],
              ["Qdrant", "Operational", "99.96%"],
              ["Serper", "Degraded", "98.40%"],
              ["OpenRouter", "Operational", "99.72%"],
            ].map(([service, state, uptime]) => (
              <div className="service-card" key={service}>
                <i className={state === "Degraded" ? "status warning" : "status"} />
                <div><strong>{service}</strong><span>{state}</span></div><b>{uptime}</b>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}

function AnalysisTable({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState("");
  const [verdict, setVerdict] = useState("All verdicts");
  const filtered = useMemo(() => analyses.filter((row) =>
    (row.claim.toLowerCase().includes(query.toLowerCase()) || row.id.toLowerCase().includes(query.toLowerCase())) &&
    (verdict === "All verdicts" || row.verdict === verdict.toUpperCase().replace(" ", "_"))
  ), [query, verdict]);

  return (
    <Panel>
      {!compact && (
        <div className="table-tools">
          <label className="search"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search claim or analysis ID" /></label>
          <select value={verdict} onChange={(e) => setVerdict(e.target.value)} aria-label="Filter by verdict">
            <option>All verdicts</option><option>True</option><option>False</option><option>Unverified</option><option>Not sure</option>
          </select>
          <button className="secondary-button">More filters</button>
        </div>
      )}
      <div className="table-scroll">
        <table>
          <thead><tr><th>Analysis</th><th>Claim preview</th><th>Verdict</th><th>Confidence</th><th>Latency</th><th>Origin</th><th>Status</th><th /></tr></thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id}>
                <td><strong>{row.id}</strong><span className="cell-sub">{row.time} today</span></td>
                <td className="claim-cell">{row.claim}</td>
                <td><Badge tone={row.verdict === "TRUE" ? "success" : row.verdict === "FALSE" ? "danger" : row.verdict === "UNVERIFIED" ? "warning" : "neutral"}>{row.verdict.replace("_", " ")}</Badge></td>
                <td><span className={`confidence confidence-${row.confidence.toLowerCase()}`}>{row.confidence}</span></td>
                <td>{row.latency}</td><td>{row.source}</td>
                <td><span className="row-status"><i className={row.status === "Review" ? "review" : ""} />{row.status}</span></td>
                <td><button className="icon-button" aria-label={`Open ${row.id}`}>›</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <div className="empty-search">No analyses match these filters.</div>}
      </div>
      <div className="table-footer"><span>Showing {filtered.length} of 12,481 analyses</span><div><button disabled>‹</button><button className="active">1</button><button>2</button><button>3</button><button>›</button></div></div>
    </Panel>
  );
}

function AnalysesPage() {
  return (
    <>
      <div className="summary-strip">
        <div><span>Total analyses</span><strong>12,481</strong></div>
        <div><span>Cache hit rate</span><strong>38.4%</strong></div>
        <div><span>Needs review</span><strong className="amber-text">74</strong></div>
        <div><span>Errors</span><strong className="red-text">31</strong></div>
      </div>
      <AnalysisTable />
    </>
  );
}

function SourcesPage() {
  const [query, setQuery] = useState("");
  const rows = sourceRows.filter((row) => row.domain.includes(query.toLowerCase()));
  return (
    <>
      <div className="dataset-banner">
        <div><span>◈</span><div><strong>CRED-1 risk signals active</strong><small>v2026-07-28 · 2,635 normalized domains · CC BY 4.0</small></div></div>
        <p>Missing domains remain unrated and enter the review queue; absence never implies trust.</p>
      </div>
      <Panel>
      <div className="table-tools">
        <label className="search"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search 2,660 domains" /></label>
        <button className="primary-button">＋ Add source</button>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Domain</th><th>Credibility</th><th>Category</th><th>Used in checks</th><th>Last updated</th><th /></tr></thead>
          <tbody>{rows.map((row) => (
            <tr key={row.domain}>
              <td><div className="domain-cell"><span>{row.domain.slice(0, 1).toUpperCase()}</span><strong>{row.domain}</strong></div></td>
              <td><div className="score"><div><i style={{ width: `${row.score * 100}%` }} /></div><strong>{row.score.toFixed(2)}</strong></div></td>
              <td><Badge>{row.category}</Badge></td><td>{row.checks}</td><td>{row.updated}</td>
              <td><button className="icon-button" aria-label={`Edit ${row.domain}`}>•••</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      </Panel>
    </>
  );
}

function PipelinePage() {
  return (
    <>
      <div className="metrics-grid">
        <MetricCard label="Pipeline success" value="96.8%" trend="+1.1%" caption="last 7 days" icon="✓" accent="green" />
        <MetricCard label="Median latency" value="2.4s" trend="-8.4%" caption="week over week" icon="↯" accent="blue" />
        <MetricCard label="Cache hit rate" value="38.4%" trend="+5.2%" caption="semantic matches" icon="↻" accent="violet" />
        <MetricCard label="Est. cost / check" value="$0.014" trend="-2.1%" caption="API spend" icon="$" accent="amber" />
      </div>
      <Panel>
        <SectionHeader title="Stage diagnostics" subtitle="Performance across 12,481 analyses in the selected period" />
        <div className="stage-grid">
          {[
            ["01", "Preprocess", "99.9%", "84 ms", "Language normalization"],
            ["02", "Web search", "98.2%", "680 ms", "Serper retrieval"],
            ["03", "Credibility", "99.7%", "142 ms", "Source scoring"],
            ["04", "Content fetch", "94.1%", "1.1 s", "Article extraction"],
            ["05", "Synthesis", "97.6%", "940 ms", "LLM evaluation"],
          ].map(([number, name, success, latency, detail]) => (
            <div className="stage-card" key={name}>
              <span>{number}</span><div><strong>{name}</strong><small>{detail}</small></div>
              <dl><dt>Success</dt><dd>{success}</dd><dt>Median</dt><dd>{latency}</dd></dl>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

function HealthPage() {
  return (
    <>
      <div className="health-banner"><div><i className="status" /><strong>All core systems operational</strong><span>One external provider is experiencing elevated latency.</span></div><span>Last checked 18 seconds ago</span></div>
      <div className="health-list">
        {[
          ["Backend API", "Operational", "99.99%", "118 ms", "Singapore"],
          ["PostgreSQL", "Operational", "99.98%", "21 ms", "Primary"],
          ["Redis cache", "Operational", "100%", "4 ms", "Primary"],
          ["Qdrant vector store", "Operational", "99.96%", "32 ms", "Primary"],
          ["Serper search", "Degraded", "98.40%", "1,248 ms", "External"],
          ["OpenRouter", "Operational", "99.72%", "884 ms", "External"],
        ].map(([name, state, uptime, latency, region]) => (
          <Panel className="health-row" key={name}>
            <div className="health-name"><i className={state === "Degraded" ? "status warning" : "status"} /><div><strong>{name}</strong><span>{region}</span></div></div>
            <div><span>Status</span><strong className={state === "Degraded" ? "amber-text" : "green-text"}>{state}</strong></div>
            <div><span>30-day uptime</span><strong>{uptime}</strong></div>
            <div><span>Response time</span><strong>{latency}</strong></div>
            <button className="icon-button" aria-label={`Open ${name} details`}>›</button>
          </Panel>
        ))}
      </div>
    </>
  );
}

function DatabasePage() {
  const [store, setStore] = useState("PostgreSQL");
  const [table, setTable] = useState("sources");
  const stores = ["PostgreSQL", "Redis", "Qdrant"];
  return (
    <div className="database-layout">
      <Panel className="db-sidebar">
        <div className="db-title"><span>▰</span><div><strong>Data stores</strong><small>Read-only access</small></div></div>
        {stores.map((item) => <button key={item} className={store === item ? "active" : ""} onClick={() => setStore(item)}><i className={item === "PostgreSQL" ? "status" : item === "Redis" ? "status redis" : "status qdrant"} />{item}<span>{item === "PostgreSQL" ? "2 tables" : item === "Redis" ? "246 keys" : "1 collection"}</span></button>)}
        <div className="db-safety"><strong>Read-only mode</strong><span>Changes are disabled to protect production data.</span></div>
      </Panel>
      <Panel className="db-main">
        {store === "PostgreSQL" ? (
          <>
            <div className="db-toolbar">
              <div><span className="crumb">PostgreSQL</span><b>/</b><select value={table} onChange={(e) => setTable(e.target.value)} aria-label="Select database table"><option>sources</option><option>pipeline_logs</option></select></div>
              <div><Badge tone="success">● Connected</Badge><button className="secondary-button">↻ Refresh</button><button className="secondary-button">⇩ Export CSV</button></div>
            </div>
            <div className="schema-strip"><span><b>Table</b> public.{table}</span><span><b>Rows</b> {table === "sources" ? "2,660" : "12,481"}</span><span><b>Primary key</b> {table === "sources" ? "domain" : "id"}</span><span><b>Size</b> {table === "sources" ? "0.8 MB" : "8.6 MB"}</span></div>
            <div className="table-tools compact"><label className="search"><span>⌕</span><input placeholder="Filter rows..." /></label><button className="secondary-button">Columns</button><button className="secondary-button">Filters</button></div>
            {table === "sources" ? (
              <div className="table-scroll"><table className="db-table">
                <thead><tr><th>#</th><th>domain <small>varchar · PK</small></th><th>credibility_score <small>float</small></th><th>category <small>varchar</small></th><th>last_updated <small>date</small></th></tr></thead>
                <tbody>{databaseRows.map((row, index) => <tr key={row.domain}><td>{index + 1}</td><td><code>{row.domain}</code></td><td>{row.score}</td><td>{row.category}</td><td>{row.updated}</td></tr>)}</tbody>
              </table></div>
            ) : (
              <div className="table-scroll"><table className="db-table">
                <thead><tr><th>#</th><th>id <small>varchar · PK</small></th><th>input_hash <small>varchar · masked</small></th><th>verdict <small>varchar</small></th><th>response_time_ms <small>integer</small></th></tr></thead>
                <tbody>{analyses.map((row, index) => <tr key={row.id}><td>{index + 1}</td><td><code>{row.id.toLowerCase()}</code></td><td><code>••••••••{(index + 18).toString(16)}af</code></td><td>{row.verdict}</td><td>{parseFloat(row.latency) * 1000}</td></tr>)}</tbody>
              </table></div>
            )}
            <div className="table-footer"><span>Showing 1–6 of {table === "sources" ? "2,660" : "12,481"} rows</span><div><button disabled>‹</button><button className="active">1</button><button>2</button><button>›</button></div></div>
          </>
        ) : (
          <div className="store-overview">
            <div className={`store-mark ${store.toLowerCase()}`}>{store === "Redis" ? "R" : "Q"}</div>
            <h2>{store}</h2>
            <p>{store === "Redis" ? "Inspect cache keys, TTL, and memory usage without exposing raw payloads." : "Inspect semantic claim vectors, collection health, and masked payload metadata."}</p>
            <div className="store-stats">
              <div><span>{store === "Redis" ? "Keys" : "Points"}</span><strong>{store === "Redis" ? "246" : "8,942"}</strong></div>
              <div><span>{store === "Redis" ? "Hit rate" : "Vector size"}</span><strong>{store === "Redis" ? "38.4%" : "384"}</strong></div>
              <div><span>Storage</span><strong>{store === "Redis" ? "18.2 MB" : "42.8 MB"}</strong></div>
            </div>
            <div className="masked-message"><span>◈</span><div><strong>Payloads are protected</strong><p>Raw cached claims and embeddings are masked in this preview. Metadata browsing will connect through the admin API.</p></div></div>
          </div>
        )}
      </Panel>
    </div>
  );
}

function PlaceholderPage({ type }: { type: "Users" | "Feedback" | "Settings" }) {
  const content = {
    Users: ["User management is ready for identity data", "Track accounts, anonymous extension installations, usage quotas, and account status once authentication is connected.", "Connect identity provider"],
    Feedback: ["Build trust with a review workflow", "Helpful ratings, correction reports, disputed verdicts, and reviewer assignments will appear here when feedback collection is enabled.", "Enable feedback collection"],
    Settings: ["Administrative controls", "Manage access roles, retention policies, alert thresholds, source scoring rules, and a complete audit trail.", "Configure admin access"],
  }[type];
  return (
    <Panel className="placeholder-page">
      <div className="placeholder-icon">{type === "Users" ? "♙" : type === "Feedback" ? "◇" : "⚙"}</div>
      <Badge tone="info">DATA CONNECTION REQUIRED</Badge>
      <h2>{content[0]}</h2><p>{content[1]}</p><button className="primary-button">{content[2]}</button>
      <div className="placeholder-preview">
        {[1, 2, 3].map((item) => <div key={item}><i /><span /><b /></div>)}
      </div>
    </Panel>
  );
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [period, setPeriod] = useState("Last 30 days");
  const [toast, setToast] = useState("");

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  };

  const pageDescriptions: Record<Tab, string> = {
    Overview: "Monitor product performance, trust signals, and system health.",
    Analyses: "Inspect every fact-check request and investigate uncertain results.",
    Users: "Manage accounts, installations, quotas, and access.",
    Feedback: "Review user ratings, corrections, and disputed verdicts.",
    Sources: "Maintain the source credibility database and scoring policy.",
    "AI & Pipeline": "Measure model quality, cost, latency, and stage reliability.",
    "System Health": "Track service uptime, dependencies, and active incidents.",
    Database: "Safely inspect PostgreSQL, Redis, and Qdrant in read-only mode.",
    Settings: "Control admin access, retention, thresholds, and audit history.",
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">✓</div><div><strong>Verity</strong><span>Control center</span></div></div>
        <nav aria-label="Admin sections">
          <span className="nav-label">Workspace</span>
          {tabs.slice(0, 6).map((tab) => <button key={tab.label} onClick={() => setActiveTab(tab.label)} className={activeTab === tab.label ? "active" : ""}><span>{tab.icon}</span>{tab.label}{tab.label === "Feedback" && <b>12</b>}</button>)}
          <span className="nav-label nav-system">System</span>
          {tabs.slice(6).map((tab) => <button key={tab.label} onClick={() => setActiveTab(tab.label)} className={activeTab === tab.label ? "active" : ""}><span>{tab.icon}</span>{tab.label}</button>)}
        </nav>
        <div className="sidebar-footer">
          <div className="usage"><div><span>Monthly analyses</span><strong>62%</strong></div><div className="usage-track"><i /></div><small>62,481 of 100,000</small></div>
          <button className="admin-profile"><span>LT</span><div><strong>Lam Thien</strong><small>Super admin</small></div><b>•••</b></button>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="mobile-brand"><div className="brand-mark">✓</div><strong>Verity</strong></div>
          <label className="global-search"><span>⌕</span><input placeholder="Search analyses, users, sources..." /><kbd>⌘ K</kbd></label>
          <div className="top-actions"><button aria-label="View notifications">♢<i /></button><button aria-label="Open help">?</button><div className="environment"><i />Production</div></div>
        </header>
        <div className="mobile-nav">{tabs.map((tab) => <button key={tab.label} onClick={() => setActiveTab(tab.label)} className={activeTab === tab.label ? "active" : ""}>{tab.label}</button>)}</div>
        <div className="content">
          <div className="page-header">
            <div><div className="eyebrow">VERITY ADMIN / {activeTab.toUpperCase()}</div><h1>{activeTab}</h1><p>{pageDescriptions[activeTab]}</p></div>
            <div className="page-actions">
              {(activeTab === "Overview" || activeTab === "Analyses" || activeTab === "AI & Pipeline") && <select value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Reporting period"><option>Last 24 hours</option><option>Last 7 days</option><option>Last 30 days</option><option>Last 90 days</option></select>}
              <button className="secondary-button" onClick={() => notify("Report export prepared")}>⇩ Export report</button>
            </div>
          </div>
          {activeTab === "Overview" && <Overview onNavigate={setActiveTab} />}
          {activeTab === "Analyses" && <AnalysesPage />}
          {activeTab === "Sources" && <SourcesPage />}
          {activeTab === "AI & Pipeline" && <PipelinePage />}
          {activeTab === "System Health" && <HealthPage />}
          {activeTab === "Database" && <DatabasePage />}
          {(activeTab === "Users" || activeTab === "Feedback" || activeTab === "Settings") && <PlaceholderPage type={activeTab} />}
        </div>
      </main>
      {toast && <div className="toast"><span>✓</span>{toast}</div>}
    </div>
  );
}

// The consultation screen.
//
// One design constraint governs this file: `04-targets.md` says the doctor has two
// minutes and must be able to read this in **fifteen seconds**. So it is optimised
// to be read, not to be comprehensive — the things that change management sit at the
// top in colour, and the completeness lives below the fold where it does not compete.
//
// Gate G3 is the other one: the physician is the authority. Nothing is permanent until
// they press a button, the summary is editable, and nothing on this screen states or
// implies a diagnosis.

import { useCallback, useEffect, useState } from "react";

const TOKEN_KEY = "aapka.doctor.token";

type Section = { key: string; title: string; lines: string[]; note: string | null };

type Summary = {
  session_id: string;
  patient: { age_band: string | null; sex: string | null; respondent: string; language: string };
  proxy_note: string | null;
  red_flag: { label: string; severity: string; staff_alert: string } | null;
  sections: Section[];
  coverage: {
    socrates: { text: string };
    dashavidha: { text: string };
    sections: Record<string, { filled: number; reachable: number; percent: number }>;
  };
  interactions: { drug_a: string; drug_b: string; note: string; severity: string; scope: string }[];
  abnormal_values: {
    analyte: string; value: number; unit: string | null;
    ref_low: number | null; ref_high: number | null; direction: string; ref_source: string;
  }[];
  audit: { node: string | null; why: string; answered: unknown }[];
  elapsed_s: number;
  budget_s: number;
  generated_from: string;
  disclaimer: string;
};

type QueueRow = {
  session_id: string;
  complaint: string;
  age_band: string | null;
  sex: string | null;
  red_flag: boolean;
  proxy: boolean;
  reviewed: boolean;
};

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [authed, setAuthed] = useState(false);
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [abdm, setAbdm] = useState<{ mode: string; live: boolean; notice: string | null } | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [showAudit, setShowAudit] = useState(false);
  const [decision, setDecision] = useState<string | null>(null);

  const headers = useCallback(
    () => ({ "Content-Type": "application/json", Authorization: `Bearer ${token}` }),
    [token],
  );

  const loadQueue = useCallback(async () => {
    const response = await fetch("/api/doctor/queue", { headers: headers() });
    if (!response.ok) {
      setAuthed(false);
      return;
    }
    const data = await response.json();
    setQueue(data.waiting);
    setAbdm(data.abdm);
    setStats(data.stats);
    setAuthed(true);
    localStorage.setItem(TOKEN_KEY, token);
  }, [headers, token]);

  useEffect(() => {
    if (!token) return;
    void loadQueue();
    const timer = window.setInterval(loadQueue, 4000);
    return () => window.clearInterval(timer);
  }, [token, loadQueue]);

  const open = async (id: string) => {
    setSelected(id);
    setDecision(null);
    setEdits({});
    const response = await fetch(`/api/doctor/summary/${id}`, { headers: headers() });
    if (response.ok) setSummary((await response.json()).summary);
  };

  const decide = async (choice: string) => {
    if (!selected) return;
    await fetch(`/api/doctor/summary/${selected}/decision`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ decision: choice, amendments: edits }),
    });
    setDecision(choice);
    void loadQueue();
    if (choice === "reject") {
      setSelected(null);
      setSummary(null);
    }
  };

  if (!authed) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-100">
        <div className="w-[440px] rounded-2xl bg-white p-8 shadow-sm">
          <h1 className="text-2xl font-semibold">Aapka — consultation view</h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter the department token to see waiting summaries.
          </p>
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadQueue()}
            placeholder="demo-doctor-token"
            className="mt-5 w-full rounded-lg border border-slate-300 px-4 py-3 text-lg"
          />
          <button
            onClick={loadQueue}
            className="mt-4 w-full rounded-lg bg-slate-900 py-3 font-semibold text-white"
          >
            Open
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-slate-100 text-slate-900">
      {/* ------------------------------------------------ queue */}
      <aside className="flex w-80 shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h1 className="text-lg font-semibold">Waiting</h1>
          <p className="text-xs text-slate-500">
            {queue.length} intake{queue.length === 1 ? "" : "s"} ready
          </p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {queue.length === 0 && (
            <p className="p-5 text-sm text-slate-400">
              Nothing waiting. Summaries appear here the moment a patient finishes at
              the terminal.
            </p>
          )}
          {queue.map((row) => (
            <button
              key={row.session_id}
              onClick={() => open(row.session_id)}
              className={`block w-full border-b border-slate-100 px-5 py-4 text-left hover:bg-slate-50 ${
                selected === row.session_id ? "bg-slate-100" : ""
              }`}
            >
              <div className="flex items-center gap-2">
                {row.red_flag && (
                  <span className="rounded bg-red-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                    Escalated
                  </span>
                )}
                {row.proxy && (
                  <span className="rounded bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                    Proxy
                  </span>
                )}
                {row.reviewed && <span className="text-[10px] text-slate-400">reviewed</span>}
              </div>
              <p className="mt-1 font-medium leading-snug">{row.complaint}</p>
              <p className="text-xs text-slate-500">
                {[row.sex, row.age_band].filter(Boolean).join(", ") || "details not given"}
              </p>
            </button>
          ))}
        </div>
        <Footer abdm={abdm} stats={stats} />
      </aside>

      {/* ------------------------------------------------ summary */}
      <main className="flex-1 overflow-y-auto">
        {!summary ? (
          <div className="flex h-full items-center justify-center text-slate-400">
            Select a patient
          </div>
        ) : (
          <div className="mx-auto max-w-4xl px-8 py-6">
            {/* The fifteen-second block. Everything that changes what the doctor does
                in the next two minutes is above this line. */}
            {summary.red_flag && (
              <Banner tone="red" title={`Escalated at the terminal — ${summary.red_flag.label}`}>
                {summary.red_flag.staff_alert} This patient was sent to triage and did
                not complete the interview.
              </Banner>
            )}
            {summary.proxy_note && (
              <Banner tone="amber" title="Not answered by the patient">
                {summary.proxy_note} Confirm anything that matters directly.
              </Banner>
            )}
            {summary.abnormal_values.length > 0 && (
              <Banner tone="red" title="Out-of-range results in the patient's own papers">
                <ul className="mt-1 space-y-0.5">
                  {summary.abnormal_values.map((value, i) => (
                    <li key={i}>
                      <strong>{value.analyte}</strong> {value.value} {value.unit ?? ""}{" "}
                      <span className="uppercase">({value.direction})</span> — reference{" "}
                      {value.ref_low}–{value.ref_high}
                      <span className="text-xs opacity-60">
                        {" "}
                        [{value.ref_source === "document" ? "range from the report" : "range from our table"}]
                      </span>
                    </li>
                  ))}
                </ul>
              </Banner>
            )}
            {summary.interactions.length > 0 && (
              <Banner tone="amber" title="Possible drug interaction">
                <ul className="mt-1 space-y-0.5">
                  {summary.interactions.map((hit, i) => (
                    <li key={i}>
                      <strong>{hit.drug_a}</strong> + <strong>{hit.drug_b}</strong> — {hit.note}
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs opacity-70">{summary.interactions[0].scope}.</p>
              </Banner>
            )}

            <header className="mb-5 mt-2 flex items-end justify-between border-b border-slate-200 pb-4">
              <div>
                <h1 className="text-2xl font-semibold">
                  {[summary.patient.sex, summary.patient.age_band].filter(Boolean).join(", ") ||
                    "Patient"}
                </h1>
                <p className="text-sm text-slate-500">
                  Intake took {Math.round(summary.elapsed_s)} s of a {summary.budget_s} s budget ·{" "}
                  SOCRATES {summary.coverage.socrates.text} · Dashavidha{" "}
                  {summary.coverage.dashavidha.text}
                </p>
              </div>
              <button
                onClick={() => setShowAudit((s) => !s)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-white"
              >
                {showAudit ? "Hide" : "Why these questions?"}
              </button>
            </header>

            {showAudit && (
              <div className="mb-5 rounded-lg border border-slate-200 bg-white p-4 text-xs">
                <p className="mb-2 font-semibold">
                  Every question, and the rule that caused it to be asked.
                </p>
                <ul className="space-y-1 font-mono text-[11px] text-slate-600">
                  {summary.audit.map((entry, i) => (
                    <li key={i}>
                      <span className="text-slate-900">{entry.node ?? "—"}</span> · {entry.why}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {summary.sections.map((section) => (
              <section key={section.key} className="mb-5">
                <h2 className="mb-1.5 text-xs font-bold uppercase tracking-wider text-slate-400">
                  {section.title}
                </h2>
                {section.lines.length === 0 ? (
                  <p className="text-sm italic text-slate-400">Not captured</p>
                ) : (
                  <ul className="space-y-1">
                    {section.lines.map((line, i) => (
                      <li
                        key={i}
                        className={`leading-relaxed ${
                          line.startsWith("    ") ? "pl-6 text-sm text-slate-600" : ""
                        } ${
                          line.startsWith("ALLERGY") || line.startsWith("DANGER")
                            ? "font-semibold text-red-700"
                            : ""
                        } ${line.includes("ABNORMAL") ? "font-medium text-red-700" : ""}`}
                      >
                        {line.trim()}
                      </li>
                    ))}
                  </ul>
                )}
                {section.note && (
                  <p className="mt-1.5 rounded border-l-2 border-slate-300 bg-slate-50 py-1 pl-3 text-xs text-slate-500">
                    {section.note}
                  </p>
                )}
                <textarea
                  value={edits[section.key] ?? ""}
                  onChange={(e) => setEdits({ ...edits, [section.key]: e.target.value })}
                  placeholder="Amend this section…"
                  rows={edits[section.key] ? 3 : 1}
                  className="mt-2 w-full resize-none rounded border border-slate-200 bg-white px-3 py-1.5 text-sm placeholder:text-slate-300 focus:border-slate-400 focus:outline-none"
                />
              </section>
            ))}

            <p className="mt-6 rounded-lg bg-slate-200/60 p-3 text-xs leading-relaxed text-slate-600">
              {summary.disclaimer} HPI paragraph produced by:{" "}
              <strong>{summary.generated_from}</strong>.
            </p>

            {/* Gate G3. Nothing is permanent until one of these is pressed. */}
            <div className="sticky bottom-0 mt-5 flex gap-3 border-t border-slate-200 bg-slate-100 py-4">
              <button
                onClick={() => decide("accept")}
                className="flex-[2] rounded-lg bg-emerald-700 py-3 font-semibold text-white"
              >
                Accept
              </button>
              <button
                onClick={() => decide("amend")}
                disabled={Object.values(edits).every((v) => !v)}
                className="flex-1 rounded-lg bg-slate-900 py-3 font-semibold text-white disabled:opacity-30"
              >
                Save amendments
              </button>
              <button
                onClick={() => decide("reject")}
                className="flex-1 rounded-lg border border-red-300 bg-white py-3 font-semibold text-red-700"
              >
                Reject
              </button>
            </div>
            {decision && (
              <p className="pb-6 text-sm text-emerald-700">Recorded: {decision}.</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function Banner({
  tone, title, children,
}: { tone: "red" | "amber"; title: string; children: React.ReactNode }) {
  const styles =
    tone === "red"
      ? "border-red-300 bg-red-50 text-red-900"
      : "border-amber-300 bg-amber-50 text-amber-900";
  return (
    <div className={`mb-3 rounded-lg border-l-4 p-3.5 text-sm ${styles}`}>
      <p className="font-bold">{title}</p>
      <div className="mt-0.5 leading-relaxed">{children}</div>
    </div>
  );
}

function Footer({
  abdm, stats,
}: { abdm: { mode: string; live: boolean; notice: string | null } | null; stats: Record<string, unknown> | null }) {
  return (
    <div className="border-t border-slate-200 p-4 text-[11px] leading-relaxed text-slate-500">
      {stats && (
        <p className="mb-2">
          {String(stats.completed_intakes)} intakes · {String(stats.escalations)} escalated ·
          mean {stats.mean_intake_s ? `${stats.mean_intake_s}s` : "—"}
        </p>
      )}
      {/* Impossible to demo a mock believing it is live. See server/aapka/abdm.py. */}
      {abdm && !abdm.live && (
        <p className="rounded border border-amber-300 bg-amber-50 p-2 text-amber-800">
          <strong>ABDM: {abdm.mode}.</strong> {abdm.notice}
        </p>
      )}
      {abdm?.live && (
        <p className="rounded border border-emerald-300 bg-emerald-50 p-2 text-emerald-800">
          <strong>ABDM sandbox connected.</strong>
        </p>
      )}
    </div>
  );
}

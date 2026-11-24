import React, { useEffect, useRef, useState } from "react";
import { Search, Users, Sparkles, Radar } from "lucide-react";
import { getJobs } from "../../services/jobService";
import { searchLinkedInCandidates } from "../../services/sourcingService";

// LinkedIn candidate sourcing: HR describes who they need, HERA suggests
// candidates from LinkedIn. The backend integration is pending; the page is
// fully built around honest loading and empty states so it demos cleanly and
// the team only has to swap services/sourcingService.js.

const SEARCH_PHASES = [
  "Reading your requirements…",
  "Scanning LinkedIn profiles…",
  "Ranking candidates by fit…",
];

export default function LinkedInSourcing() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [needs, setNeeds] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | searching | done
  const [phaseText, setPhaseText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const timers = useRef([]);

  useEffect(() => {
    let cancelled = false;
    getJobs()
      .then((data) => {
        if (cancelled) return;
        const list = Array.isArray(data) ? data : data?.jobs || data?.items || [];
        setJobs(list);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      timers.current.forEach(clearTimeout);
    };
  }, []);

  const runSearch = async (event) => {
    event.preventDefault();
    if (!needs.trim() && !jobId) {
      setError("Describe who you need, or pick a job to source for.");
      return;
    }
    setError("");
    setResult(null);
    setPhase("searching");
    timers.current.forEach(clearTimeout);
    timers.current = SEARCH_PHASES.map((text, i) =>
      setTimeout(() => setPhaseText(text), i * 900)
    );
    setPhaseText(SEARCH_PHASES[0]);
    try {
      const data = await searchLinkedInCandidates({ jobId, needs: needs.trim() });
      timers.current.push(
        setTimeout(() => {
          setResult(data);
          setPhase("done");
        }, SEARCH_PHASES.length * 900)
      );
    } catch (err) {
      setPhase("idle");
      setError(err?.message || "The search could not be completed.");
    }
  };

  const selectedJob = jobs.find((j) => String(j.id) === String(jobId));

  return (
    <section className="content-grid sourcing-grid">
      <div className="panel sourcing-hero">
        <p className="eyebrow"><Radar size={13} aria-hidden="true" /> LINKEDIN SOURCING</p>
        <h2>Tell HERA who you need. Get candidates from LinkedIn.</h2>
        <p className="sourcing-hero-sub">
          Skip the Boolean search. Describe the person you are looking for, or attach
          a job, and HERA suggests LinkedIn candidates ranked by fit.
        </p>

        <form className="sourcing-form" onSubmit={runSearch}>
          <label htmlFor="sourcing-job">Job (optional)</label>
          <select
            id="sourcing-job"
            value={jobId}
            onChange={(event) => setJobId(event.target.value)}
          >
            <option value="">No specific job</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>{job.title}</option>
            ))}
          </select>

          <label htmlFor="sourcing-needs">Who do you need?</label>
          <textarea
            id="sourcing-needs"
            rows="4"
            value={needs}
            onChange={(event) => setNeeds(event.target.value)}
            placeholder="e.g. Senior backend engineer, 5+ years Python and PostgreSQL, fintech experience, Cairo or remote-friendly"
          />

          {error && <p className="hera-note hera-error" role="alert">{error}</p>}

          <button type="submit" className="primary sourcing-submit" disabled={phase === "searching"}>
            <Search size={16} aria-hidden="true" />
            {phase === "searching" ? "Searching LinkedIn…" : "Find candidates"}
          </button>
        </form>
      </div>

      <div className="panel sourcing-results" aria-live="polite">
        {phase === "idle" && (
          <div className="sourcing-idle">
            <Radar size={40} aria-hidden="true" className="sourcing-idle-icon" />
            <h3>Your candidate suggestions appear here</h3>
            <p>Ranked by fit, with the evidence behind each match.</p>
          </div>
        )}

        {phase === "searching" && (
          <div className="sourcing-searching" role="status">
            <div className="sourcing-radar" aria-hidden="true">
              <span className="sourcing-radar-sweep" />
              <span className="sourcing-in-mark" aria-hidden="true">in</span>
            </div>
            <p className="sourcing-phase-text">{phaseText}</p>
            <div className="sourcing-skeleton-list" aria-hidden="true">
              <span className="motion-skeleton" style={{ height: 56 }} />
              <span className="motion-skeleton" style={{ height: 56, animationDelay: "120ms" }} />
              <span className="motion-skeleton" style={{ height: 56, animationDelay: "240ms" }} />
            </div>
          </div>
        )}

        {phase === "done" && result && result.status !== "ok" && (
          <div className="sourcing-empty">
            <Users size={40} aria-hidden="true" className="sourcing-idle-icon" />
            <h3>No LinkedIn candidates yet</h3>
            <p>
              {selectedJob
                ? `Sourcing for "${selectedJob.title}" is ready.`
                : "Your search is ready."}{" "}
              Ranked candidate suggestions from LinkedIn will appear here with fit
              scores and profile evidence as soon as sourcing results come in.
            </p>
            {needs.trim() && (
              <p className="sourcing-criteria"><Sparkles size={13} aria-hidden="true" /> Looking for: {needs.trim()}</p>
            )}
          </div>
        )}

        {phase === "done" && result && result.status === "ok" && (
          <ul className="sourcing-candidate-list motion-stagger">
            {(result.candidates || []).map((c) => (
              <li key={c.id} className="sourcing-candidate-card">
                <strong dir="auto">{c.name}</strong>
                <span dir="auto">{c.headline}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

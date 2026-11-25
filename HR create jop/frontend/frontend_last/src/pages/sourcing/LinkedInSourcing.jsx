import React, { useEffect, useRef, useState } from "react";
import { Search, Users, Sparkles, Radar, MapPin, Building2, ExternalLink, TriangleAlert } from "lucide-react";
import { getJobs } from "../../services/jobService";
import { searchLinkedInCandidates } from "../../services/sourcingService";

// LinkedIn candidate sourcing: HR describes who they need, HERA runs a real
// sourcing search through the backend (services/sourcingService.js) and shows
// the suggested profiles with their fit evidence.

const SEARCH_PHASES = [
  "Reading your requirements…",
  "Scanning LinkedIn profiles…",
  "Ranking candidates by fit…",
];

const PHASE_ROTATE_MS = 1800;

export default function LinkedInSourcing() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [needs, setNeeds] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | searching | done
  const [phaseText, setPhaseText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const rotator = useRef(null);

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
      if (rotator.current) clearInterval(rotator.current);
    };
  }, []);

  const startTheater = () => {
    let step = 0;
    setPhaseText(SEARCH_PHASES[0]);
    if (rotator.current) clearInterval(rotator.current);
    rotator.current = setInterval(() => {
      step = (step + 1) % SEARCH_PHASES.length;
      setPhaseText(SEARCH_PHASES[step]);
    }, PHASE_ROTATE_MS);
  };

  const stopTheater = () => {
    if (rotator.current) {
      clearInterval(rotator.current);
      rotator.current = null;
    }
  };

  const runSearch = async (event) => {
    event.preventDefault();
    if (!needs.trim() && !jobId) {
      setError("Describe who you need, or pick a job to source for.");
      return;
    }
    setError("");
    setResult(null);
    setPhase("searching");
    startTheater();
    try {
      const data = await searchLinkedInCandidates({ jobId, needs: needs.trim() });
      setResult(data);
      setPhase("done");
    } catch (err) {
      setPhase("idle");
      setError(err?.message || "The search could not be completed.");
    } finally {
      stopTheater();
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

        {phase === "done" && result && result.status === "failed" && (
          <div className="sourcing-empty" role="alert">
            <TriangleAlert size={40} aria-hidden="true" className="sourcing-idle-icon" />
            <h3>The search could not be completed</h3>
            <p>{result.errorMessage}</p>
          </div>
        )}

        {phase === "done" && result && result.status === "unavailable" && (
          <div className="sourcing-empty">
            <Users size={40} aria-hidden="true" className="sourcing-idle-icon" />
            <h3>LinkedIn sourcing is not enabled yet</h3>
            <p>
              The sourcing engine is built and ready. Once it is switched on for this
              workspace, ranked candidate suggestions from LinkedIn will appear here
              with fit scores and profile evidence.
            </p>
            {needs.trim() && (
              <p className="sourcing-criteria"><Sparkles size={13} aria-hidden="true" /> Looking for: {needs.trim()}</p>
            )}
          </div>
        )}

        {phase === "done" && result && result.status === "ok" && (
          <div className="sourcing-results-live">
            <div className="sourcing-results-head">
              <h3>
                {result.candidates.length}{" "}
                {result.candidates.length === 1 ? "candidate" : "candidates"} found
              </h3>
              {(needs.trim() || selectedJob) && (
                <p className="sourcing-criteria">
                  <Sparkles size={13} aria-hidden="true" />{" "}
                  {selectedJob ? `For: ${selectedJob.title}` : `Looking for: ${needs.trim()}`}
                </p>
              )}
            </div>
            <ul className="sourcing-candidate-list motion-stagger">
            {(result.candidates || []).map((c) => (
              <li key={c.id} className="sourcing-candidate-card">
                <div className="sourcing-candidate-main">
                  <strong dir="auto">{c.name}</strong>
                  {c.headline && <span dir="auto">{c.headline}</span>}
                  <span className="sourcing-candidate-meta">
                    {c.currentTitle && (
                      <span><Building2 size={12} aria-hidden="true" /> {c.currentTitle}{c.currentCompany ? ` at ${c.currentCompany}` : ""}</span>
                    )}
                    {c.location && (
                      <span><MapPin size={12} aria-hidden="true" /> {c.location}</span>
                    )}
                  </span>
                </div>
                <span className="sourcing-candidate-actions">
                  {c.email && (
                    <a className="sourcing-candidate-link" href={`mailto:${c.email}`}>
                      {c.email}
                    </a>
                  )}
                  {c.profileUrl && (
                    <a
                      className="sourcing-candidate-link"
                      href={c.profileUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Profile <ExternalLink size={12} aria-hidden="true" />
                    </a>
                  )}
                </span>
              </li>
            ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

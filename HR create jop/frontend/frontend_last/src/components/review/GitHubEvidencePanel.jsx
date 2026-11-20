import React, { useCallback, useEffect, useState } from "react";
import { AlertCircle, ExternalLink, GitBranch, RefreshCw, ShieldCheck } from "lucide-react";
import "./GitHubEvidencePanel.css";
import {
  getLatestGitHubEvidence,
  requestGitHubEvidenceConsent,
  retryGitHubEvidence,
} from "../../services/githubEvidenceService";

const STATUS_LABELS = {
  awaiting_consent: "Waiting for candidate consent",
  pending: "Queued for review",
  in_progress: "Review in progress",
  completed: "Review completed",
  failed: "Review failed",
  declined: "Candidate declined",
  consent_expired: "Consent link expired",
};
const CLASSIFICATION_LABELS = {
  direct: "Direct account-attributed activity",
  indirect: "Indirect project evidence",
  insufficient: "Insufficient evidence",
};

export default function GitHubEvidencePanel({ applicationId, githubUrl }) {
  const [urls, setUrls] = useState(githubUrl || "");
  const [analysis, setAnalysis] = useState(null);
  const [consentUrl, setConsentUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try {
      setAnalysis(await getLatestGitHubEvidence(applicationId));
    } catch {
      setError("Could not load GitHub evidence review status.");
    }
  }, [applicationId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!analysis || !["awaiting_consent", "pending", "in_progress"].includes(analysis.status)) return undefined;
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, [analysis, load]);

  const requestConsent = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    setConsentUrl("");
    try {
      const repositoryUrls = urls.split(/\r?\n/).map((url) => url.trim()).filter(Boolean);
      const result = await requestGitHubEvidenceConsent(applicationId, repositoryUrls);
      setConsentUrl(new URL(result.consent_url, window.location.origin).href);
      setNotice("Consent link created. Share it with the candidate; analysis starts only after they agree.");
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not create the consent link.");
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    if (!analysis) return;
    setBusy(true);
    setError("");
    try {
      setAnalysis(await retryGitHubEvidence(applicationId, analysis.id));
      setNotice("Retry queued.");
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not retry the review.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel review-block github-evidence-panel" aria-labelledby="github-evidence-heading">
      <div className="review-block-title">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <GitBranch size={18} aria-hidden="true" />
          <h3 id="github-evidence-heading">Public GitHub evidence</h3>
        </div>
        <span className="flag flag-human"><ShieldCheck size={12} aria-hidden="true" /> Advisory · HR review</span>
      </div>
      <p className="muted-note">
        Only public information is reviewed, with the candidate’s permission. Repository metadata is not proof of personal skill, and this review never changes scores or makes hiring decisions.
      </p>
      <label htmlFor="github-evidence-urls">GitHub profile or public repository URLs</label>
      <textarea
        id="github-evidence-urls"
        rows={2}
        value={urls}
        onChange={(event) => setUrls(event.target.value)}
        placeholder="https://github.com/username or https://github.com/owner/repository"
        aria-describedby="github-evidence-url-help"
      />
      <small id="github-evidence-url-help" className="muted-note">One URL per line, up to five. The candidate sees these links before consenting.</small>
      <div style={{ marginTop: 12 }}>
        <button type="button" className="btn btn-secondary btn-small" onClick={requestConsent} disabled={busy || !urls.trim()}>
          <ShieldCheck size={14} aria-hidden="true" /> {busy ? "Working…" : "Request candidate consent"}
        </button>
      </div>
      {consentUrl && (
        <div className="interview-invite-link-row" style={{ marginTop: 12 }}>
          <label htmlFor="github-evidence-consent-link">Share this one-time consent link</label>
          <input id="github-evidence-consent-link" readOnly value={consentUrl} onFocus={(event) => event.target.select()} />
        </div>
      )}
      {analysis && (
        <div className="github-evidence-results" aria-live="polite" aria-atomic="true" style={{ marginTop: 16 }}>
          <p><strong>Status:</strong> {STATUS_LABELS[analysis.status] || analysis.status}</p>
          {analysis.status === "failed" && (
            <div className="form-error" role="alert">
              <AlertCircle size={15} aria-hidden="true" /> Review could not be completed ({analysis.error_code || "unknown error"}). No evidence conclusion was produced.
              {analysis.error_code === "RATE_LIMITED" && analysis.retry_after_at && <span> Try again after {new Date(analysis.retry_after_at).toLocaleTimeString()}.</span>}
              <button type="button" className="btn btn-secondary btn-small" onClick={retry} disabled={busy || analysis.attempts >= 3}>
                <RefreshCw size={13} aria-hidden="true" /> Retry
              </button>
            </div>
          )}
          {analysis.status === "completed" && (
            <>
              {analysis.assessments?.map((assessment) => (
                <article className="github-requirement-evidence" key={assessment.requirement_key}>
                  <h4>{assessment.requirement_text} · {CLASSIFICATION_LABELS[assessment.classification]}</h4>
                  <span className="muted-note">{assessment.requirement_category.replaceAll("_", " ")}</span>
                  <p>{assessment.explanation}</p>
                  {assessment.limitations?.length > 0 && <p className="muted-note">Limitations: {assessment.limitations.join("; ")}</p>}
                  {assessment.evidence_ids?.length > 0 && (
                    <ul>
                      {assessment.evidence_ids.map((id) => {
                        const item = analysis.evidence?.find((entry) => entry.evidence_id === id);
                        return item ? <li key={id}><a href={item.source_url} target="_blank" rel="noopener noreferrer">{item.kind} source <ExternalLink size={12} aria-hidden="true" /></a><span className="muted-note"> — {item.limitation}</span><details><summary>View public observation</summary><pre>{JSON.stringify(item.content, null, 2)}</pre></details></li> : null;
                      })}
                    </ul>
                  )}
                </article>
              ))}
              {analysis.assessments?.every((assessment) => assessment.classification === "insufficient") && (
                <p className="muted-note">No sufficient public evidence was found. This does not mean the candidate lacks these skills.</p>
              )}
            </>
          )}
          {notice && <p role="status" className="form-success">{notice}</p>}
        </div>
      )}
      {error && <p role="alert" className="form-error">{error}</p>}
      {!analysis && notice && <p role="status" className="form-success">{notice}</p>}
    </section>
  );
}

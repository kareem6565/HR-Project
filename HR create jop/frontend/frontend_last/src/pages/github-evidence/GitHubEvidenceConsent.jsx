import React, { useEffect, useState } from "react";
import { Check, GitBranch, X } from "lucide-react";
import {
  previewGitHubEvidenceConsent,
  respondToGitHubEvidenceConsent,
} from "../../services/githubEvidenceService";

export default function GitHubEvidenceConsent() {
  const [token] = useState(() => window.location.hash.slice(1));
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(false);
  const [selfAttested, setSelfAttested] = useState(false);

  useEffect(() => {
    let active = true;
    if (!token) { setState("invalid"); return () => { active = false; }; }
    previewGitHubEvidenceConsent(token)
      .then((data) => active && (setPreview(data), setState("ready")))
      .catch((error) => active && setState(error?.response?.status === 404 ? "invalid" : "error"));
    return () => { active = false; };
  }, [token]);

  const respond = async (decision) => {
    setBusy(true);
    try {
      await respondToGitHubEvidenceConsent(token, decision);
      setState(decision);
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    } catch (error) {
      setState(error?.response?.status === 404 ? "invalid" : "error");
    } finally { setBusy(false); }
  };

  return (
    <main className="consent-page">
      <section className="panel consent-card" aria-labelledby="github-consent-title">
        <div className="consent-mark"><GitBranch size={24} aria-hidden="true" /></div>
        <p className="eyebrow">HERA · GITHUB EVIDENCE</p>
        <h1 id="github-consent-title">Your choice about public GitHub review</h1>
        {state === "loading" && <p role="status">Checking this consent link…</p>}
        {state === "invalid" && <p role="alert">This link has expired or was already used. Ask the organization for a new link.</p>}
        {state === "error" && <p role="alert">We could not save your choice because of a connection problem. Please try again.</p>}
        {state === "accepted" && <p role="status">Your permission is recorded. This review is advisory and will not change your application score or make a hiring decision.</p>}
        {state === "declined" && <p role="status">Your choice was recorded. Declining does not affect your application.</p>}
        {state === "ready" && preview && (
          <>
            <p><strong>{preview.organization_name}</strong> requests permission to review public GitHub material for this application.</p>
            <ul>{preview.repository_urls.map((url) => <li key={url}><a href={url} target="_blank" rel="noopener noreferrer">{url}</a></li>)}</ul>
            <p className="consent-copy">{preview.consent_text}</p>
            <p className="muted-note">One-time link expires {new Date(preview.link_expires_at).toLocaleString()}.</p>
            <label className="consent-self-attestation">
              <input type="checkbox" checked={selfAttested} onChange={(event) => setSelfAttested(event.target.checked)} />
              I am the candidate and I am making this choice myself.
            </label>
            <div className="consent-actions">
              <button type="button" className="btn-secondary" disabled={busy || !selfAttested} onClick={() => respond("declined")}><X size={16} aria-hidden="true" /> Decline</button>
              <button type="button" className="primary" disabled={busy || !selfAttested} onClick={() => respond("accepted")}><Check size={16} aria-hidden="true" /> {busy ? "Saving…" : "I agree"}</button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

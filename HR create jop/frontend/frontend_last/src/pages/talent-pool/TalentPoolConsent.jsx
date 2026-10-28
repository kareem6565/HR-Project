import React, { useEffect, useState } from "react";
import { Check, ShieldCheck, X } from "lucide-react";
import {
  previewTalentPoolConsent,
  respondToTalentPoolConsent,
} from "../../services/talentPoolService";

export default function TalentPoolConsent() {
  const [token] = useState(() => window.location.hash.slice(1));
  const [preview, setPreview] = useState(null);
  const [state, setState] = useState("loading");
  const [busy, setBusy] = useState(false);
  const [selfAttested, setSelfAttested] = useState(false);

  useEffect(() => {
    let active = true;
    if (!token) {
      setState("invalid");
      return () => { active = false; };
    }
    previewTalentPoolConsent(token)
      .then((data) => {
        if (active) {
          setPreview(data);
          setState("ready");
        }
      })
      .catch((error) => active && setState(error?.response?.status === 404 ? "invalid" : "error"));
    return () => { active = false; };
  }, [token]);

  const respond = async (decision) => {
    setBusy(true);
    try {
      await respondToTalentPoolConsent(token, decision);
      setState(decision);
      window.history.replaceState(
        window.history.state,
        "",
        window.location.pathname + window.location.search,
      );
    } catch (error) {
      setState(error?.response?.status === 404 ? "invalid" : "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="consent-page">
      <section className="panel consent-card" aria-labelledby="consent-title">
        <div className="consent-mark"><ShieldCheck size={24} aria-hidden="true" /></div>
        <p className="eyebrow">HERA TALENT POOL</p>
        <h1 id="consent-title">Your choice about future opportunities</h1>
        {state === "loading" && <p role="status">Checking this consent link…</p>}
        {state === "invalid" && (
          <p role="alert">This link has expired or has already been used. Ask the organization for a new link.</p>
        )}
        {state === "error" && (
          <p role="alert">We could not check or save your choice because of a connection problem. Please try again later.</p>
        )}
        {state === "accepted" && <p role="status">Your consent is recorded for 12 months. You may withdraw it by contacting the organization.</p>}
        {state === "declined" && <p role="status">Your choice not to join the Talent Pool is recorded. Your original application decision is unchanged.</p>}
        {state === "ready" && preview && (
          <>
            <p><strong>{preview.organization_name}</strong> is asking for your permission to consider your profile for future roles within this organization.</p>
            <p className="consent-copy">{preview.consent_text}</p>
            <p className="muted-note">This link expires {new Date(preview.link_expires_at).toLocaleString()} and can be used once.</p>
            <label className="consent-self-attestation">
              <input
                type="checkbox"
                checked={selfAttested}
                onChange={(event) => setSelfAttested(event.target.checked)}
              />
              I am the candidate and I am making this choice myself.
            </label>
            <div className="consent-actions">
              <button type="button" className="btn-secondary" disabled={busy || !selfAttested} onClick={() => respond("declined")}>
                <X size={16} aria-hidden="true" /> Decline
              </button>
              <button type="button" className="primary" disabled={busy || !selfAttested} onClick={() => respond("accepted")}>
                <Check size={16} aria-hidden="true" /> {busy ? "Saving…" : "I agree"}
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

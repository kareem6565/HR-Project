import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getPublicApplicationConfig, getPublicJob, submitPublicApplication } from "../../services/publicApi";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import "./PublicJobDetails.css";

const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY || "";

export default function PublicJobApplication() {
  const { publicId } = useParams();
  const location = useLocation();
  const [job, setJob] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const formRef = useRef(null);
  const widgetRef = useRef(null);
  const tokenRef = useRef("");
  const idempotencyRef = useRef("");

  useEffect(() => {
    let active = true;
    Promise.all([getPublicJob(publicId), getPublicApplicationConfig()])
      .then(([publicJob, applicationConfig]) => {
        if (active) { setJob(publicJob); setConfig(applicationConfig); }
      })
      .catch(() => { if (active) setError("This job application page is unavailable."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [publicId]);

  useEffect(() => {
    if (!config?.turnstile_required || !turnstileSiteKey || !widgetRef.current) return undefined;
    let widgetId;
    let cancelled = false;
    const renderWidget = () => {
      if (cancelled || !window.turnstile || !widgetRef.current || widgetId !== undefined) return;
      widgetId = window.turnstile.render(widgetRef.current, {
        sitekey: turnstileSiteKey,
        action: "public_application",
        callback: (token) => { tokenRef.current = token; setTurnstileToken(token); },
        "expired-callback": () => { tokenRef.current = ""; setTurnstileToken(""); },
        "error-callback": () => { tokenRef.current = ""; setTurnstileToken(""); },
      });
    };
    if (window.turnstile) renderWidget();
    else {
      let script = document.querySelector('script[data-hera-turnstile="true"]');
      if (!script) {
        script = document.createElement("script");
        script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
        script.async = true;
        script.defer = true;
        script.dataset.heraTurnstile = "true";
        document.head.appendChild(script);
      }
      script.addEventListener("load", renderWidget);
    }
    return () => {
      cancelled = true;
      if (widgetId !== undefined && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [config?.turnstile_required]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!formRef.current || !config?.notice_available) return;
    if (config.turnstile_required && (!turnstileSiteKey || !config.turnstile_server_configured || !turnstileToken)) {
      setError("Bot verification is unavailable. Please contact the hiring team.");
      return;
    }
    setSubmitting(true);
    setError("");
    const formData = new FormData(formRef.current);
    const resumeFile = formRef.current.elements.namedItem("resume")?.files?.[0];
    if (resumeFile) formData.set("resume", resumeFile);
    const query = new URLSearchParams(location.search);
    for (const key of ["utm_source", "utm_medium", "utm_campaign"]) {
      const value = query.get(key);
      if (value) formData.set(key, value);
    }
    formData.set("privacy_notice_version", config.privacy_notice_version);
    if (turnstileToken) formData.set("turnstile_token", turnstileToken);
    if (!idempotencyRef.current) {
      idempotencyRef.current = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
    }
    try {
      const result = await submitPublicApplication(publicId, formData, idempotencyRef.current);
      setConfirmation(result.application_reference);
      idempotencyRef.current = "";
    } catch (submitError) {
      setError(submitError?.response?.data?.detail || "We could not submit your application. Please try again.");
      if (window.turnstile && widgetRef.current) window.turnstile.reset();
      tokenRef.current = "";
      setTurnstileToken("");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <main className="public-job-page"><LoadingSpinner label="Loading application…" /></main>;
  if (!job) return <main className="public-job-page"><section className="public-job-card"><h1>Application unavailable</h1><p role="alert">{error}</p><Link to={`/careers/${encodeURIComponent(publicId)}`}>Back to job details</Link></section></main>;

  return <main className="public-job-page" dir="auto">
    <header className="public-job-brand"><span className="public-job-mark">H</span><strong>HERA Careers</strong></header>
    <article className="public-job-card public-application-card">
      <Link className="public-application-back" to={`/careers/${encodeURIComponent(publicId)}`}>← Back to job details</Link>
      <p className="public-job-company">{job.organization_name}</p>
      <h1>{job.title}</h1>
      {job.description && <p className="public-application-summary">{job.description.slice(0, 360)}{job.description.length > 360 ? "…" : ""}</p>}
      {!job.accepting_applications ? <div className="public-job-closed" role="status">Applications are no longer being accepted for this job.</div>
          : confirmation ? <section className="public-application-success" role="status"><h2>Application received</h2><p>Your application has been received. HERA has queued your CV for processing.</p><p>Reference: <strong>{confirmation}</strong></p></section>
          : !config?.notice_available ? <div className="public-job-closed" role="status">Applications are temporarily unavailable while the privacy notice is configured.</div>
            : <form ref={formRef} className="public-application-form" onSubmit={handleSubmit}>
              <label>Full name<input name="full_name" autoComplete="name" minLength="2" maxLength="255" required /></label>
              <label>Email address<input name="email" type="email" autoComplete="email" maxLength="255" required /></label>
              <label>Phone <span>(optional)</span><input name="phone" type="tel" autoComplete="tel" maxLength="50" /></label>
              <label>LinkedIn profile <span>(optional)</span><input name="linkedin_url" type="url" placeholder="https://www.linkedin.com/in/…" /></label>
              <label>GitHub profile <span>(optional)</span><input name="github_url" type="url" placeholder="https://github.com/…" /></label>
              <label>Portfolio <span>(optional)</span><input name="portfolio_url" type="url" placeholder="https://…" /></label>
              <label className="public-application-file">Resume / CV<input name="resume" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required /><small>PDF or DOCX, up to {Math.round(config.max_upload_bytes / 1024 / 1024)} MB.</small></label>
              <fieldset className="public-privacy-notice"><legend>Application privacy notice · {config.privacy_notice_version}</legend><p>{config.privacy_notice_text}</p><label className="public-privacy-accept"><input type="checkbox" name="privacy_accepted" value="true" required />I have read and acknowledge this notice for processing this job application. This does not enroll me in the talent pool.</label></fieldset>
              {config.turnstile_required && <div className="public-turnstile-wrap">{turnstileSiteKey && config.turnstile_server_configured ? <div ref={widgetRef} /> : <p role="alert">Bot verification is required but is not fully configured.</p>}</div>}
              {error && <div className="public-application-error" role="alert">{error}</div>}
              <button className="public-application-submit" type="submit" disabled={submitting || (config.turnstile_required && (!turnstileSiteKey || !config.turnstile_server_configured || !turnstileToken))}>{submitting ? "Submitting…" : "Submit application"}</button>
            </form>}
    </article>
    <footer className="public-job-footer">Powered by HERA</footer>
  </main>;
}

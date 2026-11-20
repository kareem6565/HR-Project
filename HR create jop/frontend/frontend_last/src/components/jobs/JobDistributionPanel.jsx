import { useEffect, useMemo, useState } from "react";
import { BarChart3, Check, Copy, ExternalLink, Megaphone, Sparkles } from "lucide-react";
import {
  createJobDistribution,
  generateDistributionPost,
  listJobDistributions,
  markJobDistributionShared,
  updateJobDistribution,
} from "../../services/jobDistributionService";
import LoadingSpinner from "../common/LoadingSpinner";
import "./JobDistributionPanel.css";

const CHANNELS = [
  { value: "linkedin", label: "LinkedIn", medium: "social", href: "https://www.linkedin.com/feed/" },
  { value: "facebook", label: "Facebook", medium: "social", href: "https://www.facebook.com/" },
  { value: "wuzzuf", label: "WUZZUF", medium: "job_board", href: "https://employers.wuzzuf.net/" },
  { value: "other", label: "Other channel", medium: "external", href: "" },
];

function trackedJobUrl(publicId, campaign, origin) {
  if (!publicId || !campaign?.tracking_key) return "";
  const url = new URL(`/careers/${encodeURIComponent(publicId)}`, origin);
  url.searchParams.set("utm_source", campaign.channel);
  url.searchParams.set("utm_medium", CHANNELS.find((item) => item.value === campaign.channel)?.medium || "external");
  url.searchParams.set("utm_campaign", campaign.tracking_key);
  return url.toString();
}

export default function JobDistributionPanel({ job }) {
  const [history, setHistory] = useState([]);
  const [current, setCurrent] = useState(null);
  const [channel, setChannel] = useState("linkedin");
  const [campaignName, setCampaignName] = useState(`${job.title} campaign`);
  const [postText, setPostText] = useState("");
  const [externalPostUrl, setExternalPostUrl] = useState("");
  const [hrReviewed, setHrReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const publicUrl = useMemo(
    () => trackedJobUrl(job.publicId, current, window.location.origin),
    [job.publicId, current],
  );
  const isShared = current?.status === "shared";
  const selectedChannel = CHANNELS.find((item) => item.value === (current?.channel || channel)) || CHANNELS[0];

  useEffect(() => {
    let active = true;
    listJobDistributions(job.id)
      .then((items) => { if (active) setHistory(items); })
      .catch(() => { if (active) setError("Could not load distribution history."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [job.id]);

  function selectCampaign(item) {
    setCurrent(item);
    setChannel(item.channel);
    setCampaignName(item.campaign_name);
    setPostText(item.post_text || "");
    setExternalPostUrl(item.external_post_url || "");
    setHrReviewed(Boolean(item.hr_reviewed_at));
    setMessage("");
    setError("");
  }

  async function refreshHistory(selected) {
    const items = await listJobDistributions(job.id);
    setHistory(items);
    if (selected) selectCampaign(items.find((item) => item.id === selected.id) || selected);
  }

  async function startCampaign() {
    setBusy(true); setError(""); setMessage(""); setHrReviewed(false);
    try {
      const item = await createJobDistribution(job.id, { channel, campaign_name: campaignName });
      setCurrent(item); setPostText(""); setExternalPostUrl("");
      await refreshHistory(item);
      try {
        const generated = await generateDistributionPost(item.id);
        setPostText(generated.post_text || "");
        setCurrent((value) => ({ ...value, post_text: generated.post_text || "", ai_generated: true }));
        setMessage("Draft prepared from the approved job profile. Review and edit it before sharing.");
        await refreshHistory({ ...item, post_text: generated.post_text || "", ai_generated: true });
      } catch (generationError) {
        setError(generationError?.response?.data?.detail || "AI draft could not be generated. You can still write the post manually.");
      }
    } catch (createError) {
      setError(createError?.response?.data?.detail || "Could not create this distribution draft.");
    } finally { setBusy(false); }
  }

  async function saveDraft() {
    if (!current) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await updateJobDistribution(current.id, { campaign_name: campaignName, post_text: postText });
      setCurrent(saved); setHrReviewed(false);
      await refreshHistory(saved);
      setMessage("Draft saved. Review it again before sharing.");
    } catch (saveError) {
      setError(saveError?.response?.data?.detail || "Could not save the draft.");
    } finally { setBusy(false); }
  }

  async function copyText(value, successMessage) {
    try {
      await navigator.clipboard.writeText(value);
      setError(""); setMessage(successMessage);
    } catch {
      setError("Clipboard access is unavailable. Select and copy the text or link manually.");
    }
  }

  async function markShared() {
    if (!current || !hrReviewed || !postText.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await updateJobDistribution(current.id, { campaign_name: campaignName, post_text: postText });
      const shared = await markJobDistributionShared(saved.id, externalPostUrl.trim());
      setCurrent(shared); setHrReviewed(true);
      await refreshHistory(shared);
      setMessage("Marked as shared based on your confirmation; HERA did not publish it.");
    } catch (shareError) {
      setError(shareError?.response?.data?.detail || "Could not update distribution history.");
    } finally { setBusy(false); }
  }

  if (loading) return <section className="panel job-distribution-panel"><LoadingSpinner label="Loading distribution history…" /></section>;

  return (
    <section className="panel job-distribution-panel" aria-labelledby="distribution-title">
      <header className="job-distribution-heading">
        <div className="job-distribution-title">
          <span className="job-distribution-icon"><Megaphone size={18} aria-hidden="true" /></span>
          <div><p className="eyebrow">RECRUITMENT DISTRIBUTION</p><h3 id="distribution-title">Share this published job</h3></div>
        </div>
        <span className="job-distribution-note">Manual sharing · HERA never posts automatically</span>
      </header>

      {!current && <div className="job-distribution-new">
        <label>Platform
          <select value={channel} onChange={(event) => setChannel(event.target.value)}>
            {CHANNELS.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label>Campaign name
          <input value={campaignName} maxLength={120} onChange={(event) => setCampaignName(event.target.value)} />
        </label>
        <button type="button" className="primary" onClick={startCampaign} disabled={busy || !campaignName.trim()}>
          <Sparkles size={16} aria-hidden="true" /> {busy ? "Preparing…" : "Create post draft"}
        </button>
      </div>}

      {current && <div className="job-distribution-editor">
        <div className="job-distribution-editor-meta">
          <span><strong>{selectedChannel.label}</strong> · {campaignName}</span>
          <span className={`job-distribution-status status-${current.status}`}>{current.status === "shared" ? "Marked shared" : "Draft"}</span>
          <button type="button" className="btn btn-secondary" onClick={() => { setCurrent(null); setPostText(""); setHrReviewed(false); setMessage(""); setError(""); }}>
            New campaign
          </button>
        </div>
        <label>Campaign name
          <input value={campaignName} maxLength={120} disabled={isShared} onChange={(event) => { setCampaignName(event.target.value); setHrReviewed(false); }} />
        </label>
        <label>Recruitment post
          <textarea aria-label="Recruitment post" rows="8" maxLength={5000} value={postText} disabled={isShared}
            onChange={(event) => { setPostText(event.target.value); setHrReviewed(false); }}
            placeholder="Generate a draft or write the post here." />
        </label>
        <div className="job-distribution-link-wrap">
          <span>Tracked HERA application page</span>
          <a href={publicUrl} target="_blank" rel="noreferrer">{publicUrl}</a>
        </div>
        <label className="job-distribution-external-url">Published platform post URL <span>(optional)</span>
          <input type="url" value={externalPostUrl} disabled={isShared} placeholder="https://…"
            onChange={(event) => setExternalPostUrl(event.target.value)} />
        </label>
        {current.ai_generated && <p className="job-distribution-generated"><Sparkles size={14} aria-hidden="true" /> AI draft based on the approved profile. Verify every detail before sharing.</p>}
        <label className="job-distribution-review">
          <input type="checkbox" checked={hrReviewed} disabled={isShared}
            onChange={(event) => setHrReviewed(event.target.checked)} />
          I reviewed this post against the approved job profile and approve sharing it.
        </label>
        <div className="job-distribution-actions">
          {!isShared && <button type="button" className="btn btn-secondary" disabled={busy || !postText.trim()} onClick={saveDraft}>{busy ? "Saving…" : "Save edits"}</button>}
          <button type="button" className="btn btn-secondary" disabled={!postText.trim() || !hrReviewed}
            onClick={() => copyText(`${postText.trim()}\n\nApply here: ${publicUrl}`, "Post and tracked application link copied.")}>
            <Copy size={15} aria-hidden="true" /> Copy post + link
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => copyText(publicUrl, "Tracked application link copied.")}>
            <Copy size={15} aria-hidden="true" /> Copy link
          </button>
          {selectedChannel.href && <a className="btn btn-secondary job-distribution-open-platform"
            href={selectedChannel.href} target="_blank" rel="noopener noreferrer" aria-disabled={!hrReviewed || !postText.trim()}
            onClick={(event) => { if (!hrReviewed || !postText.trim()) event.preventDefault(); }}>
            <ExternalLink size={15} aria-hidden="true" /> Open {selectedChannel.label}
          </a>}
          {!isShared && <button type="button" className="primary" disabled={busy || !hrReviewed || !postText.trim()} onClick={markShared}>
            <Check size={15} aria-hidden="true" /> Mark as shared
          </button>}
        </div>
      </div>}

      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="job-distribution-feedback" role="status">{message}</p>}

      {history.length > 0 && <div className="job-distribution-history">
        <h4><BarChart3 size={16} aria-hidden="true" /> Distribution history</h4>
        <ul>{history.map((item) => <li key={item.id}>
          <button type="button" className="job-distribution-history-item" onClick={() => selectCampaign(item)}>
            <span><strong>{item.campaign_name}</strong><small>{CHANNELS.find((channelItem) => channelItem.value === item.channel)?.label || item.channel}</small></span>
            <span className={`job-distribution-status status-${item.status}`}>{item.status === "shared" ? "Marked shared" : "Draft"}</span>
          </button>
          {item.external_post_url && <a href={item.external_post_url} target="_blank" rel="noreferrer">Open recorded platform post</a>}
        </li>)}</ul>
      </div>}
      <p className="job-distribution-footnote">Application attribution is counted when candidates submit through this HERA link. Page visits are request counts, not unique people.</p>
    </section>
  );
}

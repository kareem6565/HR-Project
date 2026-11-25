import { useCallback, useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import {
  correctHiredPipelineStage,
  getPipelineState,
  transitionPipelineStage,
} from "../../services/reviewService";

const LABELS = {
  screening: "Screening", review: "HR review", interview: "Interview", offer: "Offer",
  hired: "Hired", rejected: "Rejected", withdrawn: "Withdrawn", archived: "Archived",
};
const REASONS = [
  ["candidate_request", "Candidate request"],
  ["process_reopened", "Process reopened"],
  ["data_correction", "Data correction"],
  ["other", "Other"],
];
export default function PipelineStagePanel({ applicationId, refreshKey = 0 }) {
  const [state, setState] = useState(null);
  const [stage, setStage] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const result = await getPipelineState(applicationId);
      setState(result);
      setStage(result.allowed_next_stages?.[0] || result.allowed_correction_stages?.[0] || "");
    } catch {
      setError("Pipeline information could not be loaded.");
    }
  }, [applicationId]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const submit = async (corrective = false) => {
    if (!state || !stage) return;
    setBusy(true);
    setError("");
    try {
      const payload = {
        expected_stage: state.pipeline_stage,
        to_stage: stage,
        idempotency_key: window.crypto.randomUUID(),
        reason_code: reasonCode || undefined,
        ...(note.trim() ? { note: note.trim() } : {}),
      };
      const next = corrective
        ? await correctHiredPipelineStage(applicationId, { ...payload, reason: note.trim() })
        : await transitionPipelineStage(applicationId, payload);
      setState(next);
      setStage(next.allowed_next_stages?.[0] || next.allowed_correction_stages?.[0] || "");
      setReasonCode("");
      setNote("");
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || "The pipeline stage was not changed. Reload and try again.");
    } finally {
      setBusy(false);
    }
  };

  if (!state && !error) return <section className="pipeline-stage-panel" aria-busy="true">Loading pipeline…</section>;
  if (!state) return <section className="pipeline-stage-panel"><p role="alert">{error}</p><button type="button" onClick={load}>Retry</button></section>;

  const corrective = state.allowed_correction_stages?.length > 0;
  const requiresReason = corrective || state.reason_required_stages?.includes(stage);

  return (
    <section className="pipeline-stage-panel" aria-labelledby="pipeline-stage-heading">
      <div className="pipeline-stage-heading">
        <div><h3 id="pipeline-stage-heading">Hiring pipeline</h3><p>HR-controlled progress; AI results never change this stage.</p></div>
        <span className={`pipeline-stage-badge is-${state.pipeline_stage}`}>{LABELS[state.pipeline_stage]}</span>
      </div>
      {error && <p className="pipeline-stage-error" role="alert"><AlertCircle size={16} aria-hidden="true" />{error}</p>}
      {corrective && <p className="pipeline-stage-correction-note">A corrective change is logged. Any employee record created at Hired is left unchanged for an administrator to reconcile.</p>}
      {(state.allowed_next_stages?.length > 0 || corrective) && (
        <div className="pipeline-stage-controls">
          <label>
            <span>{corrective ? "Correct stage" : "Move to"}</span>
            <select aria-label="Next pipeline stage" value={stage} onChange={(event) => setStage(event.target.value)}>
              {corrective && state.allowed_correction_stages.map((value) => <option key={value} value={value}>{LABELS[value]}</option>)}
              {!corrective && state.allowed_next_stages.map((value) => <option key={value} value={value}>{LABELS[value]}</option>)}
            </select>
          </label>
          {requiresReason && <label>
            <span>Reason code</span>
            <select aria-label="Reason code" required value={reasonCode} onChange={(event) => setReasonCode(event.target.value)}>
              <option value="">Choose a reason</option>{REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>}
          <label className="pipeline-stage-note">
            <span>{corrective ? "Required correction reason" : "Note (optional)"}</span>
            <input aria-label={corrective ? "Required correction reason" : "Pipeline note"} value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button type="button" className="btn btn-secondary" disabled={busy || !stage || (requiresReason && !reasonCode) || (corrective && !note.trim())} onClick={() => submit(corrective)}>
            {busy ? "Saving…" : corrective ? "Record correction" : "Update stage"}
          </button>
        </div>
      )}
      <details className="pipeline-stage-history">
        <summary>Stage history ({state.transitions?.length || 0})</summary>
        <ol>{(state.transitions || []).map((entry) => <li key={entry.id}>{entry.from_stage ? `${LABELS[entry.from_stage] || entry.from_stage} → ` : "Baseline → "}{LABELS[entry.to_stage] || entry.to_stage}<small>{entry.source} · {new Date(entry.created_at).toLocaleString()}</small></li>)}</ol>
      </details>
    </section>
  );
}

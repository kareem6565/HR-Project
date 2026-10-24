import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Sparkles,
  Link2,
  Link as LinkIcon,
  Globe,
  ExternalLink,
  FileText,
  Pencil,
  MessageSquareText,
  Save,
} from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import Modal from "../../components/common/Modal";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Badge from "../../components/common/Badge";
import { getCandidateById, updateCandidate } from "../../services/candidateService";
import { findCandidateApplications } from "../../services/interviewQuestionSetService";

const Info = ({ l, v }) => (
  <div className="info">
    <span>{l}</span>
    <strong>{v || "—"}</strong>
  </div>
);

export default function CandidateDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [c, setC] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveOk, setSaveOk] = useState(false);
  const [prepOpen, setPrepOpen] = useState(false);
  const [candidateApps, setCandidateApps] = useState([]);
  const [appsLoading, setAppsLoading] = useState(true);
  const [appsError, setAppsError] = useState(false);
  const [appsAttempt, setAppsAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    getCandidateById(id)
      .then((data) => {
        if (!active) return;
        setC(data);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setC(null);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);

  useEffect(() => {
    let active = true;
    setAppsLoading(true);
    setAppsError(false);
    findCandidateApplications(id)
      .then((apps) => {
        if (active) setCandidateApps(apps);
      })
      .catch(() => {
        if (active) setAppsError(true);
      })
      .finally(() => {
        if (active) setAppsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, appsAttempt]);

  const openEdit = () => {
    setEmail(c?.email || "");
    setPhone(c?.phone || "");
    setSaveError("");
    setSaveOk(false);
    setEditOpen(true);
  };

  const saveContact = async () => {
    setSaving(true);
    setSaveError("");
    setSaveOk(false);
    try {
      const updated = await updateCandidate(id, {
        email: email.trim() || null,
        phone: phone.trim() || null,
      });
      setC({ ...c, email: updated?.email || "", phone: updated?.phone || "" });
      setSaveOk(true);
      setEditOpen(false);
    } catch (err) {
      setSaveError(
        err?.response?.data?.detail || "Could not save the candidate's contact details."
      );
    } finally {
      setSaving(false);
    }
  };

  const openPrep = () => {
    setPrepOpen(false);
    if (appsLoading) return;
    if (appsError) return;
    if (candidateApps.length === 1) {
      navigate(`/interview-questions?applicationId=${candidateApps[0].id}`);
      return;
    }
    if (candidateApps.length === 0) return;
    setPrepOpen(true);
  };

  if (loading) return <LoadingSpinner label="Loading candidate..." />;
  if (!c) {
    return (
      <section>
        <button className="back" onClick={() => navigate("/candidates")}>
          <ArrowLeft size={17} /> Back to Candidates
        </button>
        <div className="empty">Candidate not found.</div>
      </section>
    );
  }

  const skills = c.skills || [];

  return (
    <section>
      <button className="back" onClick={() => navigate("/candidates")}>
        <ArrowLeft size={17} /> Back to Candidates
      </button>

      {/* ===== Candidate Profile ===== */}
      <div className="detail-hero panel">
        <div className="detail-person">
          <div className="big-avatar">
            {c.name
              .split(" ")
              .map((x) => x[0])
              .join("")
              .slice(0, 2)}
          </div>
          <div>
            <span className="pill">
              <Sparkles size={13} /> Candidate Profile
            </span>
            <h2>{c.name}</h2>
            <p>{c.summary || c.title || "Profile extracted from resume"}</p>
            <div className="links">
              {c.linkedin && (
                <a href={c.linkedin} target="_blank" rel="noreferrer">
                  <LinkIcon size={16} /> LinkedIn <ExternalLink size={13} />
                </a>
              )}
              {c.github && (
                <a href={c.github} target="_blank" rel="noreferrer">
                  <Link2 size={16} /> GitHub <ExternalLink size={13} />
                </a>
              )}
              {c.portfolio && (
                <a href={c.portfolio} target="_blank" rel="noreferrer">
                  <Globe size={16} /> Portfolio <ExternalLink size={13} />
                </a>
              )}
              {c.cv && (
                <a href={c.cv} target="_blank" rel="noreferrer">
                  <FileText size={16} /> Resume <ExternalLink size={13} />
                </a>
              )}
            </div>
          </div>
        </div>
        <div className="detail-hero-actions">
          <div className="candidate-scope-note">
            <strong>Candidate profile across roles</strong>
            <span>Scores, evidence, and HR decisions belong to each job application.</span>
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">CONTACT</p>
              <h3>Candidate Details</h3>
            </div>
            <button className="btn-secondary" onClick={openEdit}>
              <Pencil size={15} /> Edit
            </button>
          </div>
          <Info l={c.email ? "Email" : c.profileEmail ? "Email (from CV)" : "Email"} v={c.email || c.profileEmail} />
          <Info l={c.phone ? "Phone" : c.profilePhone ? "Phone (from CV)" : "Phone"} v={c.phone || c.profilePhone} />
          <Info l="Experience" v={c.experience} />

          <h4>Skills</h4>
          <div className="chips">
            {skills.length ? (
              skills.map((s) => (
                <span className="chip good" key={s}>
                  {s}
                </span>
              ))
            ) : (
              <span className="none">No extracted profile skills yet.</span>
            )}
          </div>
        </div>

        {/* ===== Job-scoped applications ===== */}
        <div className="panel">
          <div className="panel-title">
            <div>
              <p className="eyebrow">JOB-SCOPED WORK</p>
              <h3>Applications</h3>
            </div>
            <button
              className="btn btn-secondary btn-small"
              onClick={openPrep}
              disabled={appsLoading || appsError || candidateApps.length === 0}
              title="Prepare questions for one of this candidate's job applications"
            >
              <MessageSquareText size={15} /> {appsLoading ? "Loading…" : "Prepare questions"}
            </button>
          </div>
          <p className="muted-note" style={{ marginTop: -12, marginBottom: 16 }}>
            Review each role-specific evaluation, evidence, and HR decision from its application.
          </p>
          {appsLoading ? (
            <LoadingSpinner label="Loading candidate applications…" />
          ) : appsError ? (
            <ErrorState
              message="Unable to load this candidate's applications."
              onRetry={() => setAppsAttempt((attempt) => attempt + 1)}
            />
          ) : candidateApps.length === 0 ? (
            <EmptyState message="No job applications are linked to this candidate yet." />
          ) : (
            <div className="application-picker" aria-label="Candidate applications">
              {candidateApps.map((app) => (
                <button
                  type="button"
                  key={app.id}
                  className="application-picker-row"
                  onClick={() => navigate(`/applications/${app.id}/review`)}
                >
                  <span>
                    <strong>{app.jobTitle || "Untitled job"}</strong>
                    <span className="muted-note" style={{ display: "block", marginTop: 4 }}>
                      Applied {app.createdAt ? new Date(app.createdAt).toLocaleDateString() : "date unavailable"}
                    </span>
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                    <Badge status={app.status} />
                    <ArrowRight size={15} aria-hidden="true" />
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ===== Edit Contact Modal ===== */}
      <Modal open={editOpen} title="Edit contact details" onClose={() => setEditOpen(false)}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="person@company.com"
          />
        </label>
        <label>
          Phone
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 (555) 000-0000"
          />
        </label>
        <p className="muted-note">
          These fields update the candidate record. Contact details extracted from the CV remain labeled as CV data.
        </p>
        {saveError && <div className="form-error">{saveError}</div>}
        {saveOk && <div className="form-success">Contact details saved.</div>}
        <div className="modal-actions">
          <button className="btn-secondary" onClick={() => setEditOpen(false)}>
            Cancel
          </button>
          <button className="primary" onClick={saveContact} disabled={saving}>
            <Save size={16} /> {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </Modal>

      {/* ===== Choose Application for Question Prep ===== */}
      <Modal
        open={prepOpen}
        title="Choose a job application"
        onClose={() => setPrepOpen(false)}
      >
        <p className="muted-note">
          {c.name} has multiple job applications. Pick the role you want to prepare questions for.
        </p>
        <div className="application-picker">
          {candidateApps.map((app) => (
            <button
              key={app.id}
              className="application-picker-row"
              onClick={() => navigate(`/interview-questions?applicationId=${app.id}`)}
            >
              <strong>{app.jobTitle || "Untitled job"}</strong>
              <span className="pill">{app.status}</span>
            </button>
          ))}
        </div>
      </Modal>
    </section>
  );
}

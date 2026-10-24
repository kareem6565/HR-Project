import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Pencil,
  Trash2,
  MapPin,
  Briefcase,
  Clock3,
  CheckCircle2,
  Rocket,
  Ban,
  Sparkles,
  FileCheck2,
  Users,
} from "lucide-react";
import Badge from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import Modal from "../../components/common/Modal";
import { getJobById, deleteJob, updateJob } from "../../services/jobService";
import {
  listJobProfiles,
  extractJobProfile,
  approveJobProfile,
} from "../../services/jobProfileService";

const REQUIREMENT_TONE = {
  must_have: "chip good",
  important: "chip",
  nice_to_have: "chip chip-neutral",
};

const QUALITY_FINDING_LABEL = {
  unclear_requirement: "Unclear requirement",
  potential_conflict: "Potential conflict",
  priority_unclear: "Priority may be unclear",
  not_measurable: "Hard to measure",
};

const SOURCE_LABEL = {
  ai_extracted: "AI extracted",
  hr_edited: "HR edited",
  hr_created: "HR created",
};

function sourceLabel(source) {
  return SOURCE_LABEL[source] || source;
}

// Job descriptions arrive with a derived requirements/skills suffix because
// that composition is what the existing API and job form persist.
function displayDescription(job) {
  const raw = job.description || "";
  const derivedLines = [
    ...(job.requirements || []).map((requirement) => `- ${requirement}`),
    ...(job.requiredSkills || []).map((skill) => `Skills: ${skill}`),
  ].join("\n");
  if (!derivedLines) return raw;
  if (raw === derivedLines) return "";
  const suffix = `\n${derivedLines}`;
  return raw.endsWith(suffix) ? raw.slice(0, -suffix.length) : raw;
}

export default function JobDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  const [profiles, setProfiles] = useState([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);

  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoadError(false);
    getJobById(id)
      .then((data) => {
        if (!active) return;
        setJob(data);
      })
      .catch(() => {
        if (!active) return;
        setLoadError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, loadAttempt]);

  useEffect(() => {
    if (!id) return;
    let active = true;
    setProfilesLoading(true);
    listJobProfiles(id)
      .then((data) => {
        if (!active) return;
        setProfiles(data || []);
      })
      .catch(() => {
        if (!active) return;
        setProfileError("Could not load job profiles from the backend.");
      })
      .finally(() => {
        if (active) setProfilesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id]);

  const reloadProfiles = () => {
    setProfilesLoading(true);
    setProfileError("");
    listJobProfiles(id)
      .then((data) => setProfiles(data || []))
      .catch(() => setProfileError("Could not load job profiles from the backend."))
      .finally(() => setProfilesLoading(false));
  };

  const onExtract = async () => {
    setProfileBusy(true);
    setProfileError("");
    try {
      await extractJobProfile(id);
      reloadProfiles();
    } catch (err) {
      setProfileError(
        err?.response?.data?.detail || "AI extraction failed. Please try again."
      );
    } finally {
      setProfileBusy(false);
    }
  };

  const onApprove = async (profileId) => {
    setProfileBusy(true);
    setProfileError("");
    try {
      await approveJobProfile(profileId);
      reloadProfiles();
    } catch (err) {
      setProfileError(
        err?.response?.data?.detail || "Could not approve this job profile."
      );
    } finally {
      setProfileBusy(false);
    }
  };

  const currentProfile = profiles.find((p) => p.is_current);
  const approvedProfile = profiles.find((p) => p.status === "approved");
  const draftProfile = profiles.find((p) => p.status === "draft");

  const onDelete = () => {
    setConfirmDeleteOpen(true);
    setDeleteError(null);
  };

  const confirmDelete = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteJob(job.id);
      navigate("/jobs");
    } catch (err) {
      setDeleteError(err?.response?.data?.detail || err?.message || "Unable to delete this job.");
    } finally {
      setDeleting(false);
    }
  };

  const onChangeStatus = async () => {
    const next = job.status === "active" ? "closed" : "active";
    const updated = await updateJob(job.id, { status: next });
    if (updated) setJob(updated);
  };

  const isActive = job?.status === "active";

  if (loading) return <LoadingSpinner label="Loading job..." />;
  if (loadError) {
    return (
      <section className="job-details-page">
        <button className="btn btn-secondary job-details-back" onClick={() => navigate("/jobs")}>
          <ArrowLeft size={16} aria-hidden="true" /> Back to Jobs
        </button>
        <ErrorState
          message="Unable to load this job. Check your connection and try again."
          onRetry={() => setLoadAttempt((attempt) => attempt + 1)}
        />
      </section>
    );
  }
  if (!job) {
    return (
      <section className="job-details-page">
        <button className="btn btn-secondary job-details-back" onClick={() => navigate("/jobs")}>
          <ArrowLeft size={16} aria-hidden="true" /> Back to Jobs
        </button>
        <div className="panel job-details-not-found">
          <h2>Job not found</h2>
          <p>This job may have been removed or you may not have access to it.</p>
        </div>
      </section>
    );
  }

  const description = displayDescription(job);

  return (
    <section className="job-details-page">
      <div className="job-details-toolbar">
        <button className="btn btn-secondary job-details-back" onClick={() => navigate("/jobs")}>
          <ArrowLeft size={16} aria-hidden="true" /> Back to Jobs
        </button>
        <div className="job-details-actions">
          <Badge status={job.status} />
          {!isActive && (
            <button className="primary" onClick={onChangeStatus}>
              <Rocket size={16} aria-hidden="true" /> Publish
            </button>
          )}
          {isActive && (
            <button className="btn btn-secondary" onClick={onChangeStatus}>
              <Ban size={16} aria-hidden="true" /> Close
            </button>
          )}
          <button
            type="button"
            className="icon-btn"
            onClick={() => navigate(`/jobs/${job.id}/edit`)}
            aria-label={`Edit ${job.title}`}
            title="Edit job"
          >
            <Pencil size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="icon-btn danger"
            onClick={onDelete}
            aria-label={`Delete ${job.title}`}
            title="Delete job"
          >
            <Trash2 size={16} aria-hidden="true" />
          </button>
        </div>
      </div>

      <header className="detail-hero panel job-details-hero">
        <div className="job-details-identity">
          <span className="pill">
            <Briefcase size={13} aria-hidden="true" /> {job.department || "Department not specified"}
          </span>
          <h2>{job.title}</h2>
          <div className="job-meta">
            <span>
              <MapPin size={14} aria-hidden="true" /> {job.location || "Location not specified"}
            </span>
            <span>
              <Clock3 size={14} aria-hidden="true" /> {job.type || "Employment type not specified"}
            </span>
            {job.experience && <span>{job.experience} experience</span>}
          </div>
        </div>
      </header>

      <div className="detail-grid job-details-grid">
        <div className="panel job-details-description-panel">
          <div className="job-details-section-heading">
            <div>
              <p className="eyebrow">ROLE OVERVIEW</p>
              <h3>Description</h3>
            </div>
          </div>
          {description ? (
            <p className="job-description job-details-description">{description}</p>
          ) : (
            <p className="job-details-empty-copy">No separate job description has been provided.</p>
          )}
        </div>

        <div className="panel job-details-facts-panel">
          <div className="job-details-section-heading">
            <div>
              <p className="eyebrow">ROLE REQUIREMENTS</p>
              <h3>Requirements</h3>
            </div>
          </div>
          {job.requirements?.length ? (
            <ul className="requirements-list">
              {job.requirements.map((requirement, index) => (
                <li key={`${requirement}-${index}`}>
                  <CheckCircle2 size={15} aria-hidden="true" /> {requirement}
                </li>
              ))}
            </ul>
          ) : (
            <p className="job-details-empty-copy">No requirements are listed for this job.</p>
          )}
        </div>
      </div>

      <div className="job-details-support-grid">
        <div className="panel job-details-skills-panel">
          <div className="job-details-section-heading">
            <div>
              <p className="eyebrow">CAPABILITIES</p>
              <h3>Required skills</h3>
            </div>
          </div>
          {job.requiredSkills?.length ? (
            <div className="chips">
              {job.requiredSkills.map((skill) => (
                <span className="chip good" key={skill}>{skill}</span>
              ))}
            </div>
          ) : (
            <p className="job-details-empty-copy">No required skills are listed for this job.</p>
          )}
        </div>

        <div className="panel job-details-activity-panel">
          <p className="eyebrow">HIRING ACTIVITY</p>
          <div className="job-details-snapshot">
            <div>
              <span>Applicants</span>
              <strong><Users size={15} aria-hidden="true" /> {job.applicants} candidates applied</strong>
            </div>
          </div>
        </div>
      </div>

      <div className="panel job-details-profile-panel">
        <div className="panel-title job-details-profile-heading">
          <div>
            <p className="eyebrow">AI EXTRACTION</p>
            <h3>Job Profile</h3>
          </div>
          {!profilesLoading && !approvedProfile && draftProfile && (
            <span className="muted-note">Awaiting HR approval before screening can run.</span>
          )}
          {approvedProfile && (
            <Badge status="approved" />
          )}
        </div>

        {profileError && profiles.length > 0 && <div className="form-error" role="alert">{profileError}</div>}

        {profilesLoading ? (
          <LoadingSpinner label="Loading job profiles..." />
        ) : profiles.length === 0 && profileError ? (
          <div className="job-profile-load-error" role="alert">
            <p>{profileError}</p>
            <button type="button" className="btn btn-secondary" onClick={reloadProfiles}>
              Reload profile data
            </button>
          </div>
        ) : profiles.length === 0 ? (
          <div className="empty job-profile-empty">
            <span className="job-profile-empty-icon"><Sparkles size={18} aria-hidden="true" /></span>
            <div>
              <strong>No job profile yet</strong>
              <p>HERA can extract a structured draft from the job description. Review and approve it before screening.</p>
            </div>
          </div>
        ) : (
          profiles
            .slice()
            .reverse()
            .map((profile) => {
              const data = profile.profile_data || {};
              const requirements = Array.isArray(data.requirements) ? data.requirements : [];
              return (
                <div className="profile-card" key={profile.id}>
                  <div className="profile-card-head">
                    <div>
                      <strong>{data.title || "Extracted Job Profile"}</strong>
                      <span className="muted-note">
                        v{profile.version_number} · {sourceLabel(profile.source)}
                        {profile.is_current ? " · current" : ""}
                      </span>
                    </div>
                    <div className="profile-card-actions">
                      <Badge status={profile.status} />
                      {profile.status === "draft" && (
                        <button
                          className="primary"
                          disabled={profileBusy}
                          onClick={() => onApprove(profile.id)}
                        >
                          <FileCheck2 size={16} /> Approve
                        </button>
                      )}
                    </div>
                  </div>

                  {data.summary && <p className="muted-note">{data.summary}</p>}

                  {requirements.length > 0 && (
                    <>
                      <h4>Requirements</h4>
                      <div className="chips">
                        {requirements.map((req) => (
                          <span className={REQUIREMENT_TONE[req.category] || "chip"} key={req.key || req.text}>
                            {req.text}
                            {req.category ? ` · ${req.category.replaceAll("_", " ")}` : ""}
                          </span>
                        ))}
                      </div>
                    </>
                  )}

                  <section
                    className="job-quality-review"
                    aria-label="Job description quality review"
                  >
                    <h4>Job description quality check</h4>
                    {!data.quality_review || data.quality_review.status === "unavailable" ? (
                      <p>
                        A quality review was not returned. Review the original description before
                        approving this profile.
                      </p>
                    ) : (
                      <>
                        {data.quality_review.status === "partially_verified" && (
                          <p role="status">
                            Some findings were omitted because their quotes could not be verified
                            against the source description.
                          </p>
                        )}
                        {data.quality_review.findings?.length ? (
                          <ul>
                            {data.quality_review.findings.map((finding, index) => (
                              <li key={`${finding.finding_type}-${index}`}>
                                <strong>
                                  {QUALITY_FINDING_LABEL[finding.finding_type] || "Review"}
                                </strong>
                                <blockquote dir="auto">{finding.source_quote}</blockquote>
                                <p>{finding.concern}</p>
                                <p className="job-quality-question">
                                  <span>Question for HR: </span>{finding.question_for_hr}
                                </p>
                              </li>
                            ))}
                          </ul>
                        ) : data.quality_review.status === "partially_verified" ? (
                          <p>
                            No verified findings remain. Review the source description before
                            approving this profile.
                          </p>
                        ) : (
                          <p>
                            HERA did not flag an obvious issue. Please review the source description
                            yourself; this check does not guarantee completeness.
                          </p>
                        )}
                      </>
                    )}
                  </section>
                </div>
              );
            })
        )}

        <div className="profile-card-actions footer-actions job-profile-footer">
          <button
            type="button"
            className="btn-secondary"
            disabled={profileBusy || !job.description}
            onClick={onExtract}
            title={job.description ? "" : "No job description available to extract from."}
          >
            <Sparkles size={16} aria-hidden="true" /> {currentProfile ? "Re-run AI extraction" : "Run AI extraction"}
          </button>
        </div>
      </div>

      <Modal
        open={confirmDeleteOpen}
        onClose={() => {
          if (!deleting) {
            setConfirmDeleteOpen(false);
            setDeleteError(null);
          }
        }}
        title={`Delete Job: ${job.title}`}
      >
        <p>
          Are you sure you want to delete <strong>{job.title}</strong>? This action cannot be undone.
        </p>
        {deleteError && (
          <p className="form-error" role="alert" style={{ marginTop: 12 }}>
            {deleteError}
          </p>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setConfirmDeleteOpen(false);
              setDeleteError(null);
            }}
            disabled={deleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={confirmDelete}
            disabled={deleting}
          >
            {deleting ? "Deleting…" : "Delete Job"}
          </button>
        </div>
      </Modal>
    </section>
  );
}

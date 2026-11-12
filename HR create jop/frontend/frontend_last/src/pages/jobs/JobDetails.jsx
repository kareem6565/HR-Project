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
  Copy,
} from "lucide-react";
import Badge from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import Modal from "../../components/common/Modal";
import JobDistributionPanel from "../../components/jobs/JobDistributionPanel";
import { getJobById, deleteJob, updateJob, downloadJobSourceFile, publishJob, closePublicJob } from "../../services/jobService";
import {
  listJobProfiles,
  extractJobProfile,
  approveJobProfile,
  updateJobProfile,
  buildJobDescription,
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

const EXTRACTION_STATUS_LABEL = {
  pending: "AI extraction pending",
  in_progress: "AI extraction in progress",
  failed: "AI extraction failed",
  completed: "AI extraction completed",
};

const FIELD_ORIGIN_LABEL = {
  hera_suggested: "Suggested by HERA",
  hr_entered_or_edited: "Entered or edited by HR",
  hr_edited_after_hera_suggestion: "Suggested by HERA, then reviewed or edited by HR",
  not_provided: "Not provided",
};

const PROFILE_REQUIREMENT_SECTIONS = [
  { key: "responsibilities", title: "Responsibilities", dimensions: ["responsibility"] },
  { key: "qualifications", title: "Qualifications", dimensions: ["experience", "education", "certification"] },
  { key: "skills", title: "Skills", dimensions: ["skill", "technical_skill", "soft_skill"] },
];

function groupProfileRequirements(requirements) {
  const groups = PROFILE_REQUIREMENT_SECTIONS.map((section) => ({ ...section, items: [] }));
  const other = { key: "other", title: "Other criteria", items: [] };
  requirements.forEach((requirement, index) => {
    const group = groups.find((section) => section.dimensions.includes(requirement.dimension || "skill"));
    (group || other).items.push({ requirement, index });
  });
  return [...groups, ...(other.items.length ? [other] : [])];
}

function extractionStatus(profile, busy = false) {
  if (busy && profile.is_current) return "in_progress";
  const status = profile.provenance?.ai_extraction?.status;
  if (EXTRACTION_STATUS_LABEL[status]) return status;
  // Older successful extraction versions predate the explicit status marker.
  if (profile.source === "ai_extracted" && profile.provenance?.workflow === "job_profile_extraction") {
    return "completed";
  }
  return profile.source === "ai_extracted" ? "pending" : null;
}

function sourceOriginLabel(profile) {
  const provenance = profile.provenance || {};
  const source = provenance.source || {};
  if (source.source_type === "linkedin" || provenance.linkedin_import?.source_type === "linkedin") {
    return "LinkedIn import";
  }
  if (provenance.creation_method === "pasted_external") return "Pasted external description";
  if (provenance.creation_method === "ai_generated") return "AI-generated description";
  if (["manual", "manually_created"].includes(provenance.creation_method)) return "HR-created description";
  if (profile.source === "hr_edited") return "HR edited";
  if (profile.source === "hr_created") return "HR-created description";
  return extractionStatus(profile) === "completed" ? "AI extracted" : "Description source recorded";
}

function briefDescription(value, limit = 360) {
  const text = (value || "").trim();
  return text.length > limit ? `${text.slice(0, limit).trimEnd()}…` : text;
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

function JobProfileCard({ profile, profileBusy, onApprove }) {
  const data = profile.profile_data || {};
  const requirements = Array.isArray(data.requirements) ? data.requirements : [];
  const summary = data.summary || "";
  const summaryPreview = summary.length > 220 ? `${summary.slice(0, 220).trimEnd()}…` : summary;
  let otherRequirementCount = 0;
  const visibleRequirements = requirements.filter((requirement) => {
    if (requirement.category === "must_have") return true;
    otherRequirementCount += 1;
    return otherRequirementCount <= 2;
  });
  const hiddenRequirements = requirements.filter(
    (requirement) => !visibleRequirements.includes(requirement)
  );
  const qualityReview = data.quality_review;
  const source = profile.provenance?.source;
  const fieldOrigins = profile.provenance?.field_origins || {};
  const originalListingText = profile.raw_input_snapshot?.original_listing_text;
  const qualitySummary = !qualityReview || qualityReview.status === "unavailable"
    ? "Not returned"
    : qualityReview.status === "partially_verified"
      ? "Partially verified"
      : qualityReview.findings?.length
        ? `${qualityReview.findings.length} review ${qualityReview.findings.length === 1 ? "note" : "notes"}`
        : "Review available";

  return (
    <div className={`profile-card ${profile.is_current ? "profile-card-current" : ""}`}>
      <div className="profile-card-head">
        <div>
          <strong>{data.title || "Extracted Job Profile"}</strong>
          <span className="muted-note">
            v{profile.version_number} · {sourceOriginLabel(profile)}
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

      {summary && (
        <div className="profile-summary">
          <p>{summaryPreview}</p>
          {summary.length > 220 && (
            <details className="profile-summary-details">
              <summary>Read full summary</summary>
              <p>{summary}</p>
            </details>
          )}
        </div>
      )}

      {source && (
        <details className="job-source-disclosure">
          <summary>Listing source · reviewed by HR</summary>
          {originalListingText && (
            <details className="original-listing-disclosure">
              <summary>View original listing text provided by HR</summary>
              <p dir="auto">{originalListingText}</p>
            </details>
          )}
          <p>{source.source_name} · Review recorded {source.reviewed_at ? new Date(source.reviewed_at).toLocaleString() : ""}</p>
          {source.source_url && <p>Source: <a href={source.source_url} target="_blank" rel="noreferrer">Open provided source link</a></p>}
          {source.application_url && <p>Apply: <a href={source.application_url} target="_blank" rel="noreferrer">Open provided application link</a></p>}
          {source.published_at && <p>Publication date supplied by HR: {source.published_at}</p>}
          <p>HERA has not checked whether either link works or whether the listing is still available.</p>
        </details>
      )}

      {Object.keys(fieldOrigins).length > 0 && (
        <details className="job-field-origin-disclosure">
          <summary>How these fields were prepared</summary>
          <ul>
            {Object.entries(fieldOrigins).map(([field, origin]) => (
              <li key={field}>
                <strong>{field.replaceAll("Text", "").replaceAll(/([A-Z])/g, " $1").trim()}:</strong>{" "}
                {FIELD_ORIGIN_LABEL[origin] || "Origin recorded"}
              </li>
            ))}
          </ul>
        </details>
      )}

      {requirements.length > 0 && (
        <>
          <h4>Requirements</h4>
          <div className="chips">
            {visibleRequirements.map((requirement) => (
              <span
                className={REQUIREMENT_TONE[requirement.category] || "chip"}
                key={requirement.key || requirement.text}
              >
                {requirement.text}
                {requirement.category ? ` · ${requirement.category.replaceAll("_", " ")}` : ""}
              </span>
            ))}
          </div>
          {hiddenRequirements.length > 0 && (
            <details className="profile-requirements-details">
              <summary>View all {requirements.length} requirements ({hiddenRequirements.length} more)</summary>
              <div className="chips">
                {hiddenRequirements.map((requirement) => (
                  <span
                    className={REQUIREMENT_TONE[requirement.category] || "chip"}
                    key={requirement.key || requirement.text}
                  >
                    {requirement.text}
                    {requirement.category ? ` · ${requirement.category.replaceAll("_", " ")}` : ""}
                  </span>
                ))}
              </div>
            </details>
          )}
        </>
      )}

      <details className="job-quality-disclosure">
        <summary>
          Job description quality check
          <span className="muted-note">{qualitySummary}</span>
        </summary>
        <section
          className="job-quality-review"
          aria-label="Job description quality review"
        >
          <h4>Job description quality check</h4>
          {!qualityReview || qualityReview.status === "unavailable" ? (
            <p>
              A quality review was not returned. Review the original description before
              approving this profile.
            </p>
          ) : (
            <>
              {qualityReview.status === "partially_verified" && (
                <p role="status">
                  Some findings were omitted because their quotes could not be verified
                  against the source description.
                </p>
              )}
              {qualityReview.findings?.length ? (
                <ul>
                  {qualityReview.findings.map((finding, index) => (
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
              ) : qualityReview.status === "partially_verified" ? (
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
      </details>
    </div>
  );
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
  const [extractionBusy, setExtractionBusy] = useState(false);
  const [originalDescriptionOpen, setOriginalDescriptionOpen] = useState(false);
  const [previousVersionsOpen, setPreviousVersionsOpen] = useState(false);
  const [editingProfileId, setEditingProfileId] = useState(null);
  const [editedRequirements, setEditedRequirements] = useState([]);
  const [editedSummary, setEditedSummary] = useState("");
  const [sectionImprovement, setSectionImprovement] = useState(null);
  const [sectionImprovementBusy, setSectionImprovementBusy] = useState(false);
  const [activationError, setActivationError] = useState("");
  const [publicationMessage, setPublicationMessage] = useState("");
  const [publicationBusy, setPublicationBusy] = useState(false);
  const extractionKey = React.useRef(null);

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
    setExtractionBusy(true);
    setProfileError("");
    extractionKey.current ||= globalThis.crypto?.randomUUID?.() || `extract-${Date.now()}-${Math.random()}`;
    try {
      await extractJobProfile(id, extractionKey.current);
      extractionKey.current = null;
      reloadProfiles();
    } catch (err) {
      setProfileError(
        err?.response?.data?.detail || "AI extraction failed. Please try again."
      );
    } finally {
      setExtractionBusy(false);
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

  const beginProfileEdit = (profile) => {
    setEditingProfileId(profile.id);
    setEditedRequirements((profile.profile_data?.requirements || []).map((item) => ({ ...item })));
    setEditedSummary(profile.profile_data?.summary || "");
    setSectionImprovement(null);
    setProfileError("");
  };

  const saveProfileEdits = async (profile) => {
    setProfileBusy(true);
    setProfileError("");
    try {
      await updateJobProfile(profile.id, {
        ...profile.profile_data,
        summary: editedSummary,
        requirements: editedRequirements,
      });
      setEditingProfileId(null);
      reloadProfiles();
    } catch (error) {
      setProfileError(error?.response?.data?.detail || "Could not save profile edits. Check each requirement and retry.");
    } finally {
      setProfileBusy(false);
    }
  };

  const suggestSectionImprovement = async (target) => {
    const selectedText = target.type === "summary" ? editedSummary : editedRequirements[target.index]?.text;
    if (!selectedText?.trim()) return;
    setProfileError("");
    setSectionImprovement(null);
    setSectionImprovementBusy(true);
    try {
      const result = await buildJobDescription({
        operation: "improve",
        title: job?.title,
        department: job?.department,
        section_name: target.label,
        selected_section: selectedText,
      });
      setSectionImprovement({ ...target, text: result.summary || result.requirements?.[0]?.text || "" });
    } catch (error) {
      setProfileError(error?.response?.data?.detail || "Could not prepare an AI suggestion for this section.");
    } finally {
      setSectionImprovementBusy(false);
    }
  };

  const applySectionImprovement = () => {
    if (!sectionImprovement) return;
    if (sectionImprovement.type === "summary") {
      setEditedSummary(sectionImprovement.text);
    } else {
      setEditedRequirements((current) => current.map((item, index) => index === sectionImprovement.index
        ? { ...item, text: sectionImprovement.text }
        : item));
    }
    setSectionImprovement(null);
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
    setActivationError("");
    try {
      const updated = await updateJob(job.id, { status: next });
      if (updated) setJob(updated);
    } catch (error) {
      setActivationError(error?.response?.data?.detail || "Vacancy status could not be updated.");
    }
  };

  const onPublishPublic = async () => {
    setPublicationBusy(true); setActivationError(""); setPublicationMessage("");
    try {
      const updated = await publishJob(job.id);
      setJob(updated);
      const link = `${window.location.origin}/careers/${updated.publicId}`;
      try { await navigator.clipboard.writeText(link); setPublicationMessage("Public job link copied."); }
      catch { setPublicationMessage(`Job published. Copy this link: ${link}`); }
    } catch (error) {
      setActivationError(error?.response?.data?.detail || "Could not publish this job.");
    } finally { setPublicationBusy(false); }
  };

  const onClosePublic = async () => {
    setPublicationBusy(true); setActivationError(""); setPublicationMessage("");
    try { setJob(await closePublicJob(job.id)); setPublicationMessage("Public listing closed."); }
    catch (error) { setActivationError(error?.response?.data?.detail || "Could not close this listing."); }
    finally { setPublicationBusy(false); }
  };

  const onCopyPublicLink = async () => {
    try { await navigator.clipboard.writeText(`${window.location.origin}/careers/${job.publicId}`); setPublicationMessage("Public job link copied."); }
    catch { setActivationError("Clipboard access is unavailable. Copy the link from the address preview."); }
  };

  const isActive = job?.status === "active";
  const publicStatus = job?.publicationStatus || "unpublished";

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
  const currentExtractionStatus = currentProfile
    ? extractionStatus(currentProfile, extractionBusy)
    : null;
  const currentSource = currentProfile?.provenance?.source || {};
  const companyName = currentSource.company_name || currentProfile?.provenance?.linkedin_import?.company_name;
  const originalDescription = currentProfile?.raw_input_snapshot?.original_listing_text || description;
  const roleOverview = currentExtractionStatus === "completed"
    ? currentProfile?.profile_data?.summary || briefDescription(description)
    : briefDescription(description);

  return (
    <section className="job-details-page">
      <div className="job-details-toolbar">
        <button className="btn btn-secondary job-details-back" onClick={() => navigate("/jobs")}>
          <ArrowLeft size={16} aria-hidden="true" /> Back to Jobs
        </button>
        <div className="job-details-actions">
          <Badge status={job.status} />
          <span className={`pill public-status public-status-${publicStatus}`}>Public: {publicStatus}</span>
          {publicStatus !== "published" && (
            <button className="primary" onClick={onPublishPublic} disabled={publicationBusy}>
              <Rocket size={16} aria-hidden="true" /> {publicStatus === "closed" ? "Republish job" : "Publish job publicly"}
            </button>
          )}
          {publicStatus === "published" && <>
            <button className="btn btn-secondary" onClick={onCopyPublicLink} disabled={publicationBusy}><Copy size={16} /> Copy public link</button>
            <button className="btn btn-secondary" onClick={onClosePublic} disabled={publicationBusy}><Ban size={16} /> Close public job</button>
          </>}
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
            <span>{companyName || "Company not provided"}</span>
            <span>{job.workMode || "Workplace type not provided"}</span>
            {job.experience && <span>{job.experience} experience</span>}
          </div>
        </div>
      </header>

      {activationError && <p className="form-error" role="alert">{activationError}</p>}
      {publicationMessage && <p role="status" className="muted-note">{publicationMessage} {job.publicId && <a href={`/careers/${job.publicId}`} target="_blank" rel="noreferrer">Open public listing</a>}</p>}

      {publicStatus === "published" && <JobDistributionPanel job={job} />}

      <div className="detail-grid job-details-grid">
        <div className="panel job-details-description-panel">
          <div className="job-details-section-heading">
            <div>
              <p className="eyebrow">ROLE OVERVIEW</p>
              <h3>Description</h3>
            </div>
          </div>
          {roleOverview ? (
            <p className="job-description job-details-description">{roleOverview}</p>
          ) : (
            <p className="job-details-empty-copy">No separate job description has been provided.</p>
          )}
          {currentExtractionStatus && (
            <p
              className={currentExtractionStatus === "failed" ? "form-error" : "muted-note"}
              role={currentExtractionStatus === "failed" ? "alert" : currentExtractionStatus === "in_progress" ? "status" : undefined}
            >
              {currentExtractionStatus === "failed"
                ? "AI extraction failed. The original listing is preserved; retry extraction or review the source manually."
                : currentExtractionStatus === "in_progress"
                  ? "AI is extracting structured responsibilities, qualifications, and skills…"
                  : currentExtractionStatus === "pending"
                    ? "AI extraction is pending. The source description has not been analyzed yet."
                    : "AI extraction completed. Review the structured criteria before approval."}
            </p>
          )}
          {originalDescription && (
            <details className="job-source-disclosure" onToggle={(event) => setOriginalDescriptionOpen(event.currentTarget.open)}>
              <summary>View full original job description</summary>
              {originalDescriptionOpen && <p dir="auto">{originalDescription}</p>}
            </details>
          )}
          {job.sourceFileName && (
            <div className="muted-note" role="status">
              Original file: {job.sourceFileName} · text extraction {job.sourceFileStatus || "pending"}
              {job.sourceFileError ? ` · ${job.sourceFileError}` : ""}
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => downloadJobSourceFile(job.id, job.sourceFileName)}
              >Download original file</button>
            </div>
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
            <p className="eyebrow">HERA JOB COPILOT</p>
            <h3>Job Profile</h3>
          </div>
          {!profilesLoading && !approvedProfile && draftProfile && (
            <span className="muted-note">Awaiting HR approval before screening can run.</span>
          )}
          {approvedProfile && (
            <Badge status="approved" />
          )}
        </div>

        <div className="job-profile-hero">
          <span className="job-profile-hero-mark">
            <Sparkles size={19} aria-hidden="true" />
          </span>
          <div className="job-profile-hero-copy">
            <strong>Turn this role into a reviewable profile</strong>
            <p>HERA organizes the job description into structured criteria. You decide what to approve.</p>
          </div>
          <button
            type="button"
            className="primary job-profile-hero-action"
            disabled={profileBusy || !job.description}
            onClick={onExtract}
            title={job.description ? "" : "No job description available to extract from."}
          >
            <Sparkles size={16} aria-hidden="true" />
            {currentProfile ? "Re-run AI extraction" : "Analyze with HERA"}
          </button>
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
            <div>
              <strong>No structured profile yet</strong>
              <p>Analyze the job description to create a draft. Review and approve it before screening.</p>
            </div>
          </div>
        ) : (
          <>
          {profiles.some((profile) => !profile.is_current) && (
            <details className="profile-versions-disclosure" onToggle={(event) => setPreviousVersionsOpen(event.currentTarget.open)}>
              <summary>Previous versions ({profiles.filter((profile) => !profile.is_current).length})</summary>
              <p>Older profile versions are shown below when expanded.</p>
            </details>
          )}
          {profiles
            .slice()
            .reverse()
            .map((profile) => {
              if (!profile.is_current && !previousVersionsOpen) return null;
              const data = profile.profile_data || {};
              const requirements = Array.isArray(data.requirements) ? data.requirements : [];
              const requirementGroups = groupProfileRequirements(requirements);
              let nonRequiredCount = 0;
              const visibleRequirements = requirements.filter((requirement) => {
                if (requirement.category === "must_have") return true;
                nonRequiredCount += 1;
                return nonRequiredCount <= 2;
              });
              const hiddenRequirements = requirements.filter(
                (requirement) => !visibleRequirements.includes(requirement)
              );
              const qualityReview = data.quality_review;
              const qualitySummary = !qualityReview || qualityReview.status === "unavailable"
                ? "Not returned"
                : qualityReview.status === "partially_verified"
                  ? "Partially verified"
                  : qualityReview.findings?.length
                    ? `${qualityReview.findings.length} review ${qualityReview.findings.length === 1 ? "note" : "notes"}`
                    : "Review available";
              const needsConfirmation = Array.isArray(profile.raw_input_snapshot?.needs_confirmation)
                ? profile.raw_input_snapshot.needs_confirmation
                : [];
              const fieldOrigins = profile.provenance?.field_origins || {};
              return (
                <div className="profile-card" key={profile.id}>
                  <div className="profile-card-head">
                    <div>
                      <strong>{data.title || "Extracted Job Profile"}</strong>
                      <span className="muted-note">
                        v{profile.version_number} · {sourceOriginLabel(profile)}
                        {profile.is_current ? " · current" : ""}
                      </span>
                    </div>
                    <div className="profile-card-actions">
                      <Badge status={profile.status} />
                      {profile.status === "draft" && (
                        <>
                          {editingProfileId !== profile.id && (
                            <button type="button" className="btn btn-secondary" onClick={() => beginProfileEdit(profile)}>Review / edit</button>
                          )}
                          <button
                            className="primary"
                            disabled={profileBusy || editingProfileId === profile.id}
                            onClick={() => onApprove(profile.id)}
                          >
                            <FileCheck2 size={16} /> Approve
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <p className="muted-note">
                    Description origin: {sourceOriginLabel(profile)}
                    {extractionStatus(profile, extractionBusy) && ` · ${EXTRACTION_STATUS_LABEL[extractionStatus(profile, extractionBusy)]}`}
                    {profile.status === "draft" && " · HR approval is required before screening."}
                  </p>

                  {profile.provenance?.source && (
                    <details className="job-source-disclosure">
                      <summary>Listing source · reviewed by HR</summary>
                      <p>{profile.provenance.source.source_name || sourceOriginLabel(profile)} · Review recorded {profile.provenance.source.reviewed_at ? new Date(profile.provenance.source.reviewed_at).toLocaleString() : ""}</p>
                      {profile.provenance.source.source_url && <p>Source: <a href={profile.provenance.source.source_url} target="_blank" rel="noreferrer">Open provided source link</a></p>}
                      {profile.provenance.source.application_url && <p>Apply: <a href={profile.provenance.source.application_url} target="_blank" rel="noreferrer">Open provided application link</a></p>}
                      <p>HERA has not checked whether either link works or whether the listing is still available.</p>
                    </details>
                  )}
                  {Object.keys(fieldOrigins).length > 0 && (
                    <details className="job-field-origin-disclosure">
                      <summary>How these fields were prepared</summary>
                      <ul>
                        {Object.entries(fieldOrigins).map(([field, origin]) => (
                          <li key={field}>
                            <strong>{field.replaceAll("Text", "").replaceAll(/([A-Z])/g, " $1").trim()}:</strong>{" "}
                            {FIELD_ORIGIN_LABEL[origin] || "Origin recorded"}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}

                  {needsConfirmation.length > 0 && (
                    <aside className="hera-note" role="note">
                      <strong>Confirm these items before approving</strong>
                      <ul>{needsConfirmation.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
                    </aside>
                  )}

                  {profile.status === "draft" && editingProfileId === profile.id ? (
                    <div className="profile-summary-editor">
                      <label>
                        Job overview
                        <textarea aria-label="Job overview" rows="4" value={editedSummary}
                          onChange={(event) => setEditedSummary(event.target.value)} />
                      </label>
                      <button type="button" className="btn btn-secondary" disabled={sectionImprovementBusy || !editedSummary.trim()}
                        onClick={() => suggestSectionImprovement({ type: "summary", label: "Job overview" })}>
                        {sectionImprovementBusy ? "Preparing suggestion…" : "Improve overview with AI"}
                      </button>
                      {sectionImprovement?.type === "summary" && (
                        <div className="hera-note" role="region" aria-label="AI overview suggestion">
                          <p>{sectionImprovement.text}</p>
                          <button type="button" className="primary" onClick={applySectionImprovement}>Use suggestion</button>
                          <button type="button" className="btn btn-secondary" onClick={() => setSectionImprovement(null)}>Discard</button>
                        </div>
                      )}
                    </div>
                  ) : data.summary ? (
                    <div className="profile-summary">
                      <p className="muted-note">{briefDescription(data.summary, 220)}</p>
                      {data.summary.length > 220 && (
                        <details className="profile-summary-details">
                          <summary>Read full summary</summary>
                          <p>{data.summary}</p>
                        </details>
                      )}
                    </div>
                  ) : null}

                  {data.coverage && (
                    <section aria-label="Requirement category coverage">
                      <h4>Coverage</h4>
                      <ul>
                        {Object.entries(data.coverage).map(([dimension, coverage]) => (
                          <li key={dimension}>{dimension.replaceAll("_", " ")}: {coverage}</li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {data.conflicts?.length > 0 && (
                    <section className="job-quality-review" aria-label="Conflicting source details">
                      <h4>Conflicting source details · review required</h4>
                      <ul>
                        {data.conflicts.map((conflict, index) => (
                          <li key={`${conflict.field}-${index}`}>
                            <strong>{conflict.field.replaceAll("_", " ")}</strong>
                            <ul>{conflict.values.map((value, valueIndex) => (
                              <li key={`${value.source}-${valueIndex}`}>{value.value} · {value.source}</li>
                            ))}</ul>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {profile.status === "draft" && editingProfileId === profile.id && (
                    <section className="profile-requirement-editor" aria-label="Edit proposed requirements">
                      <h4>Review proposed job description</h4>
                      {groupProfileRequirements(editedRequirements).map((group) => (
                      <section key={group.key} aria-label={`Edit ${group.title.toLowerCase()}`}>
                      <h5>{group.title}</h5>
                      {group.items.map(({ requirement, index }) => (
                        <div className="profile-requirement-row" key={`${requirement.key || "new"}-${index}`}>
                          <input
                            aria-label={`Requirement ${index + 1}`}
                            value={requirement.text || ""}
                            onChange={(event) => setEditedRequirements((current) => current.map((item, row) => row === index ? { ...item, text: event.target.value } : item))}
                          />
                          <select
                            aria-label={`Requirement ${index + 1} category`}
                            value={requirement.category || "must_have"}
                            onChange={(event) => setEditedRequirements((current) => current.map((item, row) => row === index ? { ...item, category: event.target.value } : item))}
                          >
                            <option value="must_have">Required</option>
                            <option value="important">Important</option>
                            <option value="nice_to_have">Preferred</option>
                          </select>
                          <select
                            aria-label={`Requirement ${index + 1} type`}
                            value={requirement.dimension || "skill"}
                            onChange={(event) => setEditedRequirements((current) => current.map((item, row) => row === index ? { ...item, dimension: event.target.value } : item))}
                          >
                            {["skill", "technical_skill", "soft_skill", "experience", "education", "certification", "responsibility"].map((dimension) => (
                              <option key={dimension} value={dimension}>{dimension}</option>
                            ))}
                          </select>
                          <button type="button" className="btn btn-secondary" onClick={() => setEditedRequirements((current) => current.filter((_, row) => row !== index))}>Remove</button>
                          <button type="button" className="btn btn-secondary" disabled={sectionImprovementBusy || !requirement.text?.trim()}
                            onClick={() => suggestSectionImprovement({ type: "requirement", index, label: `${group.title} item` })}>
                            {sectionImprovementBusy ? "Improving…" : "Improve with AI"}
                          </button>
                          {sectionImprovement?.type === "requirement" && sectionImprovement.index === index && (
                            <div className="hera-note" role="region" aria-label={`AI suggestion for ${group.title.toLowerCase()}`}>
                              <p>{sectionImprovement.text}</p>
                              <button type="button" className="primary" onClick={applySectionImprovement}>Use suggestion</button>
                              <button type="button" className="btn btn-secondary" onClick={() => setSectionImprovement(null)}>Discard</button>
                            </div>
                          )}
                        </div>
                      ))}
                      </section>
                      ))}
                      <div className="profile-card-actions">
                        <button type="button" className="btn btn-secondary" onClick={() => setEditedRequirements((current) => [...current, { text: "", category: "must_have", dimension: "skill" }])}>Add requirement</button>
                        <button type="button" className="btn btn-secondary" onClick={() => setEditedRequirements((current) => [...current, { text: "", category: "important", dimension: "responsibility" }])}>Add responsibility</button>
                        <button type="button" className="btn btn-secondary" onClick={() => setEditedRequirements((current) => [...current, { text: "", category: "important", dimension: "experience" }])}>Add qualification</button>
                        <button type="button" className="btn btn-secondary" onClick={() => setEditedRequirements((current) => [...current, { text: "", category: "important", dimension: "technical_skill" }])}>Add skill</button>
                        <button type="button" className="primary" disabled={profileBusy} onClick={() => saveProfileEdits(profile)}>Save review</button>
                        <button type="button" className="btn btn-secondary" onClick={() => setEditingProfileId(null)}>Cancel</button>
                      </div>
                    </section>
                  )}

                  {requirements.length > 0 && (
                    <>
                      <h4>Job description criteria</h4>
                      {requirementGroups.map((group) => {
                        const visibleItems = group.items.filter(({ requirement }) => visibleRequirements.includes(requirement));
                        return visibleItems.length > 0 && (
                      <section key={group.key} aria-label={group.title}>
                      <h5>{group.title}</h5>
                      <div className="chips">
                        {visibleItems.map(({ requirement: req }) => (
                          <span className={REQUIREMENT_TONE[req.category] || "chip"} key={req.key || req.text} title={req.source_quote ? `Source: ${req.source} — ${req.source_quote}` : "Source not verified; recruiter review required"}>
                            {req.text}
                            {req.category ? ` · ${req.category.replaceAll("_", " ")}` : ""}
                            {req.evidence_status === "uncertain" ? " · source uncertain" : ""}
                          </span>
                        ))}
                      </div>
                      </section>
                      );
                      })}
                      {hiddenRequirements.length > 0 && (
                        <details className="profile-requirements-details">
                          <summary>View all {requirements.length} requirements ({hiddenRequirements.length} more)</summary>
                          <div className="chips">
                            {hiddenRequirements.map((req) => (
                              <span className={REQUIREMENT_TONE[req.category] || "chip"} key={req.key || req.text}>
                                {req.text}{req.category ? ` · ${req.category.replaceAll("_", " ")}` : ""}
                              </span>
                            ))}
                          </div>
                        </details>
                      )}
                    </>
                  )}

                  <details className="job-quality-disclosure">
                    <summary>
                      Job description quality check
                      <span className="muted-note">{qualitySummary}</span>
                    </summary>
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
                  </details>

                </div>
              );
            })}
          </>
        )}
        <div className="profile-card-actions footer-actions job-profile-footer">
          <button
            type="button"
            className="btn-secondary"
            disabled={profileBusy || (!job.description && !job.sourceFileName && !job.experience && !job.requiredSkills?.length && !job.requirements?.length)}
            onClick={onExtract}
            title={job.description || job.sourceFileName ? "" : "Add description text or supported job specifications first."}
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

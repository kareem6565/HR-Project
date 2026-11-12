import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  createJob,
  getJobById,
  suggestJobDraft,
  uploadJobSourceFile,
  updateJob,
} from "../../services/jobService";
import {
  buildJobDescription,
  createJobProfile,
  extractJobProfile,
  getLinkedInJobImport,
  startLinkedInJobImport,
} from "../../services/jobProfileService";
import LoadingSpinner from "../../components/common/LoadingSpinner";

const EMPTY_JOB = {
  title: "",
  department: "",
  location: "",
  workMode: "",
  type: "Full-time",
  experience: "",
  status: "draft",
  description: "",
  requirementsText: "",
  requiredSkillsText: "",
  sourceName: "",
  sourceUrl: "",
  sourceCompany: "",
  sourceSeniority: "",
  publishedAt: "",
  applicationUrl: "",
  sourceReviewConfirmed: false,
};

// The employment-type select preselects Full-time so an untouched default reads
// as "not chosen yet" to the HERA auto-fill.
const DEFAULT_JOB_TYPE = "Full-time";

// Used for both /jobs/new (create) and /jobs/:id/edit (edit) — the only
// difference is whether we preload an existing job and call updateJob
// instead of createJob on submit.
export default function JobForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();

  const [job, setJob] = useState(EMPTY_JOB);
  const jobRef = useRef(job);
  const userEditedFields = useRef(new Set());
  const heraSuggestedFields = useRef(new Set());
  const sourceImportId = useRef(globalThis.crypto?.randomUUID?.() || `source-${Date.now()}`);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [jobFile, setJobFile] = useState(null);
  const [saveError, setSaveError] = useState("");
  const idempotencyKey = useRef(
    globalThis.crypto?.randomUUID?.() || `vacancy-${Date.now()}-${Math.random()}`
  );
  const extractionKey = useRef(null);

  // Advisory HERA auto-fill ("Fill with HERA") doesn't persist anything; it
  // only pre-fills empty fields, all of which stay fully editable.
  const [fillStatus, setFillStatus] = useState("idle"); // idle|analyzing|ready|incomplete|error
  const [fillError, setFillError] = useState("");
  const [aiFields, setAiFields] = useState(() => new Set());
  const [creationMethod, setCreationMethod] = useState("manual");
  const [pastedDescription, setPastedDescription] = useState("");
  const [builderStatus, setBuilderStatus] = useState("idle");
  const [builderError, setBuilderError] = useState("");
  const [profileDraft, setProfileDraft] = useState(null);
  const [builderIndustry, setBuilderIndustry] = useState("");
  const [improvementProposal, setImprovementProposal] = useState(null);
  const [improvementStatus, setImprovementStatus] = useState("idle");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [linkedinImport, setLinkedinImport] = useState(null);
  const [linkedinImportStatus, setLinkedinImportStatus] = useState("idle");
  const [linkedinImportError, setLinkedinImportError] = useState("");

  // Saved identity: a created (or edited) job keeps the form page open so the
  // next step ("Analyze with HERA", which opens the job review) is explicit.
  const [savedId, setSavedId] = useState(isEdit ? id : null);
  const [savedMessage, setSavedMessage] = useState("");
  const [analyzStatus, setAnalyzStatus] = useState("idle"); // idle|running|error
  const [analyzError, setAnalyzError] = useState("");

  useEffect(() => {
    if (!isEdit) return;
    getJobById(id).then((data) => {
      if (!data) {
        setLoading(false);
        return;
      }
      const loadedJob = {
        ...EMPTY_JOB,
        title: data.title || "",
        department: data.department || "",
        location: data.location || "",
        workMode: data.workMode || "",
        type: data.type || DEFAULT_JOB_TYPE,
        experience: data.experience || "",
        status: data.status || "draft",
        description: data.description || "",
        requirementsText: (data.requirements || []).join("\n"),
        requiredSkillsText: (data.requiredSkills || []).join(", "),
        sourceFileName: data.sourceFileName || "",
        sourceFileStatus: data.sourceFileStatus || "",
        sourceFileError: data.sourceFileError || "",
      };
      jobRef.current = loadedJob;
      setJob(loadedJob);
      setLoading(false);
    });
  }, [id, isEdit]);

  function isFieldEmpty(name, currentJob = jobRef.current) {
    switch (name) {
      case "title":
        return !currentJob.title;
      case "department":
        return !currentJob.department;
      case "location":
        return !currentJob.location;
      case "type":
        return (
          !currentJob.type ||
          (!isEdit &&
            currentJob.type === DEFAULT_JOB_TYPE &&
            !userEditedFields.current.has(name))
        );
      case "experience":
        return !currentJob.experience;
      case "requirementsText":
        return !currentJob.requirementsText;
      case "requiredSkillsText":
        return !currentJob.requiredSkillsText;
      default:
        return false;
    }
  }

  const onChange = (e) => {
    const name = e.target.name;
    const nextJob = { ...jobRef.current, [name]: e.target.value };
    jobRef.current = nextJob;
    setJob(nextJob);
    userEditedFields.current.add(name);
    if (aiFields.has(name)) {
      const next = new Set(aiFields);
      next.delete(name);
      setAiFields(next);
    }
  };

  const onFill = async () => {
    const fields = [
      "title",
      "department",
      "location",
      "type",
      "experience",
      "requirementsText",
      "requiredSkillsText",
    ];
    const currentJob = jobRef.current;
    if (!currentJob.description) {
      setFillStatus("incomplete");
      return;
    }
    if (!fields.some((name) => isFieldEmpty(name, currentJob))) {
      setFillStatus("no-fields");
      return;
    }
    setFillStatus("analyzing");
    setFillError("");

    try {
      const suggestion = await suggestJobDraft(currentJob.description);
      const latestJob = jobRef.current;
      if (latestJob.description !== currentJob.description) {
        setFillStatus("changed");
        return;
      }
      const applied = {};
      const appliedNames = [];
      if (isFieldEmpty("title", latestJob) && suggestion.title) {
        applied.title = suggestion.title;
        appliedNames.push("title");
      }
      if (isFieldEmpty("department", latestJob) && suggestion.department) {
        applied.department = suggestion.department;
        appliedNames.push("department");
      }
      if (isFieldEmpty("location", latestJob) && suggestion.location) {
        applied.location = suggestion.location;
        appliedNames.push("location");
      }
      if (isFieldEmpty("type", latestJob) && suggestion.type) {
        applied.type = suggestion.type;
        appliedNames.push("type");
      }
      if (isFieldEmpty("experience", latestJob) && suggestion.experience) {
        applied.experience = suggestion.experience;
        appliedNames.push("experience");
      }
      if (isFieldEmpty("requirementsText", latestJob) && suggestion.requirements.length) {
        applied.requirementsText = suggestion.requirements.join("\n");
        appliedNames.push("requirementsText");
      }
      if (isFieldEmpty("requiredSkillsText", latestJob) && suggestion.requiredSkills.length) {
        applied.requiredSkillsText = suggestion.requiredSkills.join(", ");
        appliedNames.push("requiredSkillsText");
      }

      if (!appliedNames.length) {
        setFillStatus(fields.some((name) => isFieldEmpty(name, latestJob)) ? "incomplete" : "no-fields");
        return;
      }
      const nextJob = { ...latestJob, ...applied };
      jobRef.current = nextJob;
      setJob(nextJob);
      setAiFields(
        (current) => new Set([...Array.from(current), ...appliedNames])
      );
      appliedNames.forEach((field) => heraSuggestedFields.current.add(field));
      setFillStatus("ready");
    } catch {
      setFillStatus("error");
      setFillError("HERA could not suggest job fields. Your entries are unchanged. Try again.");
    }
  };

  const runDescriptionBuilder = async (operation) => {
    const current = jobRef.current;
    if (operation === "generate" && (!current.title.trim() || !current.department.trim())) {
      setBuilderError("Enter a job title and department before generating a description.");
      return;
    }
    if (operation === "parse" && !pastedDescription.trim()) {
      setBuilderError("Paste the existing job description first.");
      return;
    }
    if (
      (profileDraft || current.description.trim() || current.requirementsText.trim() || current.requiredSkillsText.trim()) &&
      !window.confirm("Replace the current job description and structured draft with this result?")
    ) return;

    setBuilderStatus("running");
    setBuilderError("");
    try {
      const result = await buildJobDescription({
        operation,
        title: current.title || undefined,
        department: current.department || undefined,
        seniority: current.experience || undefined,
        employment_type: current.type || undefined,
        work_mode: current.workMode || undefined,
        location: current.location || undefined,
        industry: builderIndustry || undefined,
        role_context: operation === "generate" ? current.description || undefined : undefined,
        additional_requirements: operation === "generate"
          ? [
              current.requirementsText ? `Role notes:\n${current.requirementsText}` : "",
              current.requiredSkillsText ? `Required skills:\n${current.requiredSkillsText}` : "",
            ].filter(Boolean).join("\n") || undefined
          : undefined,
        experience_expectations: operation === "generate" ? current.experience || undefined : undefined,
        source_text: operation === "parse" ? pastedDescription : undefined,
      });
      const draft = {
        schema_version: result.schema_version,
        title: result.title,
        summary: result.summary || "",
        requirements: (result.requirements || []).map((item) => ({
          text: item.text,
          category: item.category || "important",
          dimension: item.dimension || "skill",
          source: item.source,
          source_quote: item.source_quote,
        })),
        needs_confirmation: result.needs_confirmation || [],
        creation_method: result.creation_method,
      };
      setProfileDraft(draft);
      setCreationMethod(operation === "parse" ? "pasted_external" : "ai_generated");
      const nextJob = {
        ...current,
        title: current.title || draft.title,
        description: draft.summary || (operation === "parse" ? pastedDescription : current.description),
        requirementsText: draft.requirements
          .filter((item) => !["skill", "technical_skill", "soft_skill"].includes(item.dimension))
          .map((item) => item.text).join("\n"),
        requiredSkillsText: draft.requirements
          .filter((item) => ["skill", "technical_skill"].includes(item.dimension) && item.category === "must_have")
          .map((item) => item.text).join(", "),
      };
      jobRef.current = nextJob;
      setJob(nextJob);
      setBuilderStatus("ready");
    } catch (error) {
      setBuilderStatus("error");
      setBuilderError(
        error?.response?.data?.detail || error?.message ||
        "HERA could not prepare the job description. Your current entries are unchanged."
      );
    }
  };

  const updateProfileRequirement = (index, updates) => {
    setProfileDraft((current) => ({
      ...current,
      requirements: current.requirements.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...updates } : item
      ),
    }));
  };

  const requestSectionImprovement = async (target) => {
    const selectedText = target.type === "summary"
      ? profileDraft?.summary
      : profileDraft?.requirements?.[target.index]?.text;
    if (!selectedText?.trim()) return;
    setImprovementStatus("running");
    setImprovementProposal(null);
    setBuilderError("");
    try {
      const result = await buildJobDescription({
        operation: "improve",
        title: jobRef.current.title,
        department: jobRef.current.department,
        section_name: target.label,
        selected_section: selectedText,
      });
      const improvedText = result.summary || result.requirements?.[0]?.text || "";
      setImprovementProposal({ ...target, text: improvedText });
      setImprovementStatus("ready");
    } catch (error) {
      setImprovementStatus("error");
      setBuilderError(error?.response?.data?.detail || error?.message || `HERA could not improve ${target.label.toLowerCase()}.`);
    }
  };

  const useImprovementProposal = () => {
    if (!improvementProposal) return;
    if (improvementProposal.type === "summary") {
      setProfileDraft((current) => ({ ...current, summary: improvementProposal.text }));
      const nextJob = { ...jobRef.current, description: improvementProposal.text };
      jobRef.current = nextJob;
      setJob(nextJob);
    } else {
      updateProfileRequirement(improvementProposal.index, { text: improvementProposal.text });
    }
    setImprovementProposal(null);
  };

  const applyLinkedInImport = (record) => {
    const result = record?.result;
    if (!result?.title || !result?.description) {
      setLinkedinImportStatus("failed");
      setLinkedinImportError("The public listing did not include a title and description. You can paste the description manually.");
      return;
    }
    const workplace = (result.workplace_type || "").toLowerCase();
    const nextJob = {
      ...jobRef.current,
      title: result.title,
      location: result.location || "",
      type: result.employment_type || "",
      workMode: ({ remote: "remote", hybrid: "hybrid", "on-site": "onsite", onsite: "onsite" })[workplace] || "",
      description: result.description,
      sourceName: "LinkedIn",
      sourceUrl: record.source_url,
      sourceCompany: result.company_name || "",
      sourceSeniority: result.seniority_level || "",
      sourceReviewConfirmed: false,
    };
    jobRef.current = nextJob;
    setJob(nextJob);
    setPastedDescription(result.description);
    setCreationMethod("pasted_external");
    sourceImportId.current = record.id;
    setProfileDraft({
      schema_version: "1.4",
      title: result.title,
      // The full listing belongs in the source snapshot and job description.
      // Keep the structured profile summary within its 4,000-character contract.
      summary: result.description.length > 4000 ? "" : result.description,
      requirements: [],
      needs_confirmation: [
        "Responsibilities and qualifications have not been structured yet.",
        ...(result.description.length > 4000
          ? ["Add a concise overview; the full original listing is retained separately."]
          : []),
      ],
    });
    setLinkedinImport(record);
    setLinkedinImportStatus("succeeded");
    setLinkedinImportError("");
  };

  const importFromLinkedIn = async () => {
    if (!linkedinUrl.trim()) {
      setLinkedinImportError("Paste a public LinkedIn job URL first.");
      return;
    }
    setLinkedinImportStatus("running");
    setLinkedinImportError("");
    try {
      let record = await startLinkedInJobImport(linkedinUrl.trim());
      setLinkedinImport(record);
      for (let attempt = 0; ["queued", "running"].includes(record.status) && attempt < 150; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        record = await getLinkedInJobImport(record.id);
        setLinkedinImport(record);
        if (record.error_message) setLinkedinImportError(record.error_message);
      }
      if (record.status === "succeeded") {
        applyLinkedInImport(record);
      } else if (record.status === "failed") {
        setLinkedinImportStatus("failed");
        setLinkedinImportError(record.error_message || "LinkedIn import failed. Paste the description manually to continue.");
      } else {
        setLinkedinImportStatus("running");
        setLinkedinImportError("This import is still running. Click Import again to resume checking it without starting another Actor run.");
      }
    } catch (error) {
      setLinkedinImportStatus("failed");
      setLinkedinImportError(error?.response?.data?.detail || "Could not import this job. You can paste the description manually.");
    }
  };

  const requirementSections = [
    { key: "responsibilities", title: "Responsibilities", dimensions: ["responsibility"], defaultDimension: "responsibility" },
    { key: "qualifications", title: "Qualifications", dimensions: ["experience", "education", "certification"], defaultDimension: "experience" },
    { key: "skills", title: "Skills", dimensions: ["skill", "technical_skill", "soft_skill"], defaultDimension: "technical_skill" },
    { key: "other", title: "Other criteria", dimensions: [], defaultDimension: "skill" },
  ];

  const startManualProfileDraft = () => {
    const current = jobRef.current;
    setProfileDraft({
      schema_version: "1.4",
      title: current.title,
      summary: current.description,
      requirements: [
        ...current.requiredSkillsText.split(",").map((text) => text.trim()).filter(Boolean)
          .map((text) => ({ text, category: "must_have", dimension: "technical_skill" })),
        ...current.requirementsText.split("\n").map((text) => text.trim()).filter(Boolean)
          .map((text) => ({ text, category: "important", dimension: "skill" })),
      ],
      needs_confirmation: [],
      creation_method: "manually_created",
    });
    setCreationMethod("manual");
  };

  const selectCreationMethod = (method) => {
    if (profileDraft && !window.confirm("Discard the current structured draft and switch methods?")) {
      return;
    }
    setCreationMethod(method);
    setProfileDraft(null);
    setLinkedinImport(null);
    setLinkedinImportStatus("idle");
    setLinkedinImportError("");
    setBuilderError("");
    setImprovementProposal("");
  };

  const onSubmit = async (e) => {
    e.preventDefault();

    setSaveError("");
    const hasSourceDetails = Boolean(
      job.sourceName || job.sourceUrl || job.applicationUrl || job.publishedAt
    );
    if (hasSourceDetails && !job.sourceReviewConfirmed) {
      setSaveError("Confirm that you reviewed the supplied source details before saving them.");
      return;
    }
    if (!job.description.trim() && !profileDraft && !jobFile && !job.sourceFileName) {
      setSaveError("Add a job description or upload a PDF/DOCX description file before saving.");

      return;
    }
    setSaving(true);

    const payload = {
      title: job.title,
      department: job.department,
      location: job.location,
      type: job.type,
      workMode: job.workMode,
      experience: job.experience,
      status: "draft",
      description: profileDraft?.summary || job.description,
      requirements: job.requirementsText
        .split("\n")
        .map((r) => r.trim())
        .filter(Boolean),
      requiredSkills: job.requiredSkillsText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    const linkedInImportConfirmed = Boolean(
      linkedinImport && linkedinImportStatus === "succeeded" && creationMethod === "pasted_external"
    );

    let targetId = null;
    try {

      if (isEdit || savedId) {
        targetId = savedId || id;
        await updateJob(targetId, payload);
        if (jobFile) {
          const uploaded = await uploadJobSourceFile(targetId, jobFile);
          setJob((current) => ({
            ...current,
            sourceFileName: uploaded.sourceFileName,
            sourceFileStatus: uploaded.sourceFileStatus,
            sourceFileError: uploaded.sourceFileError,
          }));
          if (uploaded.sourceFileStatus === "failed") {
            setSaveError(`File saved, but text extraction failed: ${uploaded.sourceFileError || "Try another PDF/DOCX or correct the source."}`);
            setSaving(false);
            return;
          }
        }
        setSavedId(targetId);
        setSavedMessage("Job updated. Analyze it with HERA to build or refresh its profile.");
      } else {
        const created = await createJob(
          payload,
          linkedInImportConfirmed ? linkedinImport.id : idempotencyKey.current
        );
        targetId = created?.id;
        setSavedId(created?.id);
        if (jobFile && created?.id) {
          const uploaded = await uploadJobSourceFile(created.id, jobFile);
          setJob((current) => ({
            ...current,
            sourceFileName: uploaded.sourceFileName,
            sourceFileStatus: uploaded.sourceFileStatus,
            sourceFileError: uploaded.sourceFileError,
          }));
          if (uploaded.sourceFileStatus === "failed") {
            setSaveError(`Vacancy and file were saved, but text extraction failed: ${uploaded.sourceFileError || "Try another PDF/DOCX or correct the source."}`);
            setSaving(false);
            return;
          }
        }
        setSavedMessage("Job saved as a draft. Analyze it with HERA to build its profile.");
      }
      if (profileDraft && targetId) {
        const profileCreationMethod = creationMethod === "manual" ? "manually_created" : creationMethod;
        await createJobProfile(targetId, {
          status: "draft",
          source: creationMethod === "manual" ? "hr_created" : "ai_extracted",
          creation_method: profileCreationMethod,
          source_original_text: creationMethod === "pasted_external" ? pastedDescription : undefined,
          source_original_listing_text: creationMethod === "pasted_external" ? pastedDescription : undefined,
          source_metadata: hasSourceDetails ? {
            source_name: job.sourceName,
            source_url: job.sourceUrl || undefined,
            published_at: job.publishedAt || undefined,
            application_url: job.applicationUrl || undefined,
            source_import_id: sourceImportId.current,
            source_type: linkedInImportConfirmed ? "linkedin" : undefined,
            company_name: job.sourceCompany || undefined,
            seniority_level: job.sourceSeniority || undefined,
            review_confirmed: true,
          } : undefined,
          needs_confirmation: profileDraft.needs_confirmation,
          raw_input_snapshot: {
            creation_method: profileCreationMethod,
            needs_confirmation: profileDraft.needs_confirmation,
            ...(linkedInImportConfirmed ? { source_type: "linkedin", import_id: linkedinImport.id } : {}),
          },
          profile_data: {
            schema_version: profileDraft.schema_version || "1.3",
            title: job.title,
            summary:
              profileDraft.summary ??
              (job.description.length <= 4000 ? job.description : ""),
            requirements: profileDraft.requirements
              .filter((item) => item.text.trim())
              .map(({ text, category, dimension, source, source_quote }) => ({
                text: text.trim(),
                category,
                dimension,
                ...(creationMethod === "pasted_external" && source_quote && source
                  ? { source, source_quote }
                  : {}),
              })),
          },
        });
        navigate(`/jobs/${targetId}`);
      }
    } catch (error) {
      setSaveError(
        error?.response?.data?.detail ||
          error?.message ||
          "The vacancy could not be saved. Your form entries and selected file are still here; retry when ready."
      );

    } finally {
      setSaving(false);
    }
  };

  const onAnalyze = async () => {
    const targetId = savedId;
    if (!targetId) return;
    setAnalyzStatus("running");
    setAnalyzError("");
    extractionKey.current ||= globalThis.crypto?.randomUUID?.() || `extract-${Date.now()}-${Math.random()}`;
    try {
      await extractJobProfile(targetId, extractionKey.current);
      extractionKey.current = null;
      navigate(`/jobs/${targetId}`);
    } catch (error) {
      setAnalyzStatus("error");
      setAnalyzError(
        error?.message || "HERA could not analyse this job. It needs a description."
      );
    }
  };

  if (loading) return <LoadingSpinner label="Loading job..." />;

  const fillButtonLabel =
    fillStatus === "analyzing"
      ? "HERA is reading the description..."
      : "Suggest fields with HERA";

  return (
    <section className="content-grid job-form-grid">
      <div className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">JOB {isEdit ? "EDIT" : "SETUP"}</p>
            <h3>{isEdit ? "Edit Job" : "Create New Job"}</h3>
          </div>
        </div>

        {!isEdit && <div className="job-form-step-heading">
          <span className="job-form-step-number" aria-hidden="true">1</span>
          <div><h4>Choose how to start</h4><p>Select one approach. You can review and edit everything before saving.</p></div>
        </div>}
        <div className="job-creation-methods" role="group" aria-label="Job description creation method">
          {!isEdit && <button type="button" className="secondary"
            aria-pressed={creationMethod === "linkedin_import"}
            onClick={() => selectCreationMethod("linkedin_import")}>
            <span className="job-method-title">Import from LinkedIn</span>
            <span className="job-method-description">Start with a public job listing</span>
          </button>}
          <button type="button" className={creationMethod === "ai_generated" ? "primary" : "secondary"}
            aria-pressed={creationMethod === "ai_generated"} onClick={() => selectCreationMethod("ai_generated")}>
            <span className="job-method-title">Generate with AI</span>
            <span className="job-method-description">Build a first draft from role details</span>
          </button>
          <button type="button" className={creationMethod === "pasted_external" ? "primary" : "secondary"}
            aria-pressed={creationMethod === "pasted_external"} onClick={() => selectCreationMethod("pasted_external")}>
            <span className="job-method-title">Paste existing</span>
            <span className="job-method-description">Organize a description you already have</span>
          </button>
          <button type="button" className={creationMethod === "manual" ? "primary" : "secondary"}
            aria-pressed={creationMethod === "manual"} onClick={() => selectCreationMethod("manual")}>
            <span className="job-method-title">Create manually</span>
            <span className="job-method-description">Write and organize it yourself</span>
          </button>
        </div>

        {!isEdit && <div className="job-form-step-heading job-form-details-heading">
          <span className="job-form-step-number" aria-hidden="true">2</span>
          <div><h4>Job details</h4><p>Start with the essentials. HERA keeps this as a draft for your review.</p></div>
        </div>}

        {creationMethod === "linkedin_import" && (
          <div className="job-paste-source">
            <label htmlFor="linkedin-job-url">Public LinkedIn job URL</label>
            <input id="linkedin-job-url" type="url" value={linkedinUrl}
              onChange={(event) => setLinkedinUrl(event.target.value)}
              placeholder="https://www.linkedin.com/jobs/view/1234567890/" />
            <button type="button" className="primary" onClick={importFromLinkedIn}
              disabled={linkedinImportStatus === "running" && !linkedinImportError}>
              {linkedinImportStatus === "running" ? "Importing or checking status…" : "Import job"}
            </button>
            {linkedinImportStatus === "running" && <p className="hera-note" role="status">
              HERA is retrieving public job details. Nothing is saved, approved, or published until you review and save the draft.
            </p>}
            {linkedinImportError && <p className="hera-note hera-error" role="alert">{linkedinImportError}</p>}
          </div>
        )}

        {creationMethod === "ai_generated" && (
          <div className="hera-toolbar">
            <label>
              Industry (optional)
              <input value={builderIndustry} onChange={(event) => setBuilderIndustry(event.target.value)} maxLength={100} />
            </label>
            <button type="button" className="primary" onClick={() => runDescriptionBuilder("generate")}
              disabled={builderStatus === "running"}>
              {builderStatus === "running" ? "Preparing structured draft…" : "Generate draft with HERA"}
            </button>
          </div>
        )}
        {creationMethod === "pasted_external" && (
          <details className="job-paste-source" open={builderStatus !== "ready"}>
            <summary>Original pasted description <span>Source text is retained</span></summary>
            <div className="job-paste-source-content">
              <label htmlFor="pasted-job-description">Existing description</label>
              <textarea id="pasted-job-description" rows="6" maxLength={50_000}
                value={pastedDescription} onChange={(event) => setPastedDescription(event.target.value)}
                placeholder="Paste an authorized job description here. HERA treats the text as source material and does not open links." />
              <button type="button" className="primary" onClick={() => runDescriptionBuilder("parse")}
                disabled={builderStatus === "running" || !pastedDescription.trim()}>
                {builderStatus === "running" ? "Analyzing pasted text…" : "Structure pasted description"}
              </button>
              {builderStatus === "ready" && <small className="muted-note">Open this section if you want to review or edit the source.</small>}
            </div>
          </details>
        )}
        {creationMethod === "manual" && (
          <button type="button" className="secondary" onClick={startManualProfileDraft}>
            Review fields as a structured profile
          </button>
        )}
        {builderStatus === "running" && <p className="hera-note" role="status">HERA is preparing a draft. Nothing is saved or approved yet.</p>}
        {builderError && <p className="hera-note hera-error" role="alert">{builderError}</p>}
        {profileDraft && (
          <section className="job-profile-draft-editor" aria-label="Review structured job description">
            <div className="job-profile-draft-heading">
              <div>
                <p className="eyebrow">STEP 3 · HR REVIEW</p>
                <h4>Review the structured draft</h4>
              </div>
              <span className="job-draft-count">{profileDraft.requirements.length} items to review</span>
            </div>
            <p className="muted-note">AI suggestions remain editable. Review uncertain items before saving; HR approval is still required.</p>
            <label>
              Job overview
              <textarea rows="4" value={profileDraft.summary}
                onChange={(event) => {
                  const summary = event.target.value;
                  setProfileDraft((current) => ({ ...current, summary }));
                  const nextJob = { ...jobRef.current, description: summary };
                  jobRef.current = nextJob;
                  setJob(nextJob);
                }} />
            </label>
            <button type="button" className="secondary" onClick={() => requestSectionImprovement({ type: "summary", label: "Job overview" })}
              disabled={improvementStatus === "running" || !profileDraft.summary.trim()}>
              {improvementStatus === "running" ? "Preparing suggestion…" : "Suggest an overview improvement"}
            </button>
            {improvementProposal?.type === "summary" && (
              <div className="hera-note" role="region" aria-label="Proposed overview improvement">
                <strong>Suggested overview</strong>
                <p>{improvementProposal.text}</p>
                <button type="button" className="primary" onClick={useImprovementProposal}>Use suggestion</button>
                <button type="button" className="secondary" onClick={() => setImprovementProposal(null)}>Discard</button>
              </div>
            )}
            {requirementSections.map((section) => {
              const sectionRequirements = profileDraft.requirements
                .map((item, index) => ({ item, index }))
                .filter(({ item }) => section.dimensions.includes(item.dimension || "skill") ||
                  (section.key === "other" && !requirementSections.slice(0, 3).some((group) => group.dimensions.includes(item.dimension || "skill"))));
              return (
              <details className="job-draft-section" key={section.key} open={sectionRequirements.length === 0}>
                <summary>
                  <span>{section.title}</span>
                  <span className="job-draft-section-count">{sectionRequirements.length} {sectionRequirements.length === 1 ? "item" : "items"}</span>
                </summary>
                {sectionRequirements.length === 0 && <p className="muted-note">Nothing listed yet. Add an item if this role needs one.</p>}
                {sectionRequirements.map(({ item, index }) => (
              <div className="job-draft-requirement" key={`${index}-${item.text}`}>
                <label>
                  {section.key === "responsibilities" ? "Responsibility" : section.key === "qualifications" ? "Qualification" : "Skill or criterion"}
                  <input aria-label={`Requirement ${index + 1}`} value={item.text} onChange={(event) => updateProfileRequirement(index, { text: event.target.value })} />
                </label>
                <label>
                  Priority
                  <select value={item.category} onChange={(event) => updateProfileRequirement(index, { category: event.target.value })}>
                    <option value="must_have">Required</option>
                    <option value="important">Needs HR confirmation</option>
                    <option value="nice_to_have">Preferred</option>
                  </select>
                </label>
                <label>
                  Type
                  <select value={item.dimension} onChange={(event) => updateProfileRequirement(index, { dimension: event.target.value })}>
                    <option value="skill">Skill</option>
                    <option value="technical_skill">Technical skill</option>
                    <option value="soft_skill">Soft skill</option>
                    <option value="experience">Experience</option>
                    <option value="education">Education</option>
                    <option value="certification">Certification</option>
                    <option value="responsibility">Responsibility</option>
                  </select>
                </label>
                <button type="button" className="btn-secondary" onClick={() => setProfileDraft((current) => ({
                  ...current, requirements: current.requirements.filter((_, itemIndex) => itemIndex !== index),
                }))}>Remove</button>
                <button type="button" className="secondary" onClick={() => requestSectionImprovement({
                  type: "requirement", index, label: `${section.title} item`,
                })} disabled={improvementStatus === "running" || !item.text.trim()}>
                  {improvementStatus === "running" ? "Improving…" : "Improve with AI"}
                </button>
                {improvementProposal?.type === "requirement" && improvementProposal.index === index && (
                  <div className="hera-note" role="region" aria-label={`Suggested improvement for ${section.title.toLowerCase()}`}>
                    <strong>AI suggestion</strong>
                    <p>{improvementProposal.text}</p>
                    <button type="button" className="primary" onClick={useImprovementProposal}>Use suggestion</button>
                    <button type="button" className="secondary" onClick={() => setImprovementProposal(null)}>Discard</button>
                  </div>
                )}
              </div>
                ))}
                <button type="button" className="btn-secondary" onClick={() => setProfileDraft((current) => ({
                  ...current, requirements: [...current.requirements, { text: "", category: "important", dimension: section.defaultDimension }],
                }))}>Add {section.title.toLowerCase().replace(/s$/, "")}</button>
              </details>
              );
            })}
            {profileDraft.needs_confirmation.length > 0 && (
              <div className="hera-note" role="note">
                <strong>Needs HR confirmation</strong>
                <ul>{profileDraft.needs_confirmation.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
              </div>
            )}
          </section>
        )}

        <div className="hera-toolbar">
          <button
            className="secondary"
            type="button"
            onClick={onFill}
            disabled={fillStatus === "analyzing" || !job.description}
            aria-describedby="hera-fill-help"
          >
            {fillButtonLabel}
          </button>
          {(isEdit || savedId) && (
            <button
              className="primary"
              type="button"
              onClick={onAnalyze}
              disabled={analyzStatus === "running"}
            >
              {analyzStatus === "running"
                ? "HERA is analysing the job..."
                : "Analyze with HERA"}
            </button>
          )}
        </div>

        <p className="hera-note" id="hera-fill-help">
          HERA uses the description to suggest title, department, location, employment type, experience,
          requirements, and required skills.
          Suggestions fill blank fields only. Review and edit them before saving; existing entries are kept.
        </p>

        {fillStatus === "analyzing" && (
          <p className="hera-note" role="status">
            HERA is suggesting form fields from your description. Nothing is
            saved until you click Save.
          </p>
        )}
        {fillStatus === "ready" && (
          <p className="hera-note" role="status">
            HERA suggested values for blank fields below. Every suggested value is marked
            <span className="ai-chip">AI</span> and stays editable until you
            save. Other entries were kept.
          </p>
        )}
        {fillStatus === "incomplete" && (
          <p className="hera-note" role="status">
            HERA could not suggest values for the remaining blank fields. Add more role detail to the description and try again.
          </p>
        )}
        {fillStatus === "no-fields" && (
          <p className="hera-note" role="status">
            There are no blank fields for HERA to fill. Your existing entries are unchanged.
          </p>
        )}
        {fillStatus === "changed" && (
          <p className="hera-note" role="status">
            The description changed while HERA was reading it, so no suggestions were applied. Run the suggestion again to use the updated description.
          </p>
        )}
        {fillStatus === "error" && (
          <p className="hera-note hera-error" role="alert">
            {fillError}
          </p>
        )}
        {savedMessage && fillStatus !== "analyzing" && (
          <p className="hera-note" role="status">
            {savedMessage} Run Analyze with HERA to build a profile from the
            description.
          </p>
        )}
        {analyzStatus === "error" && (
          <p className="hera-note hera-error" role="status">
            {analyzError}
          </p>
        )}
        {saveError && <p className="hera-note hera-error" role="alert">{saveError}</p>}

        <form onSubmit={onSubmit}>
          <label>
            Job Title
            {aiFields.has("title") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <input name="title" value={job.title} onChange={onChange} required />
          </label>
          <label>
            Department
            {aiFields.has("department") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <input name="department" value={job.department} onChange={onChange} />
          </label>
          <label>
            Location
            {aiFields.has("location") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <input name="location" value={job.location} onChange={onChange} />
          </label>
          <label>
            Employment Type
            {aiFields.has("type") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <select
              name="type"
              value={job.type}
              onChange={onChange}
              onPointerDown={() => userEditedFields.current.add("type")}
              onKeyDown={(event) => {
                if (["ArrowUp", "ArrowDown", "Home", "End", "Enter", " "].includes(event.key)) {
                  userEditedFields.current.add("type");
                }
              }}
            >
              <option>Full-time</option>
              <option>Part-time</option>
              <option>Contract</option>
              <option>Internship</option>
            </select>
          </label>
          <label>
            Work Mode
            <select name="workMode" value={job.workMode} onChange={onChange}>
              <option value="">Not specified</option>
              <option value="onsite">On-site</option>
              <option value="hybrid">Hybrid</option>
              <option value="remote">Remote</option>
            </select>
          </label>
          <p className="muted-note">New vacancies are saved as drafts. Activation is available after required details are complete and the job profile is approved.</p>
          <label>
            Experience
            {aiFields.has("experience") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <input
              name="experience"
              value={job.experience}
              onChange={onChange}
              placeholder="e.g. 2+ years"
            />
          </label>
          <label>
            Description (original job listing text)
            <textarea
              name="description"
              rows="4"
              value={job.description}
              onChange={onChange}
              placeholder="Paste the job listing text you are authorized to use. HERA will analyze this text only; it will not open or verify links."
            />
            <small className="muted-note">This is the original text provided by HR. HERA does not fetch links or check whether the listing is still available.</small>
          </label>
          <label>
            Job description file (PDF or DOCX)
            <input
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(event) => setJobFile(event.target.files?.[0] || null)}
            />
            {jobFile && <small className="muted-note">Selected: {jobFile.name}</small>}
            {!jobFile && job.sourceFileName && (
              <small className="muted-note">
                Saved file: {job.sourceFileName} · text extraction {job.sourceFileStatus || "pending"}
                {job.sourceFileError ? ` · ${job.sourceFileError}` : ""}
              </small>
            )}
          </label>
          <label>
            Requirements (one per line)
            {aiFields.has("requirementsText") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <textarea
              name="requirementsText"
              rows="4"
              value={job.requirementsText}
              onChange={onChange}
              placeholder={"2+ years of experience\nComfortable with REST APIs"}
            />
          </label>
          <label>
            Required Skills (comma separated)
            {aiFields.has("requiredSkillsText") && (
              <span className="ai-chip" aria-label="Suggested by HERA">
                AI
              </span>
            )}
            <textarea
              name="requiredSkillsText"
              rows="2"
              value={job.requiredSkillsText}
              onChange={onChange}
              placeholder="C#, .NET, SQL Server, Docker"
            />
          </label>
          <fieldset className="job-source-fields">
            <legend>Listing source (optional)</legend>
            <p className="muted-note">Keep source details separate from the listing text and HERA's suggestions.</p>
            <label>Source name<input name="sourceName" value={job.sourceName} onChange={onChange} placeholder="e.g. Company careers page" required={Boolean(job.sourceUrl || job.applicationUrl || job.publishedAt)} /></label>
            <label>Source company<input name="sourceCompany" value={job.sourceCompany} onChange={onChange} placeholder="Company name, if provided" /></label>
            <label>Source seniority<input name="sourceSeniority" value={job.sourceSeniority} onChange={onChange} placeholder="Seniority level, if provided" /></label>
            <label>Source link<input name="sourceUrl" type="url" value={job.sourceUrl} onChange={onChange} placeholder="https://..." /></label>
            <label>Publication date<input name="publishedAt" type="date" value={job.publishedAt} onChange={onChange} /></label>
            <label>Application link<input name="applicationUrl" type="url" value={job.applicationUrl} onChange={onChange} placeholder="https://..." /></label>
            <label className="source-review-confirmation">
              <input name="sourceReviewConfirmed" type="checkbox" checked={job.sourceReviewConfirmed} onChange={(event) => {
                const nextJob = { ...jobRef.current, sourceReviewConfirmed: event.target.checked };
                jobRef.current = nextJob;
                setJob(nextJob);
                userEditedFields.current.add("sourceReviewConfirmed");
              }} />
              I reviewed these source details. This records my review; HERA has not verified the link or listing status.
            </label>
          </fieldset>
          <button className="primary wide" type="submit" disabled={saving}>
            {saving
              ? "Saving..."
              : isEdit
                ? "Save Changes"
                : "Save Draft"}
          </button>
        </form>
      </div>
    </section>
  );
}

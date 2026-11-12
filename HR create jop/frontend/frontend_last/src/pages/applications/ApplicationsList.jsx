import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, BriefcaseBusiness, CalendarDays, CheckCircle2, ChevronDown, ClipboardList, Filter, Gauge, Link2, RotateCcw, Search, SlidersHorizontal, Sparkles, UserRound } from "lucide-react";
import DataTable from "../../components/common/DataTable";
import Pagination from "../../components/common/Pagination";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import { getApplicationJobs, getApplications } from "../../services/applicationService";
import { formatScore } from "../../utils/score";
import { APPLICATION_STATUS_GROUPS, APPLICATION_STATUS_LABELS } from "../../utils/applicationStatus";

const AI_REVIEW_LABELS = { must_review: "Must Review", consider: "Consider", lower_priority: "Lower Priority" };
const SOURCES = ["LinkedIn", "WUZZUF", "Facebook", "Referral", "Direct"];
const SCREENING_LABELS = { not_started: "Pending", queued: "Queued", processing: "Processing", completed: "Completed", failed: "Failed" };
const DECISION_LABELS = { pending_review: "Pending review", advanced: "Advanced", hold: "Hold", rejected: "Rejected" };
const PAGE_SIZE = 20;

export default function ApplicationsList() {
  const [applications, setApplications] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [jobId, setJobId] = useState("");
  const [source, setSource] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [processingStatus, setProcessingStatus] = useState("");
  const [decisionStatus, setDecisionStatus] = useState("");
  const [sort, setSort] = useState("created_at:desc");
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let alive = true;
    getApplicationJobs().then((rows) => { if (alive) setJobs(rows); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => { setSearch(searchInput.trim()); setPage(1); }, 250);
    return () => window.clearTimeout(timeout);
  }, [searchInput]);

  const params = useMemo(() => {
    const [sortBy, sortOrder] = sort.split(":");
    return {
      ...(filter !== "all" ? { status: filter } : {}),
      ...(jobId ? { job_id: jobId } : {}),
      ...(source ? { source } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
      ...(processingStatus ? { processing_status: processingStatus } : {}),
      ...(decisionStatus ? { decision_status: decisionStatus } : {}),
      ...(search ? { search } : {}),
      sort_by: sortBy,
      sort_order: sortOrder,
      page,
      page_size: PAGE_SIZE,
    };
  }, [filter, jobId, source, dateFrom, dateTo, processingStatus, decisionStatus, search, sort, page]);

  const load = () => {
    setLoading(true);
    setError(false);
    getApplications(params)
      .then((result) => {
        setApplications(result.items || []);
        setTotal(result.total || 0);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };
  useEffect(load, [params]); // eslint-disable-line react-hooks/exhaustive-deps

  const resetFilters = () => {
    setFilter("all"); setSearchInput(""); setSearch(""); setJobId(""); setSource("");
    setDateFrom(""); setDateTo(""); setProcessingStatus(""); setDecisionStatus("");
    setSort("created_at:desc"); setPage(1); setAdvancedFiltersOpen(false);
  };

  const activeFilterCount = [
    filter !== "all", Boolean(search), Boolean(jobId), Boolean(source), Boolean(dateFrom), Boolean(dateTo),
    Boolean(processingStatus), Boolean(decisionStatus), sort !== "created_at:desc",
  ].filter(Boolean).length;

  const columns = [
    { key: "candidateName", header: <span className="applications-column-heading"><UserRound size={14} aria-hidden="true" /> Candidate</span>, render: (row) => <div className="application-candidate-cell"><span className="application-candidate-avatar" aria-hidden="true">{row.candidateName?.trim()?.slice(0, 1)?.toUpperCase() || "?"}</span><span><strong>{row.candidateName}</strong><small>{row.email || "Email unavailable"}{row.phone ? ` · ${row.phone}` : ""}</small></span></div> },
    { key: "job", header: <span className="applications-column-heading"><BriefcaseBusiness size={14} aria-hidden="true" /> Job</span>, render: (row) => <span className="application-job-cell">{row.job || "—"}</span> },
    { key: "appliedAt", header: <span className="applications-column-heading"><CalendarDays size={14} aria-hidden="true" /> Applied</span>, render: (row) => <span className="application-date-cell">{row.appliedAt ? new Date(row.appliedAt).toLocaleDateString() : "—"}</span> },
    { key: "source", header: <span className="applications-column-heading"><Link2 size={14} aria-hidden="true" /> Reported source</span>, render: (row) => <div className="application-source-cell"><strong>{row.source || "Unspecified"}</strong>{row.sourceMedium && <small>{row.sourceMedium}{row.sourceCampaign ? ` · ${row.sourceCampaign}` : ""}</small>}</div> },
    { key: "screeningStatus", header: <span className="applications-column-heading"><Activity size={14} aria-hidden="true" /> CV screening</span>, render: (row) => <span className={`application-status-pill is-${row.screeningStatus || "pending"}`}><span className="application-status-dot" />{SCREENING_LABELS[row.screeningStatus] || "Pending"}</span> },
    { key: "score", header: <span className="applications-column-heading"><Gauge size={14} aria-hidden="true" /> Screening result</span>, render: (row) => {
      if (row.screeningStatus !== "completed") return "—";
      const evidence = Array.isArray(row.evidence) ? row.evidence : [];
      const matched = evidence.filter((entry) => entry.evidence_type === "matched").length;
      const partial = evidence.filter((entry) => entry.evidence_type === "partial").length;
      const missing = evidence.filter((entry) => entry.evidence_type === "missing").length;
      const scorePercent = Math.max(0, Math.min(100, Number(row.score) || 0));
      return <div className="application-score-cell"><div className="application-score-topline"><strong>{formatScore(row.score)}</strong><span>{matched} matched</span></div><div className="application-score-track" aria-label={`Screening score ${formatScore(row.score)}`}><span style={{ width: `${scorePercent}%` }} /></div><small>{partial} partial · {missing} missing</small></div>;
    } },
    { key: "decisionStatus", header: <span className="applications-column-heading"><CheckCircle2 size={14} aria-hidden="true" /> HR decision</span>, render: (row) => <span className={`application-decision-pill is-${row.decisionStatus || "pending"}`}>{DECISION_LABELS[row.decisionStatus] || "Pending review"}</span> },
    { key: "group", header: <span className="applications-column-heading"><Sparkles size={14} aria-hidden="true" /> AI review</span>, render: (row) => row.group ? <span className={`application-review-pill is-${row.group}`}>{AI_REVIEW_LABELS[row.group] || row.group}</span> : "—" },
  ];

  return (
    <section className="applications-page">
      <div className="applications-page-heading">
        <div className="applications-heading-title">
          <span className="applications-heading-icon"><ClipboardList size={20} aria-hidden="true" /></span>
          <div><p className="eyebrow">HIRING WORKSPACE</p><h2>Applications</h2><p>Review candidate progress and hiring decisions in one place.</p></div>
        </div>
        <div className="applications-total-chip"><strong>{total}</strong><span>{total === 1 ? "application" : "applications"}</span></div>
      </div>

      <div className="application-dashboard-filters panel" aria-label="Application filters">
        <div className="application-filter-primary-row">
          <label className="application-filter-search">
            <span><Search size={14} aria-hidden="true" /> Search</span>
            <input type="search" value={searchInput} onChange={(event) => { setSearchInput(event.target.value); setPage(1); }} placeholder="Candidate name, email, or job" />
          </label>
          <label>
            <span>Job</span>
            <select value={jobId} onChange={(event) => { setJobId(event.target.value); setPage(1); }}>
              <option value="">All jobs</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}
            </select>
          </label>
          <label>
            <span><Filter size={14} aria-hidden="true" /> Application status</span>
            <select value={filter} onChange={(event) => { setFilter(event.target.value); setPage(1); }}>
              <option value="all">All statuses</option>
              {APPLICATION_STATUS_GROUPS.map((group) => (
                <optgroup label={group.label} key={group.id}>
                  {group.statuses.map((status) => <option key={status} value={status}>{APPLICATION_STATUS_LABELS[status]}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <div className="application-filter-actions">
            <button
              type="button"
              className={`application-more-toggle ${activeFilterCount ? "has-active-filters" : ""}`}
              aria-expanded={advancedFiltersOpen}
              aria-controls="application-advanced-filters"
              onClick={() => setAdvancedFiltersOpen((open) => !open)}
            >
              <SlidersHorizontal size={15} aria-hidden="true" /> More filters
              {activeFilterCount > 0 && <span className="application-active-count">{activeFilterCount}</span>}
              <ChevronDown className={advancedFiltersOpen ? "is-open" : ""} size={15} aria-hidden="true" />
            </button>
            <button type="button" className="application-reset-button" aria-label="Reset filters" onClick={resetFilters} disabled={activeFilterCount === 0}>
              <RotateCcw size={14} aria-hidden="true" /> Reset
            </button>
          </div>
        </div>

        {advancedFiltersOpen && <div className="application-filter-advanced" id="application-advanced-filters" aria-label="Additional application filters">
          <label><span>Reported source</span><input list="hera-application-sources" value={source} onChange={(event) => { setSource(event.target.value); setPage(1); }} placeholder="All sources" /><datalist id="hera-application-sources">{SOURCES.map((item) => <option key={item} value={item} />)}<option value="Other" /><option value="unspecified" /></datalist><small className="muted-note">Attribution is unverified.</small></label>
          <label><span>Applied from</span><input type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPage(1); }} /></label>
          <label><span>Applied to</span><input type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); setPage(1); }} /></label>
          <label><span>CV processing</span><select value={processingStatus} onChange={(event) => { setProcessingStatus(event.target.value); setPage(1); }}><option value="">All processing states</option>{Object.entries(SCREENING_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label><span>HR decision</span><select value={decisionStatus} onChange={(event) => { setDecisionStatus(event.target.value); setPage(1); }}><option value="">All decisions</option>{Object.entries(DECISION_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label><span>Sort by</span><select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }}><option value="created_at:desc">Newest applications</option><option value="created_at:asc">Oldest applications</option><option value="score:desc">Highest screening score</option><option value="score:asc">Lowest screening score</option></select></label>
        </div>}
      </div>

      {loading ? <LoadingSpinner label="Loading applications..." /> : error ? <ErrorState message="Unable to load applications. Please try again." onRetry={load} /> : <>
        <DataTable columns={columns} data={applications} onRowClick={(row) => navigate(`/applications/${row.id}/review`)} header={<div className="applications-table-heading"><div><span className="applications-table-heading-icon"><ClipboardList size={17} aria-hidden="true" /></span><span><strong>Application pipeline</strong><small>Candidate progress, screening, and decisions</small></span></div><span className="applications-table-count">Showing {applications.length} of {total}</span></div>} emptyLabel={total === 0 && filter === "all" && !search && !jobId && !source && !dateFrom && !dateTo && !processingStatus && !decisionStatus ? "No applications yet." : "No applications match these filters."} emptyAction={total === 0 && filter === "all" && !search && !jobId && !source && !dateFrom && !dateTo && !processingStatus && !decisionStatus ? <button type="button" className="btn btn-secondary btn-small" onClick={() => navigate("/candidates/screen")}>Start screening</button> : <button type="button" className="btn btn-secondary btn-small" onClick={resetFilters}>Reset filters</button>} />
        <Pagination total={total} pageSize={PAGE_SIZE} page={page} onPageChange={setPage} />
      </>}
    </section>
  );
}

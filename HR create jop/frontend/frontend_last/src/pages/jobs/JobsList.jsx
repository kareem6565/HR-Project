import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  Eye,
  MapPin,
  Pencil,
  Plus,
  Trash2,
  UsersRound,
} from "lucide-react";
import Badge from "../../components/common/Badge";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import { getJobs, deleteJob } from "../../services/jobService";

export default function JobsList() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [jobToDelete, setJobToDelete] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    getJobs()
      .then((data) => {
        setJobs(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, []);

  const jobStats = jobs.reduce((stats, job) => {
    const status = String(job.status || "").toLowerCase();
    const applicants = Number(job.applicants);
    stats.total += 1;
    if (status === "active") stats.active += 1;
    if (status === "draft") stats.drafts += 1;
    if (Number.isFinite(applicants)) stats.applicants += applicants;
    return stats;
  }, { total: 0, active: 0, drafts: 0, applicants: 0 });

  const requestDelete = (e, job) => {
    e.stopPropagation();
    setJobToDelete(job);
    setDeleteError(null);
  };

  const confirmDelete = async () => {
    if (!jobToDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteJob(jobToDelete.id);
      setJobToDelete(null);
      load();
    } catch (err) {
      setDeleteError(err?.response?.data?.detail || err?.message || "Unable to delete this job.");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading jobs..." />;
  if (error) return <ErrorState message="Unable to load jobs. Please try again." onRetry={load} />;

  return (
    <section className="jobs-page" aria-label="Jobs">
      <div className="section-head jobs-section-head">
        <div>
          <p className="eyebrow jobs-page-eyebrow"><BriefcaseBusiness size={14} aria-hidden="true" /> JOBS</p>
          <h2>Open positions</h2>
          <p className="jobs-page-description">Manage your roles and keep track of applicant activity.</p>
        </div>
        <button className="primary jobs-new-button" onClick={() => navigate("/jobs/new")}>
          <Plus size={18} /> New Job
        </button>
      </div>

      <div className="jobs-content-grid">
        <div className="jobs-list-column">
          {!jobs.length ? (
            <div className="panel jobs-empty-panel"><EmptyState message="No jobs posted yet." /></div>
          ) : (
            <div className="panel table-panel jobs-table-panel">
              <div className="jobs-table-heading">
                <div>
                  <h3><BriefcaseBusiness size={17} aria-hidden="true" /> Job listings</h3>
                  <span>{jobStats.total} {jobStats.total === 1 ? "role" : "roles"} in your workspace</span>
                </div>
                <span className="jobs-list-count" aria-label={`${jobStats.total} jobs`}>{jobStats.total}</span>
              </div>
              <div className="table-wrap">
                <table className="jobs-table">
              <thead>
                <tr>
                  <th scope="col"><span className="jobs-column-heading"><BriefcaseBusiness size={14} aria-hidden="true" /> Job Title</span></th>
                  <th scope="col">Department</th>
                  <th scope="col"><span className="jobs-column-heading"><MapPin size={14} aria-hidden="true" /> Location</span></th>
                  <th scope="col">Type</th>
                  <th scope="col">Experience</th>
                  <th scope="col"><span className="jobs-column-heading"><UsersRound size={14} aria-hidden="true" /> Applicants</span></th>
                  <th scope="col">Status</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    className="clickable"
                    tabIndex={0}
                    role="link"
                    aria-label={`View job ${job.title}`}
                    onClick={() => navigate(`/jobs/${job.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        navigate(`/jobs/${job.id}`);
                      }
                    }}
                  >
                    <td>
                      <div className="jobs-title-cell">
                        <span className="jobs-title-icon"><BriefcaseBusiness size={15} aria-hidden="true" /></span>
                        <strong>{job.title}</strong>
                      </div>
                    </td>
                    <td>{job.department}</td>
                    <td>{job.location}</td>
                    <td>{job.type}</td>
                    <td>{job.experience}</td>
                    <td><span className="jobs-applicant-total"><UsersRound size={14} aria-hidden="true" /> {job.applicants}</span></td>
                    <td>
                      <Badge status={job.status} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          type="button"
                          title="View"
                          aria-label={`View ${job.title}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/jobs/${job.id}`);
                          }}
                        >
                          <Eye size={16} aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          title="Edit"
                          aria-label={`Edit ${job.title}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/jobs/${job.id}/edit`);
                          }}
                        >
                          <Pencil size={16} aria-hidden="true" />
                        </button>
                        <button
                          type="button"
                          title="Delete"
                          aria-label={`Delete ${job.title}`}
                          className="danger"
                          disabled={deleting && jobToDelete?.id === job.id}
                          onClick={(e) => requestDelete(e, job)}
                        >
                          <Trash2 size={16} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <aside className="panel jobs-overview" aria-labelledby="jobs-overview-title">
          <div className="jobs-overview-heading">
            <span className="jobs-overview-icon"><BriefcaseBusiness size={18} aria-hidden="true" /></span>
            <div>
              <h3 id="jobs-overview-title">Hiring at a glance</h3>
              <p>Live totals from your job list</p>
            </div>
          </div>
          <div className="jobs-overview-stats">
            <div className="jobs-overview-stat">
              <span className="jobs-overview-stat-icon jobs-stat-teal"><BriefcaseBusiness size={16} aria-hidden="true" /></span>
              <span><small>Total jobs</small><strong>{jobStats.total}</strong></span>
            </div>
            <div className="jobs-overview-stat">
              <span className="jobs-overview-stat-icon jobs-stat-green"><CheckCircle2 size={16} aria-hidden="true" /></span>
              <span><small>Active</small><strong>{jobStats.active}</strong></span>
            </div>
            <div className="jobs-overview-stat">
              <span className="jobs-overview-stat-icon jobs-stat-gold"><Clock3 size={16} aria-hidden="true" /></span>
              <span><small>Drafts</small><strong>{jobStats.drafts}</strong></span>
            </div>
            <div className="jobs-overview-stat">
              <span className="jobs-overview-stat-icon jobs-stat-blue"><UsersRound size={16} aria-hidden="true" /></span>
              <span><small>Applicants</small><strong>{jobStats.applicants}</strong></span>
            </div>
          </div>
          <div className="jobs-overview-footer">
            <p>{jobStats.applicants ? "Applications are ready for review." : "Add a role to start building your hiring pipeline."}</p>
            {jobStats.applicants > 0 ? (
              <button type="button" className="secondary jobs-review-link" onClick={() => navigate("/applications")}>
                <UsersRound size={15} aria-hidden="true" /> Review applicants
              </button>
            ) : (
              <button type="button" className="secondary jobs-review-link" onClick={() => navigate("/jobs/new")}>
                <Plus size={15} aria-hidden="true" /> Create a job
              </button>
            )}
          </div>
        </aside>
      </div>

      <Modal
        open={!!jobToDelete}
        onClose={() => {
          if (!deleting) {
            setJobToDelete(null);
            setDeleteError(null);
          }
        }}
        title={`Delete Job: ${jobToDelete?.title || ""}`}
      >
        <p>
          Are you sure you want to delete <strong>{jobToDelete?.title}</strong>? This action cannot be undone.
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
              setJobToDelete(null);
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

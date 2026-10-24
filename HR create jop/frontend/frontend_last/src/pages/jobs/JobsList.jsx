import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Eye, Pencil, Trash2 } from "lucide-react";
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
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">JOBS</p>
          <h2>Open positions</h2>
        </div>
        <button className="primary" onClick={() => navigate("/jobs/new")}>
          <Plus size={18} /> New Job
        </button>
      </div>

      {!jobs.length ? (
        <EmptyState message="No jobs posted yet." />
      ) : (
        <div className="panel table-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Job Title</th>
                  <th scope="col">Department</th>
                  <th scope="col">Location</th>
                  <th scope="col">Type</th>
                  <th scope="col">Experience</th>
                  <th scope="col">Applicants</th>
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
                      <strong>{job.title}</strong>
                    </td>
                    <td>{job.department}</td>
                    <td>{job.location}</td>
                    <td>{job.type}</td>
                    <td>{job.experience}</td>
                    <td>{job.applicants}</td>
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

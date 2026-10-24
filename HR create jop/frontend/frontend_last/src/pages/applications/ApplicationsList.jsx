import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import DataTable from "../../components/common/DataTable";
import Badge from "../../components/common/Badge";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import { getApplications } from "../../services/applicationService";
import { formatScore } from "../../utils/score";
import { APPLICATION_STATUS_GROUPS, APPLICATION_STATUS_LABELS } from "../../utils/applicationStatus";

const AI_REVIEW_LABELS = {
  must_review: "Must Review",
  consider: "Consider",
  lower_priority: "Lower Priority",
};

export default function ApplicationsList() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState("all");
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    getApplications(filter)
      .then((data) => {
        setApplications(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  const columns = [
    { key: "candidateName", header: "Candidate" },
    { key: "job", header: "Job" },
    { key: "appliedAt", header: "Applied On" },
    {
      key: "score",
      header: "AI Match Score",
      render: (row) => formatScore(row.score),
    },
    {
      key: "group",
      header: "AI Review Category",
      render: (row) => {
        const label = AI_REVIEW_LABELS[row.group];
        return label ? (
          <span className="application-ai-category">{label}</span>
        ) : (
          <span className="muted-note" title="No AI review category is available for this application.">
            Not available
          </span>
        );
      },
    },
    { key: "status", header: "Application State", render: (row) => <Badge status={row.status} /> },
  ];

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">APPLICATIONS</p>
          <h2>All Applications</h2>
        </div>
      </div>

      <div className="application-filter-groups" aria-label="Filter applications">
        <div className="application-filter-group" role="group" aria-label="All applications">
          <span className="application-filter-label">All applications</span>
          <button
            type="button"
            className={`filter-tab ${filter === "all" ? "active" : ""}`}
            aria-pressed={filter === "all"}
            onClick={() => setFilter("all")}
          >
            All
          </button>
        </div>
        {APPLICATION_STATUS_GROUPS.map((group) => (
          <div className="application-filter-group" role="group" aria-label={group.label} key={group.id}>
            <span className="application-filter-label">{group.label}</span>
            <div className="application-filter-options">
              {group.statuses.map((status) => (
                <button
                  key={status}
                  type="button"
                  className={`filter-tab ${filter === status ? "active" : ""}`}
                  aria-pressed={filter === status}
                  onClick={() => setFilter(status)}
                >
                  {APPLICATION_STATUS_LABELS[status]}
                </button>
              ))}
            </div>
            {group.id === "decision" && (
              <p className="application-filter-note">{group.description}</p>
            )}
          </div>
        ))}
      </div>

      {loading ? (
        <LoadingSpinner label="Loading applications..." />
      ) : error ? (
        <ErrorState message="Unable to load applications. Please try again." onRetry={load} />
      ) : (
        <DataTable
          columns={columns}
          data={applications}
          onRowClick={(row) => navigate(`/applications/${row.id}/review`)}
          emptyLabel={filter === "all" ? "No applications yet." : "No applications match this status."}
          emptyAction={
            filter === "all" ? (
              <button
                type="button"
                className="btn btn-secondary btn-small"
                onClick={() => navigate("/candidates/screen")}
              >
                Start screening
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-secondary btn-small"
                onClick={() => setFilter("all")}
              >
                Show all applications
              </button>
            )
          }
        />
      )}
    </section>
  );
}

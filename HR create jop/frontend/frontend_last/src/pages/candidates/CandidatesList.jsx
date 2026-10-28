import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, Plus, ChevronRight, Archive } from "lucide-react";
import Badge from "../../components/common/Badge";
import Pagination from "../../components/common/Pagination";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import { archiveCandidate, getCandidates } from "../../services/candidateService";
import { CandidateStatus } from "../../types/api";

// Display labels for the org-wide roster's status vocabulary (the Candidate
// model's active/archived status). The filter dropdown uses the same values
// the API returns.
const STATUS_OPTIONS = [
  { value: CandidateStatus.ACTIVE, label: "Active" },
  { value: CandidateStatus.ARCHIVED, label: "Archived" },
];

const PAGE_SIZE = 5;

export default function CandidatesList() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState(CandidateStatus.ACTIVE);
  const [sort, setSort] = useState("date");
  const [page, setPage] = useState(1);
  const [candidateToArchive, setCandidateToArchive] = useState(null);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState("");
  const [archiveMessage, setArchiveMessage] = useState("");
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    getCandidates()
      .then((data) => {
        setCandidates(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, []);

  // Reset back to page 1 whenever the filters change so we never land on an
  // empty page after narrowing the results.
  useEffect(() => {
    setPage(1);
  }, [search, status, sort]);

  const filtered = useMemo(() => {
    let list = candidates.filter(
      (c) =>
        `${c.name} ${c.email} ${c.skills.join(" ")}`
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (status === "all" || c.status === status)
    );
    return list.sort((a, b) => {
      if (sort === "date") {
        return new Date(b.appliedAt || 0) - new Date(a.appliedAt || 0);
      }
      return a.name.localeCompare(b.name);
    });
  }, [candidates, search, status, sort]);

  const paged = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  const confirmArchive = async () => {
    if (!candidateToArchive || archiving) return;
    setArchiving(true);
    setArchiveError("");
    try {
      await archiveCandidate(candidateToArchive.id);
      setCandidates((current) =>
        current.map((candidate) =>
          candidate.id === candidateToArchive.id
            ? { ...candidate, status: CandidateStatus.ARCHIVED }
            : candidate
        )
      );
      setArchiveMessage(`${candidateToArchive.name} was archived. Their hiring history is retained.`);
      setCandidateToArchive(null);
    } catch (err) {
      setArchiveError(
        err?.response?.data?.detail || "Could not archive this candidate. Please try again."
      );
    } finally {
      setArchiving(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading candidates..." />;
  if (error) return <ErrorState message="Unable to load candidates. Please try again." onRetry={load} />;

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">CANDIDATES</p>
          <h2>All Candidates</h2>
        </div>
        <button className="primary" onClick={() => navigate("/candidates/screen")}>
          <Plus size={18} /> New Screening
        </button>
      </div>

      {archiveMessage && (
        <p className="success-message" role="status">
          {archiveMessage}
        </p>
      )}

      <div className="toolbar">
        <div className="search">
          <Search size={18} aria-hidden="true" />
          <input
            placeholder="Search candidates..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search candidates"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter candidates by status"
        >
          <option value="all">All Status</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          aria-label="Sort candidates"
        >
          <option value="date">Newest First</option>
          <option value="name">Name</option>
        </select>
      </div>

      {!candidates.length ? (
        <EmptyState message="No candidates yet. Start a screening to add candidates from CVs." />
      ) : (
        <>
          <div className="panel table-panel">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Candidate</th>
                    <th scope="col">Status</th>
                    <th scope="col">Profile Skills</th>
                    <th scope="col">Experience</th>
                    <th scope="col">Added</th>
                    <th scope="col"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {paged.map((c) => (
                    <tr
                      key={c.id}
                      className="clickable"
                      onClick={() => navigate(`/candidates/${c.id}`)}
                    >
                      <td>
                        <div className="candidate-cell">
                          <div className="mini-avatar" aria-hidden="true">
                            {c.name
                              .split(" ")
                              .map((x) => x[0])
                              .join("")
                              .slice(0, 2)}
                          </div>
                          <div>
                            <Link
                              to={`/candidates/${c.id}`}
                              aria-label={`View candidate profile for ${c.name}`}
                              onClick={(event) => event.stopPropagation()}
                            >
                              <strong>{c.name}</strong>
                            </Link>
                            <span>{c.email || "—"}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <Badge status={c.status} />
                      </td>
                      <td>
                        <div className="skill-preview">
                          {c.skills.length ? (
                            c.skills.slice(0, 3).map((s) => <span key={s}>{s}</span>)
                          ) : (
                            <span className="muted-note">No profile yet</span>
                          )}
                          {c.skills.length > 3 && <span>+{c.skills.length - 3}</span>}
                        </div>
                      </td>
                      <td>{c.experience || "—"}</td>
                      <td>{c.appliedAt ? new Date(c.appliedAt).toLocaleDateString() : "—"}</td>
                      <td>
                        <div className="candidate-row-actions">
                          {c.status === CandidateStatus.ACTIVE && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-small candidate-archive-action"
                              aria-label={`Archive ${c.name}`}
                              onClick={(event) => {
                                event.stopPropagation();
                                setArchiveError("");
                                setArchiveMessage("");
                                setCandidateToArchive(c);
                              }}
                            >
                              <Archive size={15} aria-hidden="true" /> Archive
                            </button>
                          )}
                          <ChevronRight size={17} aria-hidden="true" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!filtered.length && (
              <EmptyState
                message="No candidates match your search or status filter."
                action={(
                  <button
                    type="button"
                    className="btn btn-secondary btn-small"
                    onClick={() => {
                      setSearch("");
                      setStatus("all");
                    }}
                  >
                    Clear filters
                  </button>
                )}
              />
            )}
          </div>

          <Pagination total={filtered.length} pageSize={PAGE_SIZE} page={page} onPageChange={setPage} />
        </>
      )}

      <Modal
        open={Boolean(candidateToArchive)}
        title="Archive candidate?"
        onClose={() => {
          if (!archiving) {
            setCandidateToArchive(null);
            setArchiveError("");
          }
        }}
      >
        <p>
          Archive <strong>{candidateToArchive?.name}</strong>? They will leave the active candidate
          list, while applications, CVs, evaluations, and hiring decisions remain available in
          their history.
        </p>
        {archiveError && <p className="form-error" role="alert">{archiveError}</p>}
        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setCandidateToArchive(null);
              setArchiveError("");
            }}
            disabled={archiving}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={confirmArchive}
            disabled={archiving}
          >
            {archiving ? "Archiving…" : "Archive candidate"}
          </button>
        </div>
      </Modal>
    </section>
  );
}

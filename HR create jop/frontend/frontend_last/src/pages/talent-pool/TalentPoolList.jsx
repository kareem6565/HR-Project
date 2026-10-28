import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Search } from "lucide-react";
import RankedCandidateList, {
  CandidateCell,
  GroupPill,
  ScoreCell,
} from "../../components/common/RankedCandidateList";
import { getTalentPool } from "../../services/talentPoolService";

const STATUS_LABEL = {
  hold: "Hold",
  advanced: "Advanced",
  rejected: "Rejected for this role",
};

const DECISION_LABEL = {
  advance: "Advance",
  hold: "Hold",
  reject: "Reject",
};

// Search/filter semantics belong to the page: the search box matches the
// human-readable group label too, while only the backend's raw group value is
// ever displayed (GroupPill owns the display mapping).
const GROUP_SEARCH_LABEL = {
  must_review: "Must Review",
  consider: "Consider",
  lower_priority: "Lower Priority",
};

function SkillsCell({ skills }) {
  if (!skills?.length) return <span className="muted-note">No extracted skills available</span>;
  return (
    <div className="talent-pool-skills" aria-label={`Profile skills: ${skills.join(", ")}`}>
      {skills.slice(0, 4).map((skill) => <span className="chip" key={skill}>{skill}</span>)}
      {skills.length > 4 && <span className="muted-note">+{skills.length - 4}</span>}
    </div>
  );
}

export default function TalentPoolList() {
  const [pool, setPool] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState("");
  const [includeRejected, setIncludeRejected] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    getTalentPool({ includeRejected })
      .then((data) => {
        setPool(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, [includeRejected]);

  const filtered = pool.filter((c) =>
    `${c.name} ${c.jobTitle} ${(c.skills || []).join(" ")} ${GROUP_SEARCH_LABEL[c.group] || ""} ${c.status}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const columns = [
    {
      key: "candidate",
      header: "Candidate",
      render: (c) => (
        <CandidateCell name={c.name} subtitle={c.email ? <span className="muted-note">{c.email}</span> : null} />
      ),
    },
    { key: "jobTitle", header: "Role" },
    { key: "skills", header: "Profile skills", render: (c) => <SkillsCell skills={c.skills} /> },
    { key: "group", header: "Group", render: (c) => <GroupPill group={c.group} /> },
    { key: "status", header: "Status", render: (c) => STATUS_LABEL[c.status] || c.status || "—" },
    { key: "score", header: "Score", render: (c) => <ScoreCell score={c.score} variant="text" /> },
    { key: "decision", header: "HR decision", render: (c) => DECISION_LABEL[c.decision] || c.decision || "—" },
    {
      key: "consentExpiresAt",
      header: "Talent Pool consent until",
      render: (c) => c.consentExpiresAt ? new Date(c.consentExpiresAt).toLocaleDateString() : "—",
    },
    {
      key: "decisionCreatedAt",
      header: "Decision date",
      render: (c) => c.decisionCreatedAt ? new Date(c.decisionCreatedAt).toLocaleDateString() : "—",
    },
    {
      key: "evidence",
      header: "Previous evidence",
      render: (c) => {
        const items = c.evidence || [];
        const verified = items.filter((item) => item.quote_verified && item.quote);
        if (!items.length) return <span className="muted-note">No saved evidence</span>;
        return (
          <details onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
            <summary>{verified.length} verified quote{verified.length === 1 ? "" : "s"} · {items.length} criteria</summary>
            <ul>
              {items.map((item, index) => (
                <li key={`${item.requirement}-${index}`}>
                  <strong>{item.requirement || "Requirement"}</strong>: {item.evidence_type}
                  {item.quote_verified && item.quote
                    ? <blockquote>{item.quote}</blockquote>
                    : <span className="muted-note"> No verified quote</span>}
                </li>
              ))}
            </ul>
          </details>
        );
      },
    },
    {
      key: "action",
      header: "Action",
      render: (c) => (
        <div className="row-actions">
          <button
            type="button"
            className="btn btn-secondary btn-small"
            onClick={() => navigate(`/applications/${c.id}/review`)}
          >
            Review application <ArrowRight size={14} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">TALENT POOL</p>
          <h2>Previous applications to revisit</h2>
          <p className="muted-note">
            This view contains applications HR marked Hold or Advance for earlier roles. Rejected applications are optional; rejection applies only to the original role. Review opens the original
            application so its evidence and decision stay tied to that job. Only candidates with current Talent Pool consent appear here. Search includes stored profile skill tags;
            HERA does not calculate a new suitability score here.
          </p>
        </div>
      </div>

      <RankedCandidateList
        loading={loading}
        loadingLabel="Loading talent pool..."
        error={error}
        errorMessage="Unable to load the talent pool. Please try again."
        onRetry={load}
        emptyMessage={
          search
            ? "No previous applications match your search."
            : includeRejected
              ? "No prior Hold, Advance, or Rejected applications with current Talent Pool consent are available."
              : "No Hold or Advance applications with current Talent Pool consent are available. Turn on ‘Include rejected applications’ to include eligible prior rejections."
        }
        header={
          <div className="panel-title" style={{ padding: "18px 22px 0" }}>
            <h3>Previous applications</h3>
            <div className="toolbar" style={{ gap: 10 }}>
              <div className="search" style={{ maxWidth: 240 }}>
                <Search size={16} />
                <input
                  placeholder="Search name, role, or skill..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <label className="talent-pool-rejected-filter">
                <input
                  type="checkbox"
                  checked={includeRejected}
                  onChange={(event) => setIncludeRejected(event.target.checked)}
                />
                Include rejected applications
              </label>
            </div>
          </div>
        }
        columns={columns}
        rows={filtered}
        onRowClick={(c) => navigate(`/applications/${c.id}/review`)}
      />
    </section>
  );
}

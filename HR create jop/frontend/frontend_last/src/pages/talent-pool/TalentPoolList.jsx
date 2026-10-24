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
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    getTalentPool()
      .then((data) => {
        setPool(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, []);

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
    { key: "decision", header: "Decision", render: (c) => c.decision || "—" },
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
          <h2>Previously held or advanced applications</h2>
          <p className="muted-note">
            This view contains applications HR marked Hold or Advance for earlier roles. Review opens the original
            application so its evidence and decision stay tied to that job. Search includes stored profile skill tags;
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
            ? "No held or advanced applications match your search."
            : "No applications are currently on Hold or Advanced."
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

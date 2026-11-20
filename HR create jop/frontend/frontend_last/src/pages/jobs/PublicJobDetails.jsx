import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { BriefcaseBusiness, MapPin, Clock3, Building2 } from "lucide-react";
import { getPublicJob } from "../../services/jobService";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import "./PublicJobDetails.css";

function Section({ title, items }) {
  if (!items?.length) return null;
  return <section className="public-job-section"><h2>{title}</h2><ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></section>;
}

export default function PublicJobDetails() {
  const { publicId } = useParams();
  const location = useLocation();
  const trackedCampaign = new URLSearchParams(location.search).get("utm_campaign") || "";
  const [job, setJob] = useState(null);
  const [state, setState] = useState("loading");
  useEffect(() => {
    let alive = true;
    getPublicJob(publicId, trackedCampaign ? { utm_campaign: trackedCampaign } : {})
      .then((data) => { if (alive) { setJob(data); setState("ready"); } })
      .catch(() => { if (alive) setState("missing"); });
    return () => { alive = false; };
  }, [publicId, trackedCampaign]);
  if (state === "loading") return <main className="public-job-page"><LoadingSpinner label="Loading job…" /></main>;
  if (state === "missing") return <main className="public-job-page"><section className="public-job-card"><h1>Job listing unavailable</h1><p>This job may be unpublished or the link may be invalid.</p></section></main>;
  return <main className="public-job-page" dir="auto">
    <header className="public-job-brand"><span className="public-job-mark">H</span><strong>HERA Careers</strong></header>
    <article className="public-job-card">
      <p className="public-job-company"><Building2 size={17} /> {job.organization_name}</p>
      <h1>{job.title}</h1>
      <div className="public-job-meta">
        {job.location && <span><MapPin size={16} />{job.location}</span>}
        {job.job_type && <span><BriefcaseBusiness size={16} />{job.job_type}</span>}
        {job.work_mode && <span>{job.work_mode}</span>}
        {job.experience && <span><Clock3 size={16} />{job.experience}</span>}
      </div>
      {!job.accepting_applications && <div className="public-job-closed" role="status">Applications are no longer being accepted for this job.</div>}
      {job.accepting_applications && <Link className="public-job-apply-link" to={{
        pathname: `/careers/${encodeURIComponent(publicId)}/apply`,
        search: location.search,
      }}>Apply for this job</Link>}
      {job.description && <section className="public-job-section"><h2>About the role</h2><p>{job.description}</p></section>}
      <Section title="Responsibilities" items={job.responsibilities} />
      <Section title="Required qualifications" items={job.required_qualifications} />
      <Section title="Other qualifications" items={job.other_qualifications} />
      <Section title="Preferred qualifications" items={job.preferred_qualifications} />
    </article>
    <footer className="public-job-footer">Powered by HERA</footer>
  </main>;
}

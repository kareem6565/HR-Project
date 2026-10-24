import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  XCircle,
  Calendar,
  CalendarDays,
  Clock3,
  CheckCircle2,
  FileText,
  ChevronLeft,
  ChevronRight,
  List,
} from "lucide-react";
import Badge from "../../components/common/Badge";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Modal from "../../components/common/Modal";
import { getInterviews, cancelInterview } from "../../services/interviewService";

const TABS = [
  { key: "Scheduled", label: "Upcoming Interviews" },
  { key: "Completed", label: "Completed Interviews" },
  { key: "Cancelled", label: "Cancelled Interviews" },
];

const TYPE_TONE = { Technical: "blue", HR: "violet", Behavioral: "amber" };

function localDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfWeek(date) {
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  return start;
}

function addDays(date, amount) {
  const result = new Date(date);
  result.setDate(result.getDate() + amount);
  return result;
}

export function getInterviewWeekDays(date) {
  const start = startOfWeek(date);
  return Array.from({ length: 7 }, (_, index) => addDays(start, index));
}

function formatWeekRange(start, end) {
  const sameMonth = start.getMonth() === end.getMonth();
  const sameYear = start.getFullYear() === end.getFullYear();
  if (sameMonth && sameYear) {
    return `${start.toLocaleDateString(undefined, { month: "long" })} ${start.getDate()}–${end.getDate()}, ${start.getFullYear()}`;
  }
  const monthDayYear = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
  if (sameYear) {
    const monthDay = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
    return `${monthDay.format(start)} – ${monthDayYear.format(end)}`;
  }
  return `${monthDayYear.format(start)} – ${monthDayYear.format(end)}`;
}

function formatCalendarDay(date) {
  return {
    weekday: new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(date),
    day: new Intl.DateTimeFormat(undefined, { day: "numeric" }).format(date),
  };
}

function getInitials(name) {
  return String(name || "?")
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function isValidCalendarDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isFinite(parsed.getTime()) && localDateKey(parsed) === value;
}

export function countInterviewsScheduledThisWeek(interviews, now = new Date()) {
  const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
  const nextWeekStart = new Date(weekStart);
  nextWeekStart.setDate(nextWeekStart.getDate() + 7);
  const startKey = localDateKey(weekStart);
  const endKey = localDateKey(nextWeekStart);

  return interviews.filter((interview) => {
    if (!["Scheduled", "Completed"].includes(interview.status)) return false;
    if (!isValidCalendarDate(interview.date)) return false;
    return interview.date >= startKey && interview.date < endKey;
  }).length;
}

export default function InterviewsList() {
  const [allInterviews, setAllInterviews] = useState([]);
  const [interviews, setInterviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tab, setTab] = useState("Scheduled");
  const [view, setView] = useState("calendar");
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setError(false);
    Promise.all([getInterviews(), getInterviews(tab)])
      .then(([all, filtered]) => {
        setAllInterviews(all);
        setInterviews(filtered);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  };

  useEffect(load, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  const stats = useMemo(() => {
    const scheduled = allInterviews.filter((i) => i.status === "Scheduled").length;
    const completed = allInterviews.filter((i) => i.status === "Completed").length;
    const today = new Date().toISOString().slice(0, 10);
    const pendingFeedback = allInterviews.filter((i) => i.status === "Scheduled" && i.date < today).length;
    return {
      thisWeek: countInterviewsScheduledThisWeek(allInterviews),
      scheduled,
      completed,
      pendingFeedback,
    };
  }, [allInterviews]);

  const confirmCancel = async () => {
    if (!cancelTarget) return;
    setCancelling(true);
    await cancelInterview(cancelTarget.id);
    setCancelling(false);
    setCancelTarget(null);
    load();
  };

  const panelTitle = TABS.find((t) => t.key === tab)?.label || "Interviews";
  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)), [weekStart]);
  const weekEnd = weekDays[6];
  const weekStartKey = localDateKey(weekStart);
  const nextWeekStartKey = localDateKey(addDays(weekStart, 7));
  const weekInterviews = useMemo(
    () => interviews.filter((interview) =>
      isValidCalendarDate(interview.date) &&
      interview.date >= weekStartKey &&
      interview.date < nextWeekStartKey
    ),
    [interviews, weekStartKey, nextWeekStartKey]
  );
  const interviewsByDay = useMemo(() => {
    const grouped = new Map(weekDays.map((day) => [localDateKey(day), []]));
    weekInterviews.forEach((interview) => grouped.get(interview.date)?.push(interview));
    grouped.forEach((dayInterviews) => dayInterviews.sort((a, b) => a.time.localeCompare(b.time)));
    return grouped;
  }, [weekDays, weekInterviews]);

  const openInterview = (interview) => navigate(`/interviews/${interview.id}/feedback`);

  const renderInterviewCard = (interview) => (
    <article className="interview-calendar-event" key={interview.id}>
      <span className="interview-calendar-time">{interview.time || "Time not provided"}</span>
      <span className="interview-event-avatar" aria-hidden="true">{getInitials(interview.candidateName)}</span>
      <strong className="interview-calendar-candidate">{interview.candidateName}</strong>
      <span className="interview-calendar-job">{interview.job || "Job not provided"}</span>
      <span className={`badge badge-${TYPE_TONE[interview.type] || "grey"}`}>{interview.type || "Interview"}</span>
      <button type="button" className="interview-calendar-open" onClick={() => openInterview(interview)}>
        {interview.status === "Completed" ? "View feedback" : "Open workspace"}
      </button>
      {interview.status === "Scheduled" && (
        <button
          type="button"
          className="interview-calendar-cancel"
          aria-label={`Cancel interview with ${interview.candidateName}`}
          onClick={() => setCancelTarget(interview)}
        >
          <XCircle size={15} /> Cancel
        </button>
      )}
    </article>
  );

  return (
    <section>
      <div className="section-head">
        <div>
          <p className="eyebrow">INTERVIEWS</p>
          <h2>Interviews</h2>
          <p className="muted-note">{stats.thisWeek} scheduled this week</p>
        </div>
        <button className="primary" onClick={() => navigate("/interviews/schedule")}>
          <Plus size={18} /> Schedule Interview
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon tone-blue">
            <Calendar size={20} />
          </div>
          <div className="stat-info">
            <span>This Week</span>
            <strong>{stats.thisWeek}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon tone-violet">
            <Clock3 size={20} />
          </div>
          <div className="stat-info">
            <span>Scheduled</span>
            <strong>{stats.scheduled}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon tone-green">
            <CheckCircle2 size={20} />
          </div>
          <div className="stat-info">
            <span>Completed</span>
            <strong>{stats.completed}</strong>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon tone-amber">
            <FileText size={20} />
          </div>
          <div className="stat-info">
            <span>Pending Feedback</span>
            <strong>{stats.pendingFeedback}</strong>
          </div>
        </div>
      </div>

      <div className="filter-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`filter-tab ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label.replace(" Interviews", "")}
          </button>
        ))}
      </div>

      <div className="interview-view-toolbar">
        <div className="interview-view-switch" role="group" aria-label="Interview view">
          <button
            type="button"
            className={view === "calendar" ? "active" : ""}
            aria-pressed={view === "calendar"}
            onClick={() => setView("calendar")}
          >
            <CalendarDays size={16} /> Calendar
          </button>
          <button
            type="button"
            className={view === "list" ? "active" : ""}
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <List size={16} /> List
          </button>
        </div>
        {view === "calendar" && (
          <div className="interview-week-navigation" role="group" aria-label="Calendar week navigation">
            <button
              type="button"
              aria-label="Previous week"
              onClick={() => setWeekStart((date) => addDays(date, -7))}
            >
              <ChevronLeft size={17} />
            </button>
            <strong>{formatWeekRange(weekStart, weekEnd)}</strong>
            <button
              type="button"
              aria-label="Next week"
              onClick={() => setWeekStart((date) => addDays(date, 7))}
            >
              <ChevronRight size={17} />
            </button>
            <button
              type="button"
              className="interview-today-button"
              onClick={() => setWeekStart(startOfWeek(new Date()))}
            >
              Today
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <LoadingSpinner label="Loading interviews..." />
      ) : error ? (
        <ErrorState message="Unable to load interviews. Please try again." onRetry={load} />
      ) : view === "calendar" ? (
        <section className="panel interview-calendar" aria-label={`${tab} calendar for ${formatWeekRange(weekStart, weekEnd)}`}>
          <div className="interview-calendar-heading">
            <h3>{panelTitle}</h3>
            <span>{weekInterviews.length} {weekInterviews.length === 1 ? "interview" : "interviews"} this week</span>
          </div>
          {weekInterviews.length === 0 ? (
            <div className="interview-calendar-empty">
              <div className="interview-calendar-empty-mark" aria-hidden="true"><CalendarDays size={22} /></div>
              <div>
                <h4>
                  {allInterviews.length === 0
                    ? "No interviews scheduled yet"
                    : interviews.length === 0
                      ? `No ${tab.toLowerCase()} interviews found`
                      : `No ${tab.toLowerCase()} interviews this week`}
                </h4>
                <p>
                  {allInterviews.length === 0
                    ? "Schedule a conversation with a candidate to start building your interview calendar."
                    : interviews.length === 0
                      ? "Try another interview status or schedule a new conversation."
                      : "There are interviews in this status outside the selected week. Use the arrows to browse or return to today."}
                </p>
              </div>
              {tab === "Scheduled" && (
                <button className="primary" onClick={() => navigate("/interviews/schedule")}>
                  <Plus size={17} /> Schedule interview
                </button>
              )}
            </div>
          ) : (
            <div className="interview-calendar-grid">
              {weekDays.map((day) => {
                const dateKey = localDateKey(day);
                const { weekday, day: dayNumber } = formatCalendarDay(day);
                const dayInterviews = interviewsByDay.get(dateKey) || [];
                return (
                  <section className="interview-calendar-day" key={dateKey} aria-labelledby={`interview-day-${dateKey}`}>
                    <h4 id={`interview-day-${dateKey}`}>
                      <span>{weekday}</span>
                      <strong>{dayNumber}</strong>
                    </h4>
                    <div className="interview-calendar-day-events">
                      {dayInterviews.length
                        ? dayInterviews.map(renderInterviewCard)
                        : <p className="interview-calendar-no-events">No interviews</p>}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </section>
      ) : (
        <div className="panel table-panel">
          <div className="panel-title" style={{ padding: "18px 22px 0" }}>
            <h3>{panelTitle}</h3>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Position</th>
                  <th>Type</th>
                  <th>Date &amp; Time</th>
                  <th>Interviewers</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((i) => (
                  <tr key={i.id}>
                    <td>
                      <div className="candidate-cell">
                        <div className="mini-avatar">
                          {i.candidateName
                            .split(" ")
                            .map((x) => x[0])
                            .join("")
                            .slice(0, 2)}
                        </div>
                        <strong>{i.candidateName}</strong>
                      </div>
                    </td>
                    <td>{i.job}</td>
                    <td>
                      <span className={`badge badge-${TYPE_TONE[i.type] || "grey"}`}>{i.type}</span>
                    </td>
                    <td>
                      <div className="date-time-cell">
                        <strong>{i.date}</strong>
                        <span>{i.time}</span>
                      </div>
                    </td>
                    <td>
                      <div className="interviewer-list">
                        {(i.interviewers || []).map((iv) => (
                          <span key={iv.name}>
                            {iv.name} {iv.role ? <em>({iv.role})</em> : null}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <Badge status={i.status} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          type="button"
                          className="btn btn-secondary btn-small"
                          onClick={() => navigate(`/interviews/${i.id}/feedback`)}
                        >
                          {i.status === "Completed" ? "View Feedback" : "Open Workspace"}
                        </button>
                        {i.status === "Scheduled" && (
                          <button
                            type="button"
                            title="Cancel"
                            className="danger"
                            onClick={() => setCancelTarget(i)}
                          >
                            <XCircle size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!interviews.length && (
            <EmptyState
              message={
                allInterviews.length === 0
                  ? "No interviews scheduled yet. Use Schedule Interview to book the first conversation."
                  : `No ${tab.toLowerCase()} interviews found. Try another interview tab or schedule an interview.`
              }
              action={tab === "Scheduled" ? (
                <button className="primary" onClick={() => navigate("/interviews/schedule")}>
                  <Plus size={16} /> Schedule interview
                </button>
              ) : null}
            />
          )}
        </div>
      )}

      <Modal open={!!cancelTarget} title="Cancel interview?" onClose={() => setCancelTarget(null)}>
        <p>
          Cancel the interview with <strong>{cancelTarget?.candidateName}</strong> on{" "}
          {cancelTarget?.date} at {cancelTarget?.time}? This can't be undone.
        </p>
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={() => setCancelTarget(null)}>
            Keep it
          </button>
          <button className="btn btn-danger" onClick={confirmCancel} disabled={cancelling}>
            {cancelling ? "Cancelling..." : "Cancel Interview"}
          </button>
        </div>
      </Modal>
    </section>
  );
}

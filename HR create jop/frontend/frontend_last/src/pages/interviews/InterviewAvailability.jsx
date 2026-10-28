import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarDays, Clock3, Plus, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import {
  getInterviewers,
  getPublishedAvailability,
  publishInterviewAvailability,
  withdrawInterviewAvailability,
} from "../../services/interviewService";

function monthDate(year, month, day = 1) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function calendarCells(month) {
  const offset = new Date(month.getFullYear(), month.getMonth(), 1).getDay();
  const count = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  return [...Array.from({ length: offset }, () => null), ...Array.from({ length: count }, (_, i) => i + 1)];
}

function monthBounds(month) {
  return {
    startDate: monthDate(month.getFullYear(), month.getMonth()),
    endDate: monthDate(month.getFullYear(), month.getMonth(), new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()),
  };
}

function displayDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric", year: "numeric",
  });
}

export default function InterviewAvailability() {
  const [month, setMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });
  const [interviewers, setInterviewers] = useState([]);
  const [availability, setAvailability] = useState([]);
  const [interviewerId, setInterviewerId] = useState("");
  const [selectedDate, setSelectedDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [duration, setDuration] = useState("");
  const [timezone, setTimezone] = useState(() => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [withdrawingId, setWithdrawingId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [people, blocks] = await Promise.all([
        getInterviewers(),
        getPublishedAvailability(monthBounds(month)),
      ]);
      setInterviewers(people);
      setAvailability(blocks);
      setInterviewerId((current) => current || people[0]?.id || "");
    } catch {
      setError("Could not load interviewer availability. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => { load(); }, [load]);

  const monthLabel = month.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const cells = useMemo(() => calendarCells(month), [month]);
  const today = new Date();
  const todayKey = monthDate(today.getFullYear(), today.getMonth(), today.getDate());
  const blocksByDate = useMemo(() => {
    const map = new Map();
    availability.forEach((item) => map.set(item.scheduled_date, [...(map.get(item.scheduled_date) || []), item]));
    return map;
  }, [availability]);

  const changeMonth = (offset) => {
    setSelectedDate("");
    setMessage("");
    setMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  };

  const submitAvailability = async (event) => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!interviewerId || !selectedDate) {
      setError("Choose an interviewer and a future date first.");
      return;
    }
    setSaving(true);
    try {
      await publishInterviewAvailability({
        interviewerUserId: interviewerId,
        date: selectedDate,
        startTime,
        endTime,
        durationMinutes: Number(duration),
        timezone: timezone.trim(),
      });
      setMessage(`Availability published for ${displayDate(selectedDate)}.`);
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not publish this availability.");
    } finally {
      setSaving(false);
    }
  };

  const withdraw = async (id) => {
    setError("");
    setMessage("");
    setWithdrawingId(id);
    try {
      await withdrawInterviewAvailability(id);
      setMessage("Availability withdrawn. Already-booked interviews remain scheduled.");
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not withdraw this availability.");
    } finally {
      setWithdrawingId("");
    }
  };

  if (loading && interviewers.length === 0) return <LoadingSpinner label="Loading availability tools…" />;
  if (error && interviewers.length === 0) return <ErrorState message={error} onRetry={load} />;

  return (
    <section className="availability-page">
      <div className="review-workspace-top">
        <Link className="back" to="/interviews"><ArrowLeft size={17} aria-hidden="true" /> Back to Interviews</Link>
      </div>
      <header className="availability-heading">
        <div>
          <p className="eyebrow">INTERVIEW OPERATIONS</p>
          <h1>Manage interview availability</h1>
          <p>Only the dates and times you publish here can be offered to candidates.</p>
        </div>
        <span className="availability-truth-note"><CalendarDays size={16} aria-hidden="true" /> No calendar sync</span>
      </header>

      {error && <div className="form-error" role="alert">{error}</div>}
      {message && <div className="success-message" role="status">{message}</div>}

      <div className="availability-layout">
        <section className="panel availability-calendar-panel" aria-labelledby="availability-month-title">
          <div className="candidate-booking-monthbar">
            <button type="button" className="candidate-month-arrow" aria-label="Previous month" onClick={() => changeMonth(-1)}><ArrowLeft size={17} /></button>
            <h2 id="availability-month-title" aria-live="polite">{monthLabel}</h2>
            <button type="button" className="candidate-month-arrow" aria-label="Next month" onClick={() => changeMonth(1)}><ArrowRight size={17} /></button>
          </div>
          <div className="candidate-month-grid" role="group" aria-label={`Choose an availability date in ${monthLabel}`}>
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span className="candidate-weekday" key={day}>{day}</span>)}
            {cells.map((day, index) => {
              if (!day) return <span className="candidate-day-spacer" key={`spacer-${index}`} aria-hidden="true" />;
              const key = monthDate(month.getFullYear(), month.getMonth(), day);
              const count = blocksByDate.get(key)?.length || 0;
              const past = key < todayKey;
              return (
                <button type="button" key={key} className={`candidate-month-day${count ? " has-times" : ""}${selectedDate === key ? " selected" : ""}`} aria-label={`${displayDate(key)}${count ? `, ${count} published availability blocks` : ""}`} aria-pressed={selectedDate === key} disabled={past} onClick={() => setSelectedDate(key)}>
                  <span>{day}</span>{count > 0 && <small>{count} blocks</small>}
                </button>
              );
            })}
          </div>
          <p className="availability-calendar-note">Choose any future date. The candidate calendar will show a day only when it has at least one genuinely open slot.</p>
        </section>

        <section className="panel availability-form-panel" aria-labelledby="availability-form-title">
          <p className="eyebrow">PUBLISH A TIME WINDOW</p>
          <h2 id="availability-form-title">{selectedDate ? displayDate(selectedDate) : "Select a date first"}</h2>
          <form onSubmit={submitAvailability}>
            <label>Interviewer
              <select value={interviewerId} onChange={(event) => setInterviewerId(event.target.value)} required>
                {interviewers.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
              </select>
            </label>
            {interviewers.length === 0 && (
              <p className="availability-empty" role="status">
                No interviewers are available in this organization yet. Ask an administrator to add a team member before publishing times.
              </p>
            )}
            <div className="availability-time-row">
              <label>Start time<input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} required /></label>
              <label>End time<input type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} required /></label>
            </div>
            <div className="availability-time-row">
              <label>Interview length
                <select value={duration} onChange={(event) => setDuration(event.target.value)} required>
                  <option value="" disabled>Choose a duration</option>
                  {[30, 45, 60, 90, 120].map((minutes) => <option key={minutes} value={minutes}>{minutes} minutes</option>)}
                </select>
              </label>
              <label>Time zone<input value={timezone} onChange={(event) => setTimezone(event.target.value)} required placeholder="Africa/Cairo" /></label>
            </div>
            <p className="availability-help">HERA divides this window into fixed-length appointments. Existing interviews are removed from the candidate’s choices.</p>
            <button type="submit" className="primary wide" disabled={saving || !selectedDate || interviewers.length === 0}>
              <Plus size={16} aria-hidden="true" /> {saving ? "Publishing…" : "Publish availability"}
            </button>
          </form>
        </section>
      </div>

      <section className="panel availability-list-panel" aria-labelledby="availability-list-title">
        <div className="availability-list-heading"><div><p className="eyebrow">YOUR PUBLISHED WINDOWS</p><h2 id="availability-list-title">{monthLabel}</h2></div><Clock3 size={18} aria-hidden="true" /></div>
        {availability.length === 0 ? (
          <p className="availability-empty">No availability has been published for this month. Select a date above to add a time window.</p>
        ) : (
          <ul className="availability-block-list">
            {availability.map((item) => (
              <li key={item.id}>
                <div><strong>{displayDate(item.scheduled_date)}</strong><span>{item.start_time}–{item.end_time} · {item.duration_minutes} min · {item.timezone}</span><small>{item.interviewer?.full_name || interviewers.find((person) => person.id === item.interviewer_user_id)?.name || "Interviewer"}</small></div>
                <button type="button" className="btn-secondary" onClick={() => withdraw(item.id)} disabled={withdrawingId === item.id} aria-label={`Withdraw availability for ${displayDate(item.scheduled_date)}`}><Trash2 size={15} aria-hidden="true" />{withdrawingId === item.id ? "Withdrawing…" : "Withdraw"}</button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <p className="availability-policy-note">HERA does not read external calendars. Publish only times the interviewer has confirmed. Withdrawing a window does not cancel an interview that is already booked.</p>
    </section>
  );
}

import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { CalendarClock, Clock3, CheckCircle2, AlertCircle, ArrowLeft } from "lucide-react";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import ErrorState from "../../components/common/ErrorState";
import {
  scheduleInterview,
  getInterviewers,
  getInterviewSlots,
} from "../../services/interviewService";
import { listQuestionSets } from "../../services/interviewQuestionSetService";
import { getCandidates } from "../../services/candidateService";
import { getJobs } from "../../services/jobService";

const TIME_SLOTS = ["10:00 AM", "11:00 AM", "01:00 PM", "02:00 PM"];
const DURATION_OPTIONS = [
  { value: "30", label: "30 min" },
  { value: "45", label: "45 min" },
  { value: "60", label: "60 min" },
  { value: "90", label: "90 min" },
  { value: "120", label: "120 min" },
];

// "1:30 PM" -> 810 (minutes since midnight) — mirrors the backend helper.
function toMinutes(value) {
  const match = String(value).match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!match) return null;
  let hours = Number(match[1]) % 12;
  if (match[3].toUpperCase() === "PM") hours += 12;
  return hours * 60 + Number(match[2]);
}

// The next four weekdays, computed from today — UTC dates avoid timezone drift.
function nextWeekdays(count = 4) {
  const days = [];
  const current = new Date();
  current.setUTCHours(0, 0, 0, 0);
  while (days.length < count) {
    const dow = current.getUTCDay();
    if (dow !== 0 && dow !== 6) {
      days.push({
        date: current.toISOString().slice(0, 10),
        day: current.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" }),
        label: String(current.getUTCDate()).padStart(2, "0"),
        month: current.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" }).toUpperCase(),
      });
    }
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return days;
}

const INTERVIEW_DAYS = nextWeekdays();

function formatDateLabel(iso) {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-US", { day: "2-digit", month: "short", year: "numeric" });
}

export default function ScheduleInterview() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const applicationId = searchParams.get("applicationId");
  const presetQuestionSetId = searchParams.get("questionSetId");

  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [interviewers, setInterviewers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [candidateId, setCandidateId] = useState(state?.candidate?.id ? String(state.candidate.id) : "");
  const [jobId, setJobId] = useState("");
  const [interviewer, setInterviewer] = useState("");
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedTime, setSelectedTime] = useState("");

  const [questionSets, setQuestionSets] = useState([]);
  const [questionSetId, setQuestionSetId] = useState(presetQuestionSetId || "");
  const [duration, setDuration] = useState("60");

  const [occupied, setOccupied] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);

  const loadOptions = () => {
    setLoading(true);
    setLoadError(false);
    Promise.all([getCandidates(), getJobs(), getInterviewers()])
      .then(([cands, jobList, interviewerList]) => {
        setCandidates(cands);
        setJobs(jobList);
        setInterviewers(interviewerList);
        if (state?.candidate?.jobId) setJobId(String(state.candidate.jobId));
        setLoading(false);
      })
      .catch(() => {
        setLoadError(true);
        setLoading(false);
      });
  };

  useEffect(loadOptions, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load the application's question sets so HR can attach an approved one.
  useEffect(() => {
    let active = true;
    if (!applicationId) {
      setQuestionSets([]);
      return undefined;
    }
    listQuestionSets(applicationId)
      .then(({ questionSets: sets }) => {
        if (!active) return;
        setQuestionSets(sets);
        const approved = sets.filter((s) => s.status === "approved");
        const preset = sets.find(
          (s) => String(s.id) === String(presetQuestionSetId) && s.status === "approved"
        );
        setQuestionSetId(preset ? preset.id : approved[0]?.id || "");
      })
      .catch(() => {
        if (active) setQuestionSets([]);
      });
    return () => {
      active = false;
    };
  }, [applicationId, presetQuestionSetId]);

  // Pull the interviewer's occupied windows for the picked day.
  useEffect(() => {
    let active = true;
    setOccupied([]);
    setSlotsError("");
    if (!selectedDate || !interviewer) {
      return undefined;
    }
    setSlotsLoading(true);
    getInterviewSlots(selectedDate, interviewer)
      .then((result) => {
        if (!active) return;
        setOccupied(result.occupied || []);
      })
      .catch(() => {
        if (active) setSlotsError("Could not load availability for this day.");
      })
      .finally(() => {
        if (active) setSlotsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedDate, interviewer]);

  const selectedCandidate = useMemo(
    () => candidates.find((c) => String(c.id) === String(candidateId)),
    [candidates, candidateId]
  );
  const selectedJob = useMemo(() => jobs.find((j) => String(j.id) === String(jobId)), [jobs, jobId]);
  const selectedInterviewer = useMemo(
    () => interviewers.find((i) => String(i.id) === String(interviewer)),
    [interviewers, interviewer]
  );
  const selectedQuestionSet = useMemo(
    () => questionSets.find((s) => String(s.id) === String(questionSetId)),
    [questionSets, questionSetId]
  );

  const isBlocked = (time) => {
    const start = toMinutes(time);
    if (start === null) return false;
    const end = start + Number(duration);
    return occupied.some((slot) => start < slot.endMinutes && slot.startMinutes < end);
  };

  const selectedSlotBlocked = useMemo(() => {
    if (!selectedTime) return false;
    return isBlocked(selectedTime);
  }, [selectedTime, occupied, duration]); // eslint-disable-line react-hooks/exhaustive-deps

  // If availability loaded and clears our pick, drop the conflict.
  useEffect(() => {
    if (selectedTime && selectedSlotBlocked) setSelectedTime("");
  }, [selectedSlotBlocked]); // eslint-disable-line react-hooks/exhaustive-deps

  const approvedSets = questionSets.filter((s) => s.status === "approved");

  const onCandidateChange = (e) => {
    const id = e.target.value;
    setCandidateId(id);
    const cand = candidates.find((c) => String(c.id) === String(id));
    if (cand?.jobId) setJobId(String(cand.jobId));
  };

  const handleConfirm = async () => {
    setError("");
    if (!candidateId) return setError("Please select a candidate.");
    if (!jobId) return setError("Please select a job.");
    if (!interviewer) return setError("Please select an interviewer.");
    if (!selectedDate || !selectedTime) return setError("Please select a date and time.");
    if (selectedSlotBlocked) return setError("That time conflicts with an existing interview. Pick another slot.");
    if (!selectedCandidate || !selectedJob) return setError("Please select a candidate and job first.");

    setSubmitting(true);
    try {
      const result = await scheduleInterview({
        candidate: selectedCandidate,
        job: selectedJob,
        interviewer,
        date: selectedDate,
        time: selectedTime,
        durationMinutes: Number(duration),
        questionSetId: questionSetId || null,
      });
      setSuccess(result);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner label="Loading scheduling options..." />;
  if (loadError) {
    return (
      <ErrorState message="Unable to load scheduling options. Please try again." onRetry={loadOptions} />
    );
  }

  if (success) {
    return (
      <section className="schedule-page">
        <div className="panel success-card schedule-success-card">
          <div className="success-icon">
            <CheckCircle2 size={30} />
          </div>
          <h2>Interview Scheduled</h2>
          <div className="appointment-card schedule-success-details">
            <div>
              <span>Date</span>
              <strong>{formatDateLabel(selectedDate)}</strong>
            </div>
            <div>
              <span>Time</span>
              <strong>{selectedTime}</strong>
            </div>
            <div>
              <span>Duration</span>
              <strong>{duration} min</strong>
            </div>
            <div>
              <span>Candidate</span>
              <strong>{selectedCandidate?.name}</strong>
            </div>
          </div>
          <p className="muted-note">
            {selectedJob?.title} · Interviewer: {selectedInterviewer?.name || ""}
            {selectedQuestionSet ? ` · v${selectedQuestionSet.versionNumber} question set` : ""}
          </p>
          <div className="modal-actions">
            <button className="primary" onClick={() => navigate("/interviews")}>
              Back to Interviews
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="schedule-page">
      <header className="schedule-page-heading">
        <div>
          <p className="eyebrow">INTERVIEW SCHEDULING</p>
          <h2>Plan an interview</h2>
          <p>Choose the people and a time. HERA will check the selected interviewer’s calendar for conflicts.</p>
        </div>
        <button className="btn btn-secondary schedule-back-button" type="button" onClick={() => navigate("/interviews")}>
          <ArrowLeft size={16} /> Back to interviews
        </button>
      </header>

      <div className="schedule-layout">
        <div className="schedule-main">
          <section className="panel schedule-card" aria-labelledby="schedule-details-title">
            <div className="schedule-card-heading">
              <span className="schedule-step">1</span>
              <div>
                <h3 id="schedule-details-title">Interview details</h3>
                <p>Select the candidate, role, interviewer, and meeting length.</p>
              </div>
            </div>

            <div className="schedule-fields-grid">
              <label>
                Candidate
                <select value={candidateId} onChange={onCandidateChange}>
                  <option value="">Select a candidate...</option>
                  {candidates.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.name}{candidate.title ? ` — ${candidate.title}` : ""}
                    </option>
                  ))}
                </select>
                {candidates.length === 0 && (
                  <span className="schedule-field-help">No candidates are available. Add one through Screening first.</span>
                )}
              </label>

              <label>
                Job
                <select value={jobId} onChange={(event) => setJobId(event.target.value)}>
                  <option value="">Select a job...</option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>{job.title}</option>
                  ))}
                </select>
                {jobs.length === 0 && <span className="schedule-field-help">Create a job before scheduling its interview.</span>}
              </label>

              <label>
                Interviewer
                <select value={interviewer} onChange={(event) => setInterviewer(event.target.value)}>
                  <option value="">Select an interviewer...</option>
                  {interviewers.map((person) => (
                    <option key={person.id} value={person.id}>{person.name}</option>
                  ))}
                </select>
                {interviewers.length === 0 && (
                  <span className="schedule-field-help">No interviewers are available for this workspace.</span>
                )}
              </label>

              <label>
                Duration
                <select value={duration} onChange={(event) => setDuration(event.target.value)}>
                  {DURATION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>

              {applicationId && (
                <label className="schedule-question-field">
                  Approved question set <span className="schedule-optional">Optional</span>
                  <select value={questionSetId} onChange={(event) => setQuestionSetId(event.target.value)}>
                    {approvedSets.length === 0 && <option value="">No approved question set</option>}
                    {approvedSets.map((set) => (
                      <option key={set.id} value={set.id}>
                        v{set.versionNumber} · {set.questions.length} questions
                      </option>
                    ))}
                  </select>
                  <span className="schedule-field-help">
                    {approvedSets.length > 0
                      ? "Only approved question sets can be attached."
                      : "Generate and approve a question set first, or schedule without one."}
                  </span>
                </label>
              )}
            </div>
          </section>

          <section className="panel schedule-card" aria-labelledby="schedule-time-title">
            <div className="schedule-card-heading">
              <span className="schedule-step">2</span>
              <div>
                <h3 id="schedule-time-title">Choose a date and time</h3>
                <p>Showing the next four weekdays. Times use your local timezone.</p>
              </div>
            </div>

            <div className="schedule-subsection">
              <h4>Date</h4>
              <div className="date-grid schedule-date-grid" role="group" aria-label="Interview date">
                {INTERVIEW_DAYS.map((item) => (
                  <button
                    key={item.date}
                    className={`date-option ${selectedDate === item.date ? "selected" : ""}`}
                    onClick={() => {
                      setSelectedDate(item.date);
                      setError("");
                    }}
                    aria-pressed={selectedDate === item.date}
                    type="button"
                  >
                    <span>{item.month}</span>
                    <strong>{item.label}</strong>
                    <small>{item.day}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="schedule-subsection">
              <div className="schedule-subsection-heading">
                <h4>Time</h4>
                <span>Availability is checked after choosing an interviewer and date.</span>
              </div>
              <div className="time-grid schedule-time-grid" role="group" aria-label="Interview time">
                {TIME_SLOTS.map((time) => {
                  const blocked = isBlocked(time);
                  return (
                    <button
                      key={time}
                      className={`time-option ${selectedTime === time ? "selected" : ""}`}
                      onClick={() => {
                        if (blocked) return;
                        setSelectedTime(time);
                        setError("");
                      }}
                      disabled={blocked}
                      aria-pressed={selectedTime === time}
                      title={blocked ? "Conflicts with an existing interview" : undefined}
                      type="button"
                    >
                      <Clock3 size={14} /> {time}
                    </button>
                  );
                })}
              </div>
              {slotsLoading && <p className="schedule-inline-status" role="status">Checking interviewer availability…</p>}
              {slotsError && (
                <p className="schedule-inline-status schedule-inline-error" role="alert">
                  <AlertCircle size={14} /> {slotsError}
                </p>
              )}
              {!slotsLoading && !slotsError && occupied.length > 0 && (
                <p className="schedule-inline-status" role="status">
                  {occupied.length} occupied window{occupied.length > 1 ? "s" : ""} for this interviewer on this date. Conflicting times are disabled.
                </p>
              )}
            </div>
          </section>
        </div>

        <aside className="panel schedule-summary" aria-labelledby="schedule-summary-title">
          <div className="schedule-summary-icon"><CalendarClock size={20} /></div>
          <h3 id="schedule-summary-title">Appointment summary</h3>
          <p className="schedule-summary-intro">
            {selectedDate && selectedTime
              ? "Review the details before confirming."
              : "Your selections will appear here as you build the appointment."}
          </p>
          <dl className="schedule-summary-list">
            <div><dt>Candidate</dt><dd>{selectedCandidate?.name || "Not selected"}</dd></div>
            <div><dt>Position</dt><dd>{selectedJob?.title || "Not selected"}</dd></div>
            <div><dt>Interviewer</dt><dd>{selectedInterviewer?.name || "Not selected"}</dd></div>
            <div><dt>Date</dt><dd>{selectedDate ? formatDateLabel(selectedDate) : "Not selected"}</dd></div>
            <div><dt>Time</dt><dd>{selectedTime ? `${selectedTime} · ${duration} min` : "Not selected"}</dd></div>
            {applicationId && <div><dt>Question set</dt><dd>{selectedQuestionSet ? `v${selectedQuestionSet.versionNumber}` : "Not attached"}</dd></div>}
          </dl>

          {selectedSlotBlocked && <p className="schedule-inline-error" role="alert">This time conflicts with another interview. Choose a different slot.</p>}
          {error && <div className="form-error schedule-form-error" role="alert">{error}</div>}
          <button
            className="primary wide schedule-submit"
            onClick={handleConfirm}
            disabled={submitting || selectedSlotBlocked}
          >
            {submitting ? "Scheduling…" : "Confirm & schedule"}
          </button>
          <p className="schedule-human-note">You’ll review the appointment details here before it is saved.</p>
        </aside>
      </div>
    </section>
  );
}

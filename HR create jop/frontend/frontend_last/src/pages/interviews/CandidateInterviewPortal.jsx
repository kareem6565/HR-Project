import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, ArrowLeft, ArrowRight, CalendarDays, CheckCircle2, Clock3, RefreshCw, ShieldCheck } from "lucide-react";
import {
  bookCandidateInterview,
  getCandidateInterviewMonth,
  getCandidateInterviewPreview,
  rescheduleCandidateInterview,
} from "../../services/candidateInterviewPortalService";

function monthStartKey(value) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-01`;
}

function dateKey(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function getMonthCells(month) {
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const firstWeekday = new Date(year, monthIndex, 1).getDay();
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  return [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];
}

function formatDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function readToken() {
  if (typeof window === "undefined") return "";
  return window.location.hash.slice(1).trim();
}

function futureSlots(slots) {
  const now = Date.now();
  return slots.filter((slot) => {
    const start = Date.parse(slot.start_at || "");
    return Number.isFinite(start) && start > now;
  });
}

export default function CandidateInterviewPortal() {
  const token = useMemo(readToken, []);
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [invitation, setInvitation] = useState(null);
  const invitationRef = useRef(null);
  const [slots, setSlots] = useState([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [booking, setBooking] = useState(false);
  const [error, setError] = useState("");
  const [slotLoadError, setSlotLoadError] = useState("");
  const [rescheduleMode, setRescheduleMode] = useState(false);
  const [bookingSuccess, setBookingSuccess] = useState("");

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      setError("This scheduling link is missing or invalid. Ask your recruiter for a new link.");
      return;
    }
    setLoading(true);
    setError("");
    setSlotLoadError("");
    let previewLoaded = !!invitationRef.current;
    try {
      if (!previewLoaded) {
        const preview = await getCandidateInterviewPreview(token);
        previewLoaded = true;
        invitationRef.current = preview;
        setInvitation(preview);
      }
      if (invitationRef.current?.status === "booked" && !invitationRef.current?.can_reschedule) {
        setSlots([]);
        setSelectedDate("");
        setLoading(false);
        return;
      }
      const monthSlots = futureSlots(await getCandidateInterviewMonth(token, monthStartKey(month)));
      setSlots(monthSlots);
      setSelectedDate((current) =>
        current && monthSlots.some((slot) => slot.date === current) ? current : "",
      );
      setSelectedSlot(null);
    } catch (err) {
      if (previewLoaded) {
        setSlots([]);
        setSlotLoadError(err?.response?.data?.detail || "Could not load this month’s available times. Try again.");
      } else {
        setError(err?.response?.data?.detail || "Could not verify this scheduling link. Check your connection or ask the recruiter for help.");
      }
    } finally {
      setLoading(false);
    }
  }, [month, token]);

  useEffect(() => {
    load();
  }, [load]);

  const todayKey = dateKey(new Date().getFullYear(), new Date().getMonth(), new Date().getDate());
  const slotsByDate = useMemo(() => {
    const grouped = new Map();
    slots.forEach((slot) => grouped.set(slot.date, [...(grouped.get(slot.date) || []), slot]));
    return grouped;
  }, [slots]);
  const monthCells = useMemo(() => getMonthCells(month), [month]);
  const monthLabel = month.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const visibleSlots = selectedDate ? slotsByDate.get(selectedDate) || [] : [];
  const booked = invitation?.status === "booked";
  const canReschedule = !!invitation?.can_reschedule;

  const changeMonth = (offset) => {
    setSelectedDate("");
    setSelectedSlot(null);
    setSlots([]);
    setMonth((current) => new Date(current.getFullYear(), current.getMonth() + offset, 1));
  };

  const handleBooking = async () => {
    if (!selectedSlot || booking) return;
    setBooking(true);
    setError("");
    setBookingSuccess("");
    try {
      const wasRescheduling = booked && rescheduleMode && invitation?.interview_id;
      let confirmation;
      if (wasRescheduling) {
        confirmation = await rescheduleCandidateInterview({
          token,
          interviewId: invitation.interview_id,
          availabilityId: selectedSlot.availability_id,
          scheduledTime: selectedSlot.start_time,
        });
      } else {
        confirmation = await bookCandidateInterview({
          token,
          availabilityId: selectedSlot.availability_id,
          scheduledTime: selectedSlot.start_time,
        });
      }
      const updatedInvitation = {
        ...invitationRef.current,
        // Candidate portal invitation becomes booked after a successful booking/reschedule.
        status: "booked",
        interview_id: confirmation.interview_id || invitationRef.current?.interview_id,
        scheduled_date: confirmation.scheduled_date,
        scheduled_time: confirmation.scheduled_time,
        scheduled_duration_minutes: confirmation.scheduled_duration_minutes,
        timezone: confirmation.timezone,
        can_reschedule: true,
      };
      invitationRef.current = updatedInvitation;
      setInvitation(updatedInvitation);
      setSelectedSlot(null);
      setSelectedDate("");
      setRescheduleMode(false);
      setSlots([]);
      setSlotLoadError("");
      setBookingSuccess(wasRescheduling
        ? "Interview rescheduled successfully. Your previous time has been replaced."
        : "Interview booked successfully. Your time is confirmed.");
    } catch (err) {
      const message = err?.response?.data?.detail || "That time could not be booked. Try another time or refresh the page.";
      setError(message);
      setSlotLoadError("");
      // Refresh slots without clearing the booking error so the user sees what happened.
      try {
        if (token) {
          const monthSlots = futureSlots(await getCandidateInterviewMonth(token, monthStartKey(month)));
          setSlots(monthSlots);
          setSelectedDate((current) =>
            current && monthSlots.some((slot) => slot.date === current) ? current : "",
          );
          setSelectedSlot(null);
        }
      } catch {
        // Keep the original booking error visible.
      }
    } finally {
      setBooking(false);
    }
  };

  if (loading && !invitation) {
    return <main className="candidate-booking-shell"><section className="candidate-booking-card" role="status">Loading your interview options…</section></main>;
  }

  if (error && !invitation) {
    return (
      <main className="candidate-booking-shell">
        <section className="candidate-booking-card" aria-labelledby="candidate-booking-error">
          <div className="candidate-booking-brand">HERA <span>Interview scheduling</span></div>
          <div className="candidate-booking-error-icon"><AlertCircle aria-hidden="true" /></div>
          <h1 id="candidate-booking-error">We couldn’t open this link</h1>
          <p role="alert">{error}</p>
          <button type="button" className="btn-secondary" onClick={load}>Try again</button>
          <p className="candidate-booking-footnote">If the link has expired, contact the recruiter who invited you for a replacement.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="candidate-booking-shell">
      <section className="candidate-booking-card" aria-labelledby="candidate-booking-title">
        <div className="candidate-booking-brand">HERA <span>Interview scheduling</span></div>
        <div className="candidate-booking-heading">
          <div className="candidate-booking-icon"><CalendarDays aria-hidden="true" /></div>
          <div>
            <p className="eyebrow">A PRIVATE SCHEDULING PAGE</p>
            <h1 id="candidate-booking-title">{booked ? "Your interview is scheduled" : "Choose an interview time"}</h1>
            <p>{invitation?.job_title || "Interview"}{invitation?.department ? ` · ${invitation.department}` : ""}</p>
          </div>
        </div>

        {error && <div className="candidate-booking-inline-error" role="alert"><AlertCircle size={16} />{error}</div>}
        {bookingSuccess && <div className="candidate-booking-success" role="status">{bookingSuccess}</div>}

        {booked && !rescheduleMode ? (
          <div className="candidate-booking-confirmation" role="status">
            <CheckCircle2 aria-hidden="true" />
            <div>
              <strong>Confirmed for {formatDate(invitation.scheduled_date)}</strong>
              <span>{invitation.scheduled_time} · {invitation.scheduled_duration_minutes} minutes · {invitation.timezone || "time zone set by recruiter"}</span>
              {canReschedule ? (
                <>
                  <p>You can reschedule this interview using the same link.</p>
                  <button type="button" className="btn-secondary" onClick={() => { setRescheduleMode(true); setError(""); setSlotLoadError(""); load(); }}>
                    <RefreshCw size={14} aria-hidden="true" /> Reschedule interview
                  </button>
                </>
              ) : (
                <p>This interview can no longer be rescheduled with this link. Contact the recruiter if you need help.</p>
              )}
            </div>
          </div>
        ) : (
          <>
            {rescheduleMode && booked && (
              <div className="candidate-booking-inline-error" role="status">
                Rescheduling your interview. Select a new time below.
                <button type="button" className="btn-secondary" onClick={() => { setRescheduleMode(false); setSelectedDate(""); setSelectedSlot(null); setSlots([]); }}>Cancel</button>
              </div>
            )}
            <p className="candidate-booking-intro">Select a day with available times, then choose the time that works for you. Times are shown in the time zone listed beside each option.</p>
            <div className="candidate-booking-calendar">
              <div className="candidate-booking-monthbar">
                <button type="button" className="candidate-month-arrow" aria-label="Previous month" onClick={() => changeMonth(-1)}><ArrowLeft size={17} /></button>
                <h2 aria-live="polite">{monthLabel}</h2>
                <button type="button" className="candidate-month-arrow" aria-label="Next month" onClick={() => changeMonth(1)}><ArrowRight size={17} /></button>
              </div>
              <div className="candidate-month-grid" role="group" aria-label={`Days in ${monthLabel}`}>
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span className="candidate-weekday" key={day}>{day}</span>)}
                {monthCells.map((day, index) => {
                  if (!day) return <span className="candidate-day-spacer" key={`spacer-${index}`} aria-hidden="true" />;
                  const key = dateKey(month.getFullYear(), month.getMonth(), day);
                  const count = slotsByDate.get(key)?.length || 0;
                  const isPast = key < todayKey;
                  const disabled = isPast || count === 0 || (booked && !rescheduleMode);
                  return (
                    <button
                      type="button"
                      key={key}
                      className={`candidate-month-day${count ? " has-times" : ""}${selectedDate === key ? " selected" : ""}`}
                      aria-label={`${formatDate(key)}${count ? `, ${count} available times` : ", no times available"}`}
                      aria-pressed={selectedDate === key}
                      disabled={disabled}
                      onClick={() => { setSelectedDate(key); setSelectedSlot(null); }}
                    >
                      <span>{day}</span>
                      {count > 0 && <small>{count} times</small>}
                    </button>
                  );
                })}
              </div>
              {loading && <p className="candidate-booking-footnote" role="status">Checking published availability…</p>}
              {!loading && slotLoadError && <p className="candidate-booking-inline-error" role="alert">{slotLoadError}<button type="button" onClick={load}>Retry</button></p>}
              {!loading && !slotLoadError && slots.length === 0 && <p className="candidate-booking-empty">No interview times have been published for this month yet. Try another month or contact the recruiter.</p>}
            </div>

            {selectedDate && (
              <section className="candidate-time-picker" aria-labelledby="candidate-times-title">
                <h2 id="candidate-times-title">Available times · {formatDate(selectedDate)}</h2>
                <div className="candidate-time-options" role="group" aria-label="Available interview times">
                  {visibleSlots.map((slot) => {
                    const key = `${slot.availability_id}-${slot.start_time}`;
                    const selected = selectedSlot && `${selectedSlot.availability_id}-${selectedSlot.start_time}` === key;
                    return (
                      <button type="button" key={key} className={`candidate-time-option${selected ? " selected" : ""}`} aria-pressed={!!selected} onClick={() => setSelectedSlot(slot)}>
                        <Clock3 size={16} aria-hidden="true" />
                        <span>{slot.start_time}–{slot.end_time}</span>
                        <small>{slot.timezone}</small>
                      </button>
                    );
                  })}
                </div>
                <button type="button" className="primary candidate-booking-submit" onClick={handleBooking} disabled={!selectedSlot || booking}>
                  {booking ? "Saving…" : (rescheduleMode ? "Confirm new time" : "Confirm this time")}
                </button>
              </section>
            )}
          </>
        )}

        <div className="candidate-booking-privacy"><ShieldCheck size={15} aria-hidden="true" /><span>This page is only for scheduling this interview. It does not sign you in to HERA.</span></div>
      </section>
    </main>
  );
}

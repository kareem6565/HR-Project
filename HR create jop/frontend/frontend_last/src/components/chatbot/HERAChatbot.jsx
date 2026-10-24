import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, RotateCw, Send, X } from "lucide-react";
import HeraAssistantMark from "../common/HeraAssistantMark";
import {
  createThread,
  getThread,
  listThreads,
  sendMessage,
} from "../../services/chatService";

const WELCOME_MESSAGE = {
  id: "welcome",
  from: "hera",
  text: "Hi, I'm HERA. Ask about who's shortlisted, active jobs, candidates, interviews and availability, an application's review, or how the AI is performing.",
};

const SUGGESTED_PROMPTS = [
  "Who's shortlisted right now?",
  "Which jobs are active?",
  "Show interviews scheduled",
  "How is the AI doing lately?",
];

// In-app navigation derived from the tool results that grounded the reply —
// mirrors the link sections the backend compose step renders in its answer.
const TOOL_LINKS = {
  get_application_details: (r) => ({
    label: "Open Review",
    to: `/applications/${r.data?.application_id}/review`,
  }),
  get_interview_slots: () => ({ label: "Scheduler", to: "/interviews/schedule" }),
  summarize_pipeline: () => ({ label: "View Applications", to: "/applications" }),
  list_jobs: () => ({ label: "View Jobs", to: "/jobs" }),
  search_candidates: () => ({ label: "View Candidates", to: "/candidates" }),
  get_talent_pool: () => ({ label: "Talent Pool", to: "/talent-pool" }),
  list_interviews: () => ({ label: "View Interviews", to: "/interviews" }),
  get_ai_activity: () => ({ label: "View AI Activity", to: "/ai-activity" }),
};

function linksFromResults(toolResults) {
  const links = [];
  for (const result of toolResults || []) {
    const make = TOOL_LINKS[result.tool];
    if (result.ok && make) {
      const link = make(result);
      if (link && link.to && !links.some((l) => l.to === link.to)) links.push(link);
    }
  }
  return links.slice(0, 3);
}

export default function HERAChatbot({ inline = false }) {
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState([]);
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [threadLoading, setThreadLoading] = useState(false);
  const [errorRetry, setErrorRetry] = useState(null);
  const listRef = useRef(null);
  const activeThreadRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, sending, threadLoading]);

  const refreshThreads = useCallback(async () => {
    try {
      const rows = await listThreads();
      setThreads(rows);
      return rows;
    } catch {
      return [];
    }
  }, []);

  const openThread = useCallback(async (threadId) => {
    activeThreadRef.current = threadId;
    setActiveThreadId(threadId);
    setThreadLoading(true);
    setErrorRetry(null);
    try {
      const detail = await getThread(threadId);
      if (activeThreadRef.current === threadId) {
        setMessages(detail.messages.length ? detail.messages : [WELCOME_MESSAGE]);
      }
    } catch {
      if (activeThreadRef.current === threadId) setMessages([WELCOME_MESSAGE]);
    } finally {
      if (activeThreadRef.current === threadId) setThreadLoading(false);
    }
  }, []);

  const toggleOpen = async () => {
    const willOpen = !open;
    setOpen(willOpen);
    if (willOpen) {
      const rows = await refreshThreads();
      if (rows.length && !activeThreadId) openThread(rows[0].id);
    }
  };

  const newThread = () => {
    activeThreadRef.current = null;
    setActiveThreadId(null);
    setMessages([WELCOME_MESSAGE]);
    setErrorRetry(null);
  };

  const send = async (text) => {
    const trimmed = (text || "").trim();
    if (!trimmed || sending) return;

    setMessages((prev) => [
      ...prev,
      { id: `local-user-${Date.now()}`, from: "user", text: trimmed },
    ]);
    setInput("");
    setSending(true);
    setErrorRetry(null);

    try {
      let threadId = activeThreadId;
      if (!threadId) {
        const thread = await createThread();
        threadId = thread.id;
        activeThreadRef.current = threadId;
        setActiveThreadId(threadId);
        setThreads((prev) => [thread, ...prev]);
      }
      const res = await sendMessage(threadId, trimmed);
      if (activeThreadRef.current === threadId) {
        const reply = res.message;
        setMessages((prev) => [
          ...prev,
          {
            id: reply.id,
            from: "hera",
            text: reply.content,
            toolResults: reply.toolResults,
          },
        ]);
      }
      refreshThreads();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `local-error-${Date.now()}`,
          from: "hera",
          text: err.message || "Something went wrong. Try again.",
          isError: true,
        },
      ]);
      setErrorRetry(trimmed);
    } finally {
      setSending(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className={`karen-widget${inline ? " karen-widget-inline" : ""}`}>
      {open && (
        <div className="karen-panel" id="hera-assistant-panel" aria-label="HERA assistant">
          <div className="karen-header">
            <div className="karen-header-title">
              <HeraAssistantMark size={23} />
              <strong>HERA</strong>
              <span>AI Assistant</span>
            </div>
            <button type="button" className="icon-btn" onClick={() => setOpen(false)} aria-label="Close chat">
              <X size={18} />
            </button>
          </div>

          <div className="hera-threads">
            <button type="button" className="hera-new-btn" onClick={newThread}>
              <Plus size={12} /> New
            </button>
            {threads.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`hera-thread-btn ${t.id === activeThreadId ? "active" : ""}`}
                onClick={() => openThread(t.id)}
              >
                {t.title || "New chat"}
              </button>
            ))}
          </div>

          <div className="karen-messages" ref={listRef}>
            {messages.map((m) => {
              const isAssistant = m.from === "hera";
              const links = isAssistant ? linksFromResults(m.toolResults) : [];
              return (
                <div key={m.id} className={`karen-message ${m.from} ${m.isError ? "error" : ""}`}>
                  <p>{m.text}</p>
                  {isAssistant && m.toolResults?.length > 0 && (
                    <div className="hera-chips">
                      {m.toolResults.map((tr) => (
                        <span key={`${m.id}-${tr.tool}`} className={`hera-chip ${tr.ok ? "" : "failed"}`}>
                          {tr.tool}
                        </span>
                      ))}
                    </div>
                  )}
                  {links.length > 0 && (
                    <div className="karen-links">
                      {links.map((l) => (
                        <Link key={`${m.id}-${l.to}`} to={l.to} className="karen-link">
                          {l.label}
                        </Link>
                      ))}
                    </div>
                  )}
                  {m.isError && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      onClick={() => send(errorRetry)}
                    >
                      <RotateCw size={13} /> Retry
                    </button>
                  )}
                </div>
              );
            })}

            {(sending || threadLoading) && (
              <div className="karen-message hera">
                <div className="karen-typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          {messages.length <= 1 && !threadLoading && (
            <div className="karen-suggestions">
              {SUGGESTED_PROMPTS.map((p) => (
                <button key={p} type="button" onClick={() => send(p)}>
                  {p}
                </button>
              ))}
            </div>
          )}

          <form className="karen-input-row" onSubmit={onSubmit}>
            <input
              placeholder="Ask HERA anything..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending}
            />
            <button type="submit" className="icon-btn" disabled={sending || !input.trim()} aria-label="Send">
              <Send size={16} />
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        className="karen-fab"
        onClick={toggleOpen}
        aria-label={open ? "Close HERA assistant" : "Open HERA assistant"}
        aria-expanded={open}
        aria-controls={open ? "hera-assistant-panel" : undefined}
        data-tooltip="Ask HERA about jobs, candidates, interviews, or AI activity"
        title={open ? "Close HERA assistant" : "Ask HERA about jobs, candidates, interviews, or AI activity"}
      >
        {open ? <X size={21} /> : <HeraAssistantMark size={34} />}
      </button>
    </div>
  );
}

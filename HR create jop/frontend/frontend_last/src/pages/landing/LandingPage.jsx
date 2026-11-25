import React, { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import {
  FileUp, Sparkles, Target, ClipboardCheck, CalendarClock, MessagesSquare, Radar, ArrowDown,
} from "lucide-react";
import AnimatedHeraMark from "../../components/brand/AnimatedHeraMark";
import "./LandingPage.css";

// Public marketing landing page. No auth, no app chrome, no data access.
// Motion is CSS-driven; sections reveal on scroll via IntersectionObserver.

const JOURNEY = [
  {
    icon: FileUp,
    step: "01",
    title: "Drop the CVs in",
    text: "Single files or bulk batches. The dropzone comes alive on drag-over, and every file lands with a pop.",
    video: "/landing/clip-dropzone.mp4",
    alt: "CV upload dropzone glowing on drag-over with animated border",
  },
  {
    icon: Sparkles,
    step: "02",
    title: "HERA reads every CV",
    text: "Watch the analysis happen: live progress, live counts, no black box and no dead waiting screen.",
    video: "/landing/clip-scoring-live.mp4",
    alt: "Live screening progress bar with count-up statistics",
  },
  {
    icon: Target,
    step: "03",
    title: "A score you can interrogate",
    text: "Every score counts up with a ring draw, colored by band - and every point is backed by quoted CV evidence, requirement by requirement.",
    video: "/landing/clip-score-reveal.mp4",
    alt: "Match score counting up with a ring draw beside quoted CV evidence rows",
  },
  {
    icon: ClipboardCheck,
    step: "04",
    title: "Humans decide, HERA assists",
    text: "Advance, hold, or reject with weighty, unambiguous controls. Final hiring decisions always stay with HR.",
    video: "/landing/clip-decisions.mp4",
    alt: "Decision controls lighting up and an advance confirmation appearing",
  },
  {
    icon: CalendarClock,
    step: "05",
    title: "Interviews that schedule themselves",
    text: "Publish availability once; candidates pick a time from a private link. Feedback and stages tracked end to end.",
    video: "/landing/clip-interviews.mp4",
    alt: "Candidate picking an interview slot from a private scheduling link with a booking confirmation"
  },
  {
    icon: MessagesSquare,
    step: "06",
    title: "Questions built per candidate",
    text: "Generate interview question sets tailored to each application, with review guidance for interviewers.",
    video: "/landing/clip-questions.mp4",
    alt: "Per-candidate interview questions revealing one by one with interviewer guidance",
  },
  {
    icon: Radar,
    step: "07",
    title: "Source beyond your inbox",
    text: "Describe who you need in plain words. HERA searches LinkedIn-scale professional data and returns ranked, scored suggestions.",
    video: "/landing/clip-sourcing.mp4",
    alt: "Plain-language candidate search typing itself and returning sourced profile cards"
  },
  {
    icon: MessagesSquare,
    step: "08",
    title: "Ask HERA anything",
    text: "A built-in assistant that knows your pipeline. Ask in plain words which candidates are ready, what changed, or where to look next.",
    video: "/landing/clip-chatbot.mp4",
    alt: "HERA assistant chat answering a pipeline question with a tool chip and link",
  },
];

const FEATURES = [
  ["Jobs", "Structured job profiles, AI-assisted drafts, one-click LinkedIn import, public career pages."],
  ["Screening", "Bulk CV upload, per-file status, duplicate and failure handling that stays truthful."],
  ["Matching", "Candidates ranked per job with explainable bands: Must Review, Consider, Lower Priority."],
  ["Evidence", "Every AI claim links to a verbatim CV quote. No evidence, no points."],
  ["Interviews", "Availability publishing, self-scheduling links, structured feedback."],
  ["Question sets", "Per-application interview questions with interviewer review guides."],
  ["Talent pool", "Re-engage past candidates with consent tracking built in."],
  ["Sourcing", "Plain-language search for external candidates, scored like internal ones."],
  ["Analytics", "Pipeline, time-to-hire and AI activity your team can audit."],
  ["Assistant", "A chatbot that answers plain-language questions about your live pipeline and points you to the right screen."],
];

const PLANS = [
  {
    code: "starter",
    name: "Starter",
    price: "Free",
    tagline: "Your first roles, screened with real evidence.",
    features: ["3 active jobs", "50 screenings / month", "2 seats", "Talent pool & interview scheduling"],
    cta: "Start free",
    featured: false,
  },
  {
    code: "pro",
    name: "Pro",
    price: "$49",
    period: "/mo",
    tagline: "For teams screening at volume every week.",
    features: ["25 active jobs", "1,000 screenings / month", "10 seats", "OCR CV photo intake", "Priority support"],
    cta: "Choose Pro",
    featured: true,
  },
  {
    code: "business",
    name: "Business",
    price: "$199",
    period: "/mo",
    tagline: "High-volume hiring, uncapped roles.",
    features: ["Unlimited active jobs", "10,000 screenings / month", "Unlimited seats", "Audit exports", "Dedicated support"],
    cta: "Choose Business",
    featured: false,
  },
];

export default function LandingPage() {
  const rootRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("lp-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18 }
    );
    root.querySelectorAll(".lp-reveal").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // Capture/testing affordance: ?skip-hero hides the fixed hero for section screenshots.
  const skipHero = typeof window !== "undefined" && window.location.search.includes("skip-hero");

  return (
    <main className={`lp${skipHero ? " lp-nohero" : ""}`} ref={rootRef}>
      <nav className="lp-nav" aria-label="Landing">
        <span className="lp-brand"><AnimatedHeraMark size={30} /> HERA</span>
        <div className="lp-nav-links">
          <a href="#lp-journey">How it works</a>
          <a href="#lp-features">Features</a>
          <a href="#lp-pricing">Pricing</a>
          <Link to="/login" className="lp-nav-cta">Sign in</Link>
        </div>
      </nav>

      <header className="lp-hero">
        <div className="lp-aurora" aria-hidden="true" />
        <div className="lp-hero-inner">
          <div className="lp-hero-mark mascot-hero" aria-hidden="true">
            <AnimatedHeraMark size={132} />
          </div>
          <h1>Hiring that reads<br />like a story, not a spreadsheet.</h1>
          <p className="lp-hero-sub">
            HERA screens CVs with AI, shows the evidence behind every score, and keeps
            the final call where it belongs - with your team.
          </p>
          <div className="lp-hero-actions">
            <a href="#lp-journey" className="lp-btn lp-btn-gold">See the journey</a>
            <Link to="/login" className="lp-btn lp-btn-ghost">Sign in</Link>
          </div>
          <a href="#lp-journey" className="lp-scroll-hint" aria-label="Scroll to how it works">
            <ArrowDown size={18} />
          </a>
        </div>
      </header>

      <section className="lp-journey" id="lp-journey" aria-label="How HERA works">
        <h2 className="lp-section-title lp-reveal">One journey, upload to offer.</h2>
        {JOURNEY.map(({ icon: Icon, step, title, text, video, alt }) => (
          <article className="lp-step lp-reveal" key={step}>
            <div className="lp-step-copy">
              <span className="lp-step-num" aria-hidden="true">{step}</span>
              <span className="lp-step-icon" aria-hidden="true"><Icon size={22} /></span>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
            {video && (
              <div className="lp-step-media">
                <video src={video} autoPlay muted loop playsInline aria-label={alt} />
              </div>
            )}
          </article>
        ))}
      </section>

      <section className="lp-features" id="lp-features" aria-label="Features">
        <h2 className="lp-section-title lp-reveal">Everything a hiring team touches, in one place.</h2>
        <div className="lp-feature-grid">
          {FEATURES.map(([name, desc], i) => (
            <div className="lp-feature lp-reveal" key={name} style={{ "--lp-i": i }}>
              <strong>{name}</strong>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-pricing" id="lp-pricing" aria-label="Pricing">
        <h2 className="lp-section-title lp-reveal">Simple pricing that scales with your hiring.</h2>
        <p className="lp-pricing-sub lp-reveal">Every plan keeps the same promise: evidence behind every score, humans behind every decision.</p>
        <div className="lp-plan-grid">
          {PLANS.map((plan) => (
            <article className={`lp-plan lp-reveal${plan.featured ? " lp-plan-featured" : ""}`} key={plan.code}>
              {plan.featured && <span className="lp-plan-flag">Most popular</span>}
              <h3>{plan.name}</h3>
              <p className="lp-plan-price">
                {plan.price}
                {plan.period && <span>{plan.period}</span>}
              </p>
              <p className="lp-plan-tagline">{plan.tagline}</p>
              <ul>
                {plan.features.map((feature) => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
              <Link to="/login" className={`lp-btn ${plan.featured ? "lp-btn-gold" : "lp-btn-ghost"}`}>
                {plan.cta}
              </Link>
            </article>
          ))}
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-footer-inner lp-reveal">
          <h2>Ready to hire with evidence?</h2>
          <p>Talk to us about bringing HERA to your team.</p>
          <Link to="/login" className="lp-btn lp-btn-gold">Get started</Link>
        </div>
        <p className="lp-legal"><AnimatedHeraMark size={18} /> HERA Recruitment System</p>
      </footer>
    </main>
  );
}

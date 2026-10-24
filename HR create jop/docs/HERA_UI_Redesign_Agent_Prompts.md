# HERA UI/UX Redesign: Implementation Plan for Coding Agent

## هدف الملف

هذا الملف يحوّل تدقيق الواجهة إلى خطة تنفيذ عملية وصغيرة يمكن إعطاؤها لوكيل برمجي. المطلوب تحديث الواجهة النشطة في `frontend/frontend_last/` مع الاستفادة من هوية HERA البصرية الموجودة في الملفات المرجعية، من دون نقل منطق النظام القديم أو افتراض أن كل شاشة قديمة يجب أن تبقى.

**قاعدة التنفيذ:** أرسل Prompt واحدًا فقط في كل مرة. راجع الـ diff والاختبارات قبل الانتقال للذي بعده. لا تطلب من الوكيل تنفيذ الملف كله دفعة واحدة.

---

## رأي التصميم والهوية البصرية

### ما الذي نأخذه من ملفات HERA المرجعية؟

من لوحة الهوية والصور والـ pitch deck في `hera_UI.zip`، الهوية الأكثر تميّزًا هي:

- أخضر مزرق داكن كهوية أساسية، بدل المزج بين البنفسجي القديم والأخضر الداكن.
- خلفيات دافئة مائلة للكريمي، مع أسطح بيضاء/فاتحة لقراءة البيانات.
- أصفر ذهبي هادئ ولمسة أزرق سماوي كلونين مساعدين، لا كألوان نصوص أساسية.
- شخصية HERA الآلية كعنصر ودود ومساعد، تُستخدم بجرعات قليلة في الدخول، والحالات الفارغة، والمساعدة، لا في كل جدول وشاشة كثيفة.
- إحساس بصري ودود واحترافي، مع جداول عملية وتباين جيد وإجراءات واضحة.

### لوحة ألوان مقترحة

الألوان الأربعة الأولى مأخوذة من لوحة الهوية داخل الملفات التي أرسلها المستخدم. ألوان الخلفية وألوان حالات البيانات مقترحات استعمالية يلزم التحقق من تباينها عند التطبيق.

| Token | القيمة | الاستخدام |
|---|---|---|
| `--hera-teal` | `#1B3A3A` | اللون الأساسي للعلامة، التنقل، والعناصر الرئيسية |
| `--hera-teal-deep` | `#082A24` | شريط جانبي داكن، أو ترويسة/مساحة رئيسية محدودة |
| `--hera-ink` | `#292C2A` | النص الأساسي الداكن |
| `--hera-cream` | `#F5EFE2` | خلفية دافئة بجرعة هادئة، ليست خلفية كل بطاقة |
| `--hera-surface` | `#FFFFFF` | البطاقات والجداول والنماذج التي تحتاج وضوحًا عاليًا |
| `--hera-gold` | `#E9D98A` | لمسة للعلامة أو إبراز زخرفي صغير؛ لا تستخدمه لنص صغير فوق خلفية فاتحة |
| `--hera-sky` | `#6FA8B8` | لمسات ثانوية وخلفيات مساعدة؛ لا تستخدمه كنص صغير قبل التحقق من التباين |
| `--hera-border` | `#E2E5E3` | حدود هادئة مقترحة |
| `--hera-muted` | `#66736F` | نص ثانوي مقترح، يجب اختبار تباينه حسب الخلفية |
| `--evidence-supported` | `#067647` | دليل داعم على خلفية خضراء فاتحة |
| `--evidence-partial` | `#B54708` | دليل جزئي على خلفية كهرمانية فاتحة |
| `--evidence-none` | `#475467` | لم يُعثر على دليل، بلون محايد لا أحمر |
| `--decision-reject` | `#B42318` | إجراءات/نتائج الرفض فقط، وليس غياب الدليل |

**لا تجمع لوحتين أساسيتين.** عند اعتماد الهوية الجديدة، اجعل الأخضر المزرق هو اللون الرئيسي. أزل البنفسجي `#6d5ce7` تدريجيًا من المكونات التي تعدّلها، ولا تنفّذ استبدالًا شاملًا عشوائيًا في كل CSS مرة واحدة.

### الطباعة والشكل

- استخدم `Inter, system-ui, sans-serif` للإنجليزية حيث يتوفر.
- اختبر `Noto Sans Arabic` للبيانات العربية فقط إذا كانت الخطوط متوفرة ومرخصة للاستخدام؛ ملفات PDF المرجعية لا تعني أن ملفات الخطوط نفسها موجودة أو قابلة لإعادة الاستخدام.
- لا تستخدم خطوط العرض المزخرفة داخل جداول المرشحين أو النماذج.
- نص الجسم 14–16px، النص المساعد عادةً 12–13px مع تباين متوافق مع WCAG، وعناوين الصفحات 24px تقريبًا حسب المساحة.
- سلم مسافات متسق: 4، 8، 12، 16، 24، 32px. قلّل البطاقات المتداخلة والزخرفة الزائدة.
- اترك اللون الأحمر لقرار الرفض أو الخطأ الحقيقي؛ لا تستخدمه كإشارة إلى أن مرشحًا «ضعيف» أو لا يمتلك مهارة.
- أي تغيير بصري يجب ألا يغيّر API contracts أو نتائج التقييم أو صلاحيات الخادم.

### ما الذي لا نأخذه من الواجهة القديمة؟

- لا تنقل الشاشات أو تدفق الخطوات القديم حرفيًا.
- لا تنقل دلالات التقييم أو قواعد المطابقة القديمة.
- لا تنشئ ميزات لمجرد ظهورها في الـ pitch deck.
- لا تفترض أن الشات بوت أو المقابلات أو التحليلات ضمن نطاق الـ MVP.
- لا تضع رسومات الروبوت في كل شاشة، ولا تسمح للزخرفة أن تستهلك مساحة الجداول أو الأدلة.

---

## قواعد مشتركة يجب إرفاقها مع كل Prompt

انسخ هذا الجزء مع كل مهمة:

> Work only inside `frontend/frontend_last/`, except when a prompt explicitly identifies a backend dependency that must be verified but not modified. Before editing, inspect Git status and preserve all existing user changes. Verify paths and current code; do not trust old line numbers blindly. Implement only this work package. Do not rewrite the frontend, add dependencies, or refactor unrelated screens. Keep API contracts and backend security behavior unchanged. Do not invent fields or endpoints: if a needed backend capability is absent, report a dependency and leave it unimplemented. Add/update focused Vitest tests. Run the repository's actual lint, test, and build scripts where available, and report exact commands/results. Do not claim a test passed unless it was executed. Do not commit, push, deploy, or read actual secret values.

## الترتيب الموصى به

1. UI-00: تأسيس tokens والهوية البصرية الجديدة.
2. UI-01: الوصول، التركيز، التباين، والحوارات.
3. UI-02: دلالات الأدلة وألوان/نطاقات الدرجة.
4. UI-03: أخطاء واجهة صغيرة واتساق المكونات.
5. UI-04: تحسين شاشة النتائج وترتيبها حسب وظيفة واحدة.
6. UI-05: تبسيط صفحة مراجعة المرشح والتقييم.
7. UI-06: تجربة القرار البشري وسجل القرار، مع التحقق من دعم الـ backend.
8. UI-07: تحسين إدخال الملفات قبل الإرسال.
9. UI-08: واجهة معالجة الدفعات غير المتزامنة، بعد جاهزية Backend Prompt 7.
10. UI-09: تبسيط التنقل وإظهار عناصر الدور، بعد جاهزية المصادقة والـ feature flags المطلوبة.
11. UI-10: RTL/responsive والمراجعة البصرية النهائية بمتصفح فعلي.

لا تبدأ مهمة تعتمد على endpoint غير موجود. إذا لم تكن الاعتمادية جاهزة، نفّذ الأجزاء المستقلة فقط ثم اذكر الباقي كمانع منفصل.

---

# UI-00 — HERA Design Tokens and Visual Foundation

**Priority:** P1 · **Dependencies:** none · **Scope:** CSS tokens and low-risk global styling only.

### Prompt to coding agent

> Implement UI-00 only. Inspect `frontend/frontend_last/src/index.css`, the existing global tokens, shared `Button`, `Badge`, `Modal`, `DataTable`, `EmptyState`, `ErrorState`, and `LoadingSpinner` components. Use the visual references in the provided `hera_UI.zip` as a brand reference, not as a source of old application logic.
>
> Establish a coherent HERA palette based on deep teal `#1B3A3A`, deep green-teal `#082A24`, warm cream `#F5EFE2`, white surfaces, ink `#292C2A`, gold `#E9D98A`, and sky accent `#6FA8B8`. Introduce semantic CSS variables for surfaces, text, borders, primary actions, focus, and evidence/decision states. Verify contrast before using any palette color for text. Gold and sky are accents, not default small-text colors.
>
> Do not redesign screen layouts in this task. Replace the old purple primary token only in the shared/global foundation and shared components that can be safely updated without altering semantics. Avoid mass search-and-replace across the 3,000-line stylesheet. Remove duplicate token definitions only when proven safe. Keep current component behavior and API calls unchanged.
>
> Use restrained cream backgrounds with white/near-white data surfaces, not giant dark banners on every page. Reserve the robot/logo artwork for appropriate brand contexts; do not add new images or depend on external assets. Do not copy image assets from the PDFs unless an actual, licensed source file is present and is already intended for application use.
>
> Acceptance: a single authoritative token palette exists; shared primary components use the HERA teal direction; no new hard-coded brand colors are introduced in changed files when a token is appropriate; layout and behavior remain unchanged; tests/lint/build are reported.

---

# UI-01 — Accessibility Basics and Interactive Controls

**Priority:** P1 · **Dependencies:** UI-00.

### Prompt to coding agent

> Implement UI-01 only. Inspect the actual `src/index.css`, `src/components/common/Modal.jsx`, `DataTable.jsx`, `LoadingSpinner.jsx`, `ErrorState.jsx`, `PipelineActions.jsx`, `src/pages/candidates/CandidatesList.jsx`, `src/pages/matching/MatchingResults.jsx`, `src/pages/jobs/JobsList.jsx`, and `src/pages/candidates/ScreenCandidates.jsx` (verify exact paths first).
>
> Fix confirmed accessibility issues only:
> 1. Replace global `outline: none` rules with clearly visible `:focus-visible` styles using the HERA focus token. Never remove keyboard focus without an equivalent visible indicator.
> 2. Respect `prefers-reduced-motion` for spinners/animations.
> 3. Add accessible names to search/filter controls, icon-only actions, and file-removal buttons.
> 4. Make row navigation available through real links or buttons; click-only table rows must not be the sole interaction path.
> 5. Upgrade the shared modal with `role="dialog"`, `aria-modal`, an accessible title, focus placement/restoration, keyboard handling, and a safe overlay-dismiss behavior. Do not silently discard typed form data when a decision modal is accidentally dismissed.
> 6. Give loading and error messages suitable status/alert semantics; announce relevant success messages through a polite live region.
> 7. Add a skip-to-content link if the existing layout supports it cleanly.
>
> Do not add a new accessibility library. Add focused tests for accessible names, keyboard operation, focus behavior, and reduced-motion/focus style rules. Acceptance: core tasks can be navigated and operated by keyboard, and changed controls expose meaningful accessible labels.

---

# UI-02 — Honest Evidence Labels and Consistent Score Semantics

**Priority:** P1 · **Dependencies:** UI-00.

### Prompt to coding agent

> Implement UI-02 only. Inspect the actual evidence-status payloads and score groups returned by the backend before changing labels. Likely UI locations include `src/pages/review/ApplicationReview.jsx`, `src/components/common/ScoreCard.jsx`, `src/components/common/ScoreBadge.jsx`, `src/pages/jobs/JobDetails.jsx`, and `src/pages/matching/MatchingResults.jsx`.
>
> A backend evidence status of `missing` means no sufficient evidence was found in the available CV text; it must not be presented as proof that the candidate lacks the skill. Replace user-facing "Missing" wording with "No evidence found" or an equivalent concise label. Use a neutral icon and neutral styling for this state. Keep `nice_to_have` separate from error/red styling.
>
> Remove frontend-only traffic-light score thresholds such as 85/70 if they contradict the backend's authoritative `group`. Use the actual backend group values and labels after verifying them in source, e.g. `must_review`, `consider`, and `lower_priority` only if those are still the current values. Show the score as a number and a clear band label. Do not hide low-ranked candidates.
>
> Keep semantic colors distinct: supported evidence, partial evidence, no evidence, and human decision outcomes must not share misleading meanings. Do not change the backend score formula or evaluation output.
>
> Add/update tests for missing-evidence wording, neutral missing-evidence style, backend score groups, and low-score candidate visibility. Acceptance: no UI copy equates missing evidence with lack of skill; the score label/band matches backend semantics, not a separate frontend threshold.

---

# UI-03 — Small UI Consistency and Data Display Fixes

**Priority:** P2 · **Dependencies:** UI-00, UI-01.

### Prompt to coding agent

> Implement UI-03 only. Fix the small confirmed interface inconsistencies from the UI audit without redesigning entire pages.
>
> Inspect Navbar route titles and all registered routes; make page titles accurate from a single route/title map where practical. Remove or implement the inert notification bell rather than leaving a dead control. Correct heading hierarchy under the page title. Display a dash or an explicit unavailable state when an application score is `null`; never show `null%`. Replace `window.alert()` and `window.confirm()` in the named job delete flows with the existing shared modal and an inline error state. Remove the misleading "1 / 2" progress chip if no second step exists. Use the shared `Button` component in `ErrorState` if that is compatible with its current props.
>
> Do not change route logic, APIs, or delete flows' authorization behavior. Add tests for route titles, null score rendering, delete confirmation, and error states. Acceptance: no dead UI controls remain among the modified elements; empty/unknown values are displayed intentionally.

---

# UI-04 — Job-Scoped Candidate Results and Meaningful Filtering

**Priority:** P1 · **Dependencies:** UI-01, UI-02.

### Prompt to coding agent

> Implement UI-04 only. Inspect `src/pages/matching/MatchingResults.jsx`, the current matching service, route definitions, backend response contracts, and tests. Do not use stale line numbers from the audit as facts.
>
> Candidate ranking must be scoped to one selected job. If the user arrives without a job selected, show a clear job picker instead of ranking candidates from unrelated jobs together. Keep job selection, search, status, score-band filter, and sort order in URL query parameters using the existing React Router version where feasible. Use backend-provided grouping rather than invented frontend thresholds. Increase page size from 5 to 25 only after verifying that existing pagination and data loading support it; otherwise implement safe pagination consistent with the API.
>
> Keep low-priority candidates visible and reviewable, for example in a collapsible section that is closed by default but clearly labelled. A rank number must only be shown inside one selected job context. Add a compact evidence summary only from fields returned by the backend.
>
> Quick decision actions must not execute silently on an icon click. Open a confirmation/review dialog with clear action names. Check whether the existing decision endpoint and schema support a reason. If reason persistence is not supported by the backend, do not pretend it is saved and do not send an unsupported payload; report the exact backend dependency while completing independent UI improvements.
>
> Add tests for required job context, URL-persisted filters, ranking scope, low-score visibility, and decision confirmation. Acceptance: no ranking combines different jobs, refresh preserves filters, and no destructive/important decision happens from an unexplained icon-only click.

---

# UI-05 — Simplify Candidate Evaluation Review

**Priority:** P1 · **Dependencies:** UI-02, UI-04.

### Prompt to coding agent

> Implement UI-05 only. Inspect `src/pages/review/ApplicationReview.jsx` and the existing evaluation/evidence components and backend response schema. This page is currently long and repeats several representations of the same evidence. Reduce duplication without changing the evaluation logic.
>
> Create reusable components only when justified, such as `src/components/evaluation/EvaluationSummary.jsx`, `EvidenceTable.jsx`, and `LimitationsNote.jsx`.
>
> The screen should present:
> - A compact evaluation summary with the backend score/group and evaluation version where present.
> - One primary requirements/evidence table instead of separate redundant breakdown/evidence/signals sections.
> - Human-readable requirement names and categories, not internal `requirement_key` values.
> - Evidence status, source quote or evidence text if actually returned by the backend, and contribution information only if available in the response.
> - Expandable details for supporting context where useful.
> - A stable limitation note: the evaluation reflects the text extracted from the CV and absence of evidence does not prove absence of the skill.
>
> Never invent source quotes, limitations fields, weights, or backend properties. If exact quotes are not yet returned by the backend, show the available explanation honestly and report the missing capability as a dependency. Avoid raw `JSON.stringify` output and do not show technical provider names as primary user-facing content.
>
> Use CSS classes/tokens instead of adding more inline styles in the parts you change. Preserve current API requests and human decision functionality. Add tests for populated, empty, partially populated, and missing evidence data. Acceptance: one clear evidence table, no raw JSON, no internal keys, no duplicated evidence sections.

---

# UI-06 — Clear Human Decision Flow

**Priority:** P1 · **Dependencies:** UI-01, UI-04; backend decision API must be verified.

### Prompt to coding agent

> Implement UI-06 only. Inspect `src/pages/review/ApplicationReview.jsx`, `src/components/common/PipelineActions.jsx`, `src/services/reviewService.js`, `src/services/matchingService.js`, and the actual backend decision schemas/routes before making changes.
>
> Add a clear decision bar showing the current recorded status when the data is available. Use visible labelled buttons for Advance, Hold, and Reject. Make the confirm step deliberate and keyboard accessible. Show a reason field if the existing product/API supports reason persistence; do not make it mandatory unless that requirement is confirmed by the current backend contract and product requirements.
>
> Do not invent a decision-history endpoint. If an existing endpoint returns decision history, display it safely. If no such endpoint exists, show only the current decision and report that full history requires a backend task. Do not write fake history to local storage.
>
> Prevent accidental duplicate submits while the request is pending, show useful success/error feedback, and handle stale evaluation/conflict responses (such as HTTP 409) without silently overwriting a decision. A "Save & next candidate" action may use the ranked-list context if it exists; otherwise provide a safe fallback to the selected job's results page.
>
> Do not modify backend code in this UI-only task. If the backend does not expose a necessary field/contract, report a blocker rather than simulating it. Add tests for current status, reasons where supported, repeated submissions, errors, and navigation.

---

# UI-07 — Better File Selection and Pre-Submission Validation

**Priority:** P1 · **Dependencies:** UI-00, UI-01.

### Prompt to coding agent

> Implement UI-07 only in the current screening/upload page, likely `src/pages/candidates/ScreenCandidates.jsx`. Verify the actual route and backend accepted file rules first.
>
> Replace silent filtering of unsupported files with a visible selected/rejected list. Show each filename, readable file size, validation state, and a clear reason such as unsupported type or file larger than the actual configured single-file limit. Allow users to remove selected files using accessible, labelled buttons with `type="button"`. Detect identical selected files by a browser-safe local fingerprint such as name + size + lastModified only as an early UX hint; do not claim this proves server-side duplicate identity. The backend remains authoritative and computes file hashes.
>
> Do not read hidden configuration or assume the limit is 5 MB without verifying the value used by the current environment. If the frontend has no reliable shared configuration, define one explicit UI constant consistent with the documented backend default and report the risk that it can drift.
>
> Show which job is selected and display the approved criteria summary only if the existing API returns the needed information. Never fabricate criterion weights or an approval state. During a synchronous request, explain that submission is in progress and handle errors honestly; do not simulate per-file server progress when the API cannot provide it.
>
> Add tests for rejected file visibility, file-size checks, duplicate-selection hints, removal button accessibility, and rendering names from real API response fields. Acceptance: no unsupported file is silently discarded and the UI does not invent screening results.

---

# UI-08 — Async Batch Progress UI

**Priority:** P1 · **Dependencies:** backend async batch endpoints and worker are implemented and verified (backend Prompt 7).

### Prompt to coding agent

> Implement UI-08 only after verifying the actual screening batch API from the running code and its schemas. Do not assume the planned endpoint names or status values exist unchanged.
>
> Add a small `screeningBatchService.js` only if the current frontend service structure warrants it. Connect the selected job and selected files to the existing batch creation endpoint; store the returned batch ID; fetch the batch status; and show each item's filename, state, safe message, and retry action only when the server allows retry.
>
> Show truthful counts, such as processed/done, failed, and duplicate, derived from API data. Display partial success; successful candidate results must remain reviewable when another file fails. Provide a link to results scoped to the same job.
>
> Poll at a controlled interval with at most one request in flight. Stop polling when all items are in terminal states or when the component unmounts. Handle 401/403, network errors, and removed/expired batches using existing app conventions. Do not poll forever or treat network failure as batch failure.
>
> Do not implement worker logic in the frontend or duplicate backend validation. Do not fake progress. Add tests for mixed success/failure, duplicate items, retry, polling cleanup, no overlapping polls, and job-scoped navigation. If backend Prompt 7 is not complete, stop and report the exact missing API contract.

---

# UI-09 — Simplified MVP Navigation and Role-Aware Controls

**Priority:** P1 · **Dependencies:** authentication/profile API working; backend feature availability must be verified.

### Prompt to coding agent

> Implement UI-09 only. Inspect the authenticated profile/session mechanism, `src/components/layout/Sidebar.jsx`, `MainLayout.jsx`, `App.jsx`, and the actual registered routes. Do not assume the identity context or authentication storage strategy from old reports; the frontend must use whichever secure strategy is currently implemented by the backend/frontend auth task.
>
> Propose and implement a concise MVP navigation focused on Jobs, Screening, and Candidates/Applications, while preserving current working routes needed by the MVP. Group secondary tools only where they are genuinely implemented and approved for the current release. Remove or hide dead links and inert UI controls.
>
> Show administrator-only controls based on the authenticated profile returned by the backend. Treat frontend role filtering as UX only; backend authorization remains mandatory. Do not invent role values, feature flags, or endpoints. If backend feature flags are not implemented, do not claim direct routes or API capabilities are disabled; either hide navigation only with a documented reason or stop and report the dependency.
>
> Keep the chatbot out of the primary workflow unless it has a verified, approved MVP role. Do not remove its backend code or alter AI behavior in this task. Ensure collapsed sidebar items retain accessible names and active route states are clear.
>
> Add tests for role-based navigation, unknown roles, active routes, and direct-route behavior consistent with backend authorization. Acceptance: navigation reflects real application capabilities without implying that hiding a link secures an endpoint.

---

# UI-10 — Responsive/RTL Check and Final Visual QA

**Priority:** P1 before pilot · **Dependencies:** UI-00 through UI-09 as applicable; must use a real browser for visual claims.

### Prompt to coding agent

> Implement UI-10 only. First inspect the completed pages and determine whether a browser automation or screenshot tool already exists in the environment. Do not install a new dependency unless the user explicitly approves it.
>
> Verify real rendered layouts at approximately 360px, 768px, and 1280px widths using the available browser. Focus on the screening form, job-scoped results list, and application review. Record actual findings; do not claim responsive success based only on source inspection.
>
> Fix only observed problems: page-level horizontal overflow, clipped columns, unreachable row actions, sidebar navigation on small screens, unreadable text, dialogs exceeding the viewport, and upload controls that cannot be used by touch or keyboard. On narrow screens, prefer deliberate row/card transformations over forcing dense wide tables offscreen. Keep essential data and actions visible.
>
> For candidate names and evidence quotes, support bidirectional text using `dir="auto"` at data boundaries where mixed Arabic/English content occurs. Do not translate the entire application or force the whole interface RTL unless the product owner confirms a full Arabic interface is required. Preserve a logical reading order and ensure icons/actions remain in the correct places.
>
> Verify color contrast on actual surfaces, keyboard focus, reduced-motion behavior, and error/empty states. Do not add the robot illustration to dense tables; use existing brand artwork sparingly and only if it is already part of the app's assets.
>
> Report browser dimensions and pages actually inspected, screenshots if the existing test setup supports them, defects fixed, and remaining unverified cases. If no real browser is available, do not claim visual QA is complete; provide the exact checks still needed.

---

## قواعد المراجعة بعد كل Prompt

قبل الانتقال للمهمة التالية، اطلب من الوكيل أن يعرض:

1. الملفات التي تغيّرت ولماذا.
2. نتيجة الاختبارات التي شغّلها فعليًا، بالأوامر والنتائج.
3. الـ diff أو ملخصه، وأي افتراضات أو اعتماديات خلفية.
4. ما لم يستطع التحقق منه بصريًا أو بالاختبارات.

أوقف التنفيذ إذا ظهرت تغييرات غير مطلوبة في منطق الـ backend أو التقييم، أو إذا اختفى مرشح منخفض الدرجة من القائمة، أو إذا أصبحت حالة "لا دليل" تعني ضمنيًا "المرشح لا يمتلك المهارة".

## بوابة قبول عامة قبل الـ pilot

- الدخول والصلاحيات وسلامة بيانات الشركات تأتي من الـ backend، لا من إخفاء عناصر الواجهة.
- كل قرار بشري واضح ومتعمد ويمكن تتبعه وفق قدرات الـ API الفعلية.
- كل تقييم مفهوم ويمكن ربط الأدلة بما يعيده الـ backend فعلًا.
- حالة `missing` تُعرض بوصفها "لم يُعثر على دليل" لا إثباتًا لغياب المهارة.
- لا قيم درجات أو ألوان حكم متعارضة مع مجموعات الـ backend.
- لا توجد عناصر أساسية بلا تسمية قابلة للوصول بلوحة المفاتيح.
- الاختبارات والـ lint والـ build ناجحة أو موثّق بدقة ما يمنع النجاح.
- تمت مراجعة الشاشات بصريًا في متصفح حقيقي قبل إعلان اكتمال responsive QA.

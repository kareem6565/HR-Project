<?php
/**
 * index.php — Enterprise Landing Page
 */
require_once __DIR__ . '/includes/db.php';
require_once __DIR__ . '/includes/helpers.php';
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl" class="scroll-smooth">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>HERA — منصة الذكاء الاصطناعي وإدارة الموارد البشرية</title>
  <meta name="description" content="منصة متكاملة لإدارة الحضور الجغرافي، الرواتب، التوظيف الآلي، وشبكة الذكاء الاصطناعي للمؤسسات." />
  
  <!-- Google Fonts: IBM Plex Sans Arabic & Almarai -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Almarai:wght@400;700;800&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap" rel="stylesheet" />
  
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#eef2ff',
              100: '#e0e7ff',
              500: '#6366f1',
              600: '#4f46e5',
              700: '#4338ca',
            },
            accent: {
              50: '#f0f9ff',
              500: '#0ea5e9',
              600: '#0284c7',
            },
            surface: {
              white: '#FFFFFF',
              subtle: '#F8FAFC',
              muted: '#F1F5F9',
              dark: '#0f172a',
              darker: '#090d16',
            },
            heading: '#111827',
            bodytext: '#475569',
          },
          fontFamily: {
            sans: ['IBM Plex Sans Arabic', 'Almarai', 'sans-serif'],
            heading: ['Almarai', 'IBM Plex Sans Arabic', 'sans-serif'],
          }
        }
      }
    }
  </script>

  <style>
    body {
      background-color: #FFFFFF;
      color: #475569;
      font-family: 'IBM Plex Sans Arabic', sans-serif;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }
    h1, h2, h3, h4, h5, h6 {
      color: #111827;
      font-family: 'Almarai', 'IBM Plex Sans Arabic', sans-serif;
      line-height: 1.35;
    }
    .tight-heading {
      letter-spacing: -0.02em;
    }
    .tracking-badge {
      letter-spacing: 0.12em;
    }
    /* Floating & Glow Animations */
    .animate-float {
      animation: floatAnim 4s ease-in-out infinite;
    }
    .animate-glow {
      animation: glowAnim 3s ease-in-out infinite alternate;
    }
    @keyframes floatAnim {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-8px); }
    }
    @keyframes glowAnim {
      0% { box-shadow: 0 10px 30px -10px rgba(79, 70, 229, 0.2); }
      100% { box-shadow: 0 20px 40px 0px rgba(79, 70, 229, 0.4); }
    }
    /* Slanted signature style */
    .skew-badge {
      transform: skewX(-10deg);
      display: inline-block;
    }
    .skew-badge-inner {
      transform: skewX(10deg);
      display: inline-block;
    }
    .btn-slanted {
      transform: skewX(-6deg);
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .btn-slanted:hover {
      transform: skewX(-6deg) translateY(-2px);
    }
    .btn-slanted-content {
      transform: skewX(6deg);
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
    }
    /* Multi-layered Custom Shadow */
    .shadow-soft {
      box-shadow: 0 20px 40px -15px rgba(15, 23, 42, 0.08);
    }
    .shadow-elevated {
      box-shadow: 0 25px 50px -12px rgba(79, 70, 229, 0.25), 0 10px 20px -5px rgba(15, 23, 42, 0.3);
    }
    .border-subtle {
      border-color: rgba(226, 232, 240, 0.85);
    }
    .tab-btn.active {
      background: linear-gradient(135deg, #4f46e5, #4338ca);
      color: #FFFFFF;
      box-shadow: 0 6px 18px rgba(79, 70, 229, 0.35);
    }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #F8FAFC; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
  </style>
  <link rel="stylesheet" href="/BIC2_Mvp/assets/hera-brand.css" />
  <script src="/BIC2_Mvp/assets/hera-language.js" defer></script>
</head>
<body class="min-h-screen flex flex-col selection:bg-indigo-100 selection:text-indigo-900">

<!-- ══════════════════════════════════ NAVBAR ══════════════════════════════════ -->
<header class="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-subtle">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
    
    <!-- Brand Logo -->
    <a href="#" class="flex items-center gap-3">
      <img src="/BIC2_Mvp/assets/hera-logo.svg" alt="HERA" class="w-40 h-auto" />
    </a>

    <!-- Nav Links (Desktop) -->
    <nav class="hidden md:flex items-center gap-8">
      <a href="#features" class="text-sm font-semibold text-bodytext hover:text-indigo-600 transition-colors">الميزات الرئيسية</a>
      <a href="#bento" class="text-sm font-semibold text-bodytext hover:text-indigo-600 transition-colors">بنية النظام</a>
      <a href="#ai-rag" class="text-sm font-semibold text-bodytext hover:text-indigo-600 transition-colors">الذكاء الاصطناعي (RAG)</a>
      <a href="#metrics" class="text-sm font-semibold text-bodytext hover:text-indigo-600 transition-colors">المؤشرات والإحصائيات</a>
    </nav>

    <!-- CTAs -->
    <div class="flex items-center gap-3">
      <a href="/BIC2_Mvp/login.php" class="px-4 py-2.5 rounded-xl text-sm font-bold text-heading hover:bg-surface-subtle border border-subtle transition-all">
        تسجيل الدخول
      </a>
      <a href="/BIC2_Mvp/login.php" class="btn-slanted px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-md">
        <span class="btn-slanted-content">تجربة المنصة</span>
      </a>
    </div>

  </div>
</header>

<!-- ══════════════════════════════════ HERO SECTION (Split-Screen Asymmetrical) ══════════════════════════════════ -->
<section class="relative py-16 lg:py-24 bg-white overflow-hidden border-b border-subtle">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
      
      <!-- LEFT COLUMN: Content (7 Cols) -->
      <div class="lg:col-span-7 space-y-7 text-right">
        
        <!-- Slanted Signature Badge -->
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-lg bg-indigo-50 border border-indigo-100 skew-badge">
          <span class="w-2 h-2 rounded-full bg-indigo-600 animate-pulse"></span>
          <span class="text-xs font-bold uppercase tracking-badge text-indigo-700 skew-badge-inner">جيل جديد من أنظمة الحضور والذكاء الاصطناعي</span>
        </div>

        <!-- Main Headline (Resized to H2 as requested) -->
        <h2 class="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-heading tight-heading leading-snug">
          منصة إدارة الموارد البشرية والذكاء الاصطناعي للمؤسسات
        </h2>

        <!-- Subtitle -->
        <p class="text-lg sm:text-xl text-bodytext leading-relaxed max-w-2xl font-normal">
          دمج سلس بين بصمة الجغرافيا الحيوية (GPS)، إدارة الورديات الليلية، حساب الرواتب والخصومات التلقائية، وأتمتة التوظيف والـ RAG عبر بوت تليجرام و n8n.
        </p>

        <!-- CTA Action Buttons -->
        <div class="flex flex-wrap items-center gap-4 pt-2">
          <a href="/BIC2_Mvp/login.php" class="btn-slanted px-7 py-4 rounded-xl text-base font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-600/30">
            <span class="btn-slanted-content">
              <span>دخول النظام وحسابات التجربة</span>
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
            </span>
          </a>
          <a href="#bento" class="px-6 py-4 rounded-xl text-base font-bold text-heading bg-surface-subtle hover:bg-surface-muted border border-subtle transition-all flex items-center gap-2">
            استكشاف البنية التحتية
          </a>
        </div>

        <!-- Trust Metrics -->
        <div class="pt-8 border-t border-subtle grid grid-cols-3 gap-6">
          <div>
            <p class="text-2xl sm:text-3xl font-extrabold text-heading">99.9%</p>
            <p class="text-xs font-semibold text-bodytext mt-1">دقة البصمة الجغرافية</p>
          </div>
          <div>
            <p class="text-2xl sm:text-3xl font-extrabold text-indigo-600">10x</p>
            <p class="text-xs font-semibold text-bodytext mt-1">سرعة فحص السير الذاتية</p>
          </div>
          <div>
            <p class="text-2xl sm:text-3xl font-extrabold text-heading">100%</p>
            <p class="text-xs font-semibold text-bodytext mt-1">خصوصية بيانات محلية (Ollama)</p>
          </div>
        </div>

      </div>

      <!-- RIGHT COLUMN: Asymmetrical Dynamic Visual Mockup (5 Cols) — Darkened Contrast -->
      <div class="lg:col-span-5 relative animate-float">
        <div class="relative rounded-3xl bg-slate-950 p-6 border border-slate-800 shadow-elevated text-white">
          
          <!-- Mock Header Bar -->
          <div class="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full bg-red-500"></span>
              <span class="w-3 h-3 rounded-full bg-amber-500"></span>
              <span class="w-3 h-3 rounded-full bg-emerald-500"></span>
            </div>
            <span class="text-xs font-mono font-semibold text-slate-400">HERA HR Suite</span>
          </div>

          <!-- Live Visual Cards Stack -->
          <div class="space-y-4">
            
            <!-- Card 1: Geofence Active -->
            <div class="bg-slate-900/90 p-4 rounded-2xl border border-slate-800 shadow-lg flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold">
                  📍
                </div>
                <div>
                  <p class="text-xs font-bold text-white">بصمة النطاق الجغرافي (GPS)</p>
                  <p class="text-[11px] text-emerald-400 font-medium">داخل النطاق المصرح (26 متر)</p>
                </div>
              </div>
              <span class="px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold border border-emerald-500/30">حاضر ✅</span>
            </div>

            <!-- Card 2: Shift Engine -->
            <div class="bg-slate-900/90 p-4 rounded-2xl border border-slate-800 shadow-lg flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 flex items-center justify-center font-bold">
                  🌙
                </div>
                <div>
                  <p class="text-xs font-bold text-white">محرك الورديات الليلية</p>
                  <p class="text-[11px] text-slate-400">ورديات عابرة لمنتصف الليل (00:00 - 09:00)</p>
                </div>
              </div>
              <span class="px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-bold border border-indigo-500/30">شفت مسائي</span>
            </div>

            <!-- Card 3: AI RAG & Telegram Pipeline -->
            <div class="bg-slate-900/90 p-4 rounded-2xl border border-slate-800 shadow-lg space-y-3">
              <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                <span class="text-xs font-bold text-white flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                  n8n + Pinecone RAG Pipeline
                </span>
                <span class="text-[10px] font-mono text-cyan-400 font-bold">Automated</span>
              </div>
              <div class="p-3 rounded-xl bg-slate-950/80 text-xs text-slate-300 font-medium leading-relaxed border border-slate-800">
                🤖 <b>مساعد تليجرام الذكي:</b> استعلام فوري عن كشوفات الحضور، اللوائح، وحسابات الرواتب عبر Ollama Chat Model.
              </div>
            </div>

          </div>

        </div>
      </div>

    </div>
  </div>
</section>

<!-- ══════════════════════════════════ CORE CONTENT: Asymmetrical Bento Grid ══════════════════════════════════ -->
<section id="bento" class="py-20 bg-surface-subtle border-b border-subtle">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    
    <!-- Section Header -->
    <div class="text-center max-w-3xl mx-auto mb-16 space-y-4">
      <span class="text-xs font-bold uppercase tracking-badge text-indigo-600">بنية النظام والأتمتة الذكية</span>
      <h2 class="text-3xl sm:text-4xl font-extrabold text-heading tight-heading">
        منظومة هندسية متكاملة مصممة للرفع من كفاءة التشغيل
      </h2>
      <p class="text-bodytext text-base">
        بنية تحتية مرنة تجمع بين التحكم الجغرافي الميداني وأتمتة الذكاء الاصطناعي المتقدمة.
      </p>
    </div>

    <!-- ASYMMETRICAL BENTO GRID (Custom Span Sizes) -->
    <div class="grid grid-cols-1 md:grid-cols-12 gap-6">
      
      <!-- BENTO TILE 1: Geofence & Shift Engine (Span 8) -->
      <div class="md:col-span-8 bg-white rounded-3xl p-8 border border-subtle shadow-soft flex flex-col justify-between space-y-6">
        <div class="space-y-3">
          <div class="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 text-xl font-bold">
            🗺️
          </div>
          <h3 class="text-2xl font-bold text-heading">بصمة الجغرافيا الحيوية وحساب الورديات الليلية</h3>
          <p class="text-bodytext text-sm leading-relaxed max-w-xl">
            تقنية الدقة المكانية عبر معادلة Haversine لمنع التلاعب في الحضور، مع دعم كامل للورديات الليلية والعابرة لمنتصف الليل دون أي أخطاء في تواريخ العمل.
          </p>
        </div>

        <!-- Interactive Visual Demo -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-100">
          <div class="p-3.5 rounded-2xl bg-surface-subtle border border-subtle">
            <p class="text-[11px] font-semibold text-slate-400">حساب المسافة</p>
            <p class="text-base font-bold text-heading mt-0.5">خوارزمية Haversine</p>
          </div>
          <div class="p-3.5 rounded-2xl bg-surface-subtle border border-subtle">
            <p class="text-[11px] font-semibold text-slate-400">مهلة الدخول</p>
            <p class="text-base font-bold text-indigo-600 mt-0.5">Cutoff Minutes Config</p>
          </div>
          <div class="p-3.5 rounded-2xl bg-surface-subtle border border-subtle">
            <p class="text-[11px] font-semibold text-slate-400">دعم الشفتات</p>
            <p class="text-base font-bold text-emerald-600 mt-0.5">Cross-Midnight</p>
          </div>
        </div>
      </div>

      <!-- BENTO TILE 2: Autonomous Resume Screening (Span 4) -->
      <div class="md:col-span-4 bg-white rounded-3xl p-8 border border-subtle shadow-soft flex flex-col justify-between space-y-6">
        <div class="space-y-3">
          <div class="w-12 h-12 rounded-2xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 text-xl font-bold">
            📄
          </div>
          <h3 class="text-xl font-bold text-heading">أتمتة فحص السير الذاتية (AI CV Screening)</h3>
          <p class="text-bodytext text-sm leading-relaxed">
            استخراج بيانات PDF تلقائياً، تقييم المتقدمين عبر Ollama AI، وإرسال قرارات القبول والرفض عبر Gmail فوراً.
          </p>
        </div>
        <div class="p-4 rounded-2xl bg-emerald-50/50 border border-emerald-100 text-xs font-semibold text-emerald-800">
          ⚡ فحص وتصنيف مئات الطلبات في ثوانٍ معدودة بدون تدخل بشري.
        </div>
      </div>

      <!-- BENTO TILE 3: Automated Payroll & Payslip (Span 4) -->
      <div class="md:col-span-4 bg-white rounded-3xl p-8 border border-subtle shadow-soft flex flex-col justify-between space-y-6">
        <div class="space-y-3">
          <div class="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 text-xl font-bold">
            💳
          </div>
          <h3 class="text-xl font-bold text-heading">حساب الرواتب والخصومات التلقائية</h3>
          <p class="text-bodytext text-sm leading-relaxed">
            حساب أجر اليومية، خصومات التأخير والغياب الآلية، وصافي الراتب النهائي مع خيار طباعة قسيمة الراتب المفصلة (Payslip).
          </p>
        </div>
        <div class="p-4 rounded-2xl bg-amber-50/50 border border-amber-100 text-xs font-semibold text-amber-800">
          📊 ربط لحظي بين ساعات الحضور والخصومات الحسابية.
        </div>
      </div>

      <!-- BENTO TILE 4: Enterprise RAG System & Telegram (Span 8) — Darkened Card -->
      <div class="md:col-span-8 bg-slate-950 text-white rounded-3xl p-8 border border-slate-800 shadow-2xl flex flex-col justify-between space-y-6">
        <div class="space-y-3">
          <div class="w-12 h-12 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 text-xl font-bold">
            🤖
          </div>
          <h3 class="text-2xl font-bold text-white">شبكة الـ RAG والمساعد الذكي عبر تليجرام</h3>
          <p class="text-slate-300 text-sm leading-relaxed max-w-xl">
            ربط ملفات الشركة على Google Drive بـ Pinecone Vector Store وموديلات Ollama المحلية عبر مسارات أتمتة n8n، لتزويد الموظفين بمساعد ذكي يجيب عن اللوائح ويستعلم مباشرة من قاعدة البيانات.
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-3 pt-4 border-t border-slate-800">
          <span class="px-3.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-indigo-300">n8n Automation Engine</span>
          <span class="px-3.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-cyan-300">Pinecone Vector Store</span>
          <span class="px-3.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-emerald-300">Ollama Local LLM</span>
          <span class="px-3.5 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-semibold text-amber-300">Telegram Bot API</span>
        </div>
      </div>

    </div>

  </div>
</section>

<!-- ══════════════════════════════════ INTERACTIVE FEATURE SHOWCASE TABS ══════════════════════════════════ -->
<section id="features" class="py-20 bg-white border-b border-subtle">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    
    <div class="text-center max-w-3xl mx-auto mb-12 space-y-4">
      <span class="text-xs font-bold uppercase tracking-badge text-indigo-600">تجربة تفاعلية</span>
      <h2 class="text-3xl sm:text-4xl font-extrabold text-heading tight-heading">
        استكشف وظائف المنصة بالتفصيل
      </h2>
    </div>

    <!-- Tab Buttons -->
    <div class="flex flex-wrap justify-center gap-3 mb-12">
      <button onclick="switchTab('geo')" id="tab-geo" class="tab-btn active px-5 py-3 rounded-xl text-sm font-bold transition-all">
        📍 البصمة الجغرافية (GPS)
      </button>
      <button onclick="switchTab('shift')" id="tab-shift" class="tab-btn px-5 py-3 rounded-xl text-sm font-bold text-bodytext hover:bg-surface-subtle border border-subtle transition-all">
        🌙 الشفتات الليلية والمرنة
      </button>
      <button onclick="switchTab('work')" id="tab-work" class="tab-btn px-5 py-3 rounded-xl text-sm font-bold text-bodytext hover:bg-surface-subtle border border-subtle transition-all">
        📂 متابعة خط سير العمل
      </button>
      <button onclick="switchTab('payroll')" id="tab-payroll" class="tab-btn px-5 py-3 rounded-xl text-sm font-bold text-bodytext hover:bg-surface-subtle border border-subtle transition-all">
        💰 حسابات الرواتب والأجراس
      </button>
    </div>

    <!-- Tab Contents -->
    <div class="bg-surface-subtle rounded-3xl p-8 border border-subtle shadow-soft">
      
      <!-- TAB 1: GEO -->
      <div id="content-geo" class="tab-content grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        <div class="space-y-4">
          <span class="text-xs font-bold uppercase tracking-badge text-indigo-600">التحكم الميداني الجغرافي</span>
          <h3 class="text-2xl font-bold text-heading">بصمة المكان لمنع التلاعب والتأخير</h3>
          <p class="text-bodytext text-sm leading-relaxed">
            يستخدم النظام خوارزمية Haversine لحساب خطوط الطول والعرض بدقة فائقة بين موقع الموظف ومقر الشركة أو الفئة المخصصة، ويمنع تسجيل الحضور خارج النطاق المصرح به.
          </p>
          <ul class="space-y-2 text-xs font-semibold text-heading pt-2">
            <li class="flex items-center gap-2">✅ ربط النطاق الجغرافي بفئات العمل والمجموعات المختلفة.</li>
            <li class="flex items-center gap-2">✅ مزامنة تلقائية لإحداثيات المقر الرئيسي مع كافة الفئات.</li>
            <li class="flex items-center gap-2">✅ روابط مباشرة لمواقع الحضور على خرائط Google Maps.</li>
          </ul>
        </div>
        <div class="bg-white p-6 rounded-2xl border border-subtle shadow-soft space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <span class="text-xs font-bold text-heading">نموذج فحص الموقع الحقيقي</span>
            <span class="text-[11px] font-mono text-emerald-600 font-bold">30.2831° N, 31.3139° E</span>
          </div>
          <div class="p-4 rounded-xl bg-indigo-50 border border-indigo-100 text-xs text-indigo-900 font-semibold">
            📍 المسافة المحسوبة: 26 متر من مركز المقر (الحد المسموح: 300 متر).
          </div>
        </div>
      </div>

      <!-- TAB 2: SHIFT -->
      <div id="content-shift" class="tab-content hidden grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        <div class="space-y-4">
          <span class="text-xs font-bold uppercase tracking-badge text-indigo-600">المرونة في الورديات</span>
          <h3 class="text-2xl font-bold text-heading">دعم الورديات الليلية والعابرة لمنتصف الليل</h3>
          <p class="text-bodytext text-sm leading-relaxed">
            محرك مخصص يدعم الشفتات التي تبدأ ليلاً وتنتهي في صباح اليوم التالي (مثل 22:00 إلى 06:00 أو 00:00 إلى 09:00)، مع حماية السجلات من تكرار تسجيل الدخول.
          </p>
        </div>
        <div class="bg-white p-6 rounded-2xl border border-subtle shadow-soft space-y-3">
          <div class="p-3.5 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-between text-xs font-bold text-purple-900">
            <span>🌙 شفت مسائي (عابر لمنتصف الليل)</span>
            <span>00:00 - 09:00</span>
          </div>
        </div>
      </div>

      <!-- TAB 3: WORK -->
      <div id="content-work" class="tab-content hidden grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        <div class="space-y-4">
          <span class="text-xs font-bold uppercase tracking-badge text-indigo-600">توثيق الإنجازات</span>
          <h3 class="text-2xl font-bold text-heading">صفحة مستقلة لمتابعة خط سير العمل</h3>
          <p class="text-bodytext text-sm leading-relaxed">
            صفحة مخصصة ومحمية تتيح للموظفين رفع التقارير ومستندات PDF والصور، وتتيح للمدير والـ HR مراجعة الأعمال وإضافة الملاحظات فوراً.
          </p>
        </div>
        <div class="bg-white p-6 rounded-2xl border border-subtle shadow-soft space-y-3">
          <div class="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-xs font-bold">
            ✅ تم اعتماد تقرير المبيعات والمرفقات المرفوعة بنجاح.
          </div>
        </div>
      </div>

      <!-- TAB 4: PAYROLL -->
      <div id="content-payroll" class="tab-content hidden grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        <div class="space-y-4">
          <span class="text-xs font-bold uppercase tracking-badge text-indigo-600">الدقة المالية</span>
          <h3 class="text-2xl font-bold text-heading">كشوفات الرواتب والاستقطاعات الشفافة</h3>
          <p class="text-bodytext text-sm leading-relaxed">
            حسابات فورية تبيّن للموظف والإدارة تفاصيل أجر اليومية، استقطاعات الغياب والتأخير بالدقيقة، وصافي المبلغ المستحق.
          </p>
        </div>
        <div class="bg-white p-6 rounded-2xl border border-subtle shadow-soft space-y-3">
          <div class="flex items-center justify-between text-sm font-bold text-heading border-b border-slate-100 pb-2">
            <span>صافي الراتب المستحق</span>
            <span class="text-emerald-600">8,500 ريال</span>
          </div>
        </div>
      </div>

    </div>

  </div>
</section>

<!-- ══════════════════════════════════ ENTERPRISE METRICS / ROI ══════════════════════════════════ -->
<section id="metrics" class="py-20 bg-surface-subtle border-b border-subtle">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 text-center">
      
      <div class="bg-white p-8 rounded-3xl border border-subtle shadow-soft space-y-2">
        <p class="text-4xl font-black text-indigo-600 tight-heading">100%</p>
        <p class="text-xs font-bold text-heading">دقة تتبع الحضور والمواقع</p>
      </div>

      <div class="bg-white p-8 rounded-3xl border border-subtle shadow-soft space-y-2">
        <p class="text-4xl font-black text-heading tight-heading">0</p>
        <p class="text-xs font-bold text-heading">أخطاء في الشفتات الليلية</p>
      </div>

      <div class="bg-white p-8 rounded-3xl border border-subtle shadow-soft space-y-2">
        <p class="text-4xl font-black text-indigo-600 tight-heading">&lt; 3s</p>
        <p class="text-xs font-bold text-heading">زمن إجابة AI المساعد</p>
      </div>

      <div class="bg-white p-8 rounded-3xl border border-subtle shadow-soft space-y-2">
        <p class="text-4xl font-black text-emerald-600 tight-heading">24/7</p>
        <p class="text-xs font-bold text-heading">تشغيل ومراقبة مستمرة</p>
      </div>

    </div>
  </div>
</section>

<!-- ══════════════════════════════════ HIGH-IMPACT ENTERPRISE CTA — Darkened Section ══════════════════════════════════ -->
<section class="py-20 bg-white">
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="bg-slate-950 text-white rounded-3xl p-10 sm:p-14 border border-slate-800 shadow-2xl text-center space-y-6">
      
      <div class="inline-block skew-badge px-4 py-1.5 rounded-lg bg-indigo-500/20 border border-indigo-500/30">
        <span class="text-xs font-bold uppercase tracking-badge text-indigo-300 skew-badge-inner">جاهز للتجربة المباشرة؟</span>
      </div>
      
      <h2 class="text-3xl sm:text-5xl font-black text-white tight-heading max-w-2xl mx-auto">
        ابدأ الآن واكتشف قوة منصة HERA الذكية
      </h2>
      
      <p class="text-slate-300 text-base max-w-xl mx-auto font-normal">
        يمكنك دخول المنصة فوراً وتجربة بوابة الموظف، لوحة تحكم المدير، وشاشات متابعة خط سير العمل.
      </p>

      <div class="pt-4 flex flex-wrap justify-center gap-4">
        <a href="/BIC2_Mvp/login.php" class="btn-slanted px-8 py-4 rounded-xl text-base font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-600/30">
          <span class="btn-slanted-content">دخول المنصة وتسجيل الدخول 🚀</span>
        </a>
        <a href="/BIC2_Mvp/login.php" class="btn-slanted px-6 py-4 rounded-xl text-base font-bold text-white bg-slate-900 border border-slate-800 hover:bg-slate-800">
          <span class="btn-slanted-content">حسابات الدخول التجريبية</span>
        </a>
      </div>

    </div>
  </div>
</section>

<!-- ══════════════════════════════════ FOOTER ══════════════════════════════════ -->
<footer class="bg-white border-t border-subtle py-12">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-6">
    
    <div class="flex items-center gap-3">
      <img src="/BIC2_Mvp/assets/hera-logo.svg" alt="HERA" class="w-32 h-auto" />
    </div>

    <p class="text-xs text-bodytext font-medium">
      جميع الحقوق محفوظة © <?= date('Y') ?> — منصة إدارة الموارد البشرية والذكاء الاصطناعي للمؤسسات.
    </p>

  </div>
</footer>

<script>
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active', 'bg-indigo-600', 'text-white');
    btn.classList.add('text-bodytext', 'bg-transparent');
  });
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.add('hidden');
  });

  const activeBtn = document.getElementById('tab-' + tabId);
  const activeContent = document.getElementById('content-' + tabId);

  if (activeBtn && activeContent) {
    activeBtn.classList.add('active');
    activeContent.classList.remove('hidden');
  }
}
</script>

</body>
</html>

(() => {
  const cookieName = "hera_lang";
  const pairs = [
    ["Dashboard", "لوحة التحكم"], ["Jobs", "الوظائف"], ["Screening", "الفحص"],
    ["Matching Results", "نتائج المطابقة"], ["Candidates", "المرشحون"],
    ["Applications", "طلبات التقديم"], ["Interviews", "المقابلات"],
    ["Talent Pool", "قاعدة المواهب"], ["Analytics", "التحليلات"],
    ["Settings", "الإعدادات"], ["AI Activity", "نشاط الذكاء الاصطناعي"],
    ["Operations", "العمليات"], ["Admin", "المسؤول"], ["HR Manager", "إدارة الموارد البشرية"],
    ["Sign out", "تسجيل الخروج"], ["Open HR Manager", "فتح إدارة الموارد البشرية"],
    ["Skip to main content", "تجاوز إلى المحتوى الرئيسي"], ["Recruitment", "التوظيف"],
    ["AI RECRUITMENT", "التوظيف بالذكاء الاصطناعي"], ["Main navigation", "القائمة الرئيسية"],
    ["Administration", "الإدارة"], ["HR workspace", "مساحة الموارد البشرية"],
    ["HR Portal", "بوابة الموارد البشرية"], ["HR Management", "إدارة الموارد البشرية"],
    ["Leave balance available", "رصيد الإجازات المتاح"], ["Leave requests", "طلبات الإجازة"],
    ["Unread notifications", "إشعارات غير مقروءة"], ["Leaves and approvals", "الإجازات والموافقات"],
    ["New leave request", "طلب إجازة جديد"], ["Request leave", "طلب إجازة"],
    ["Payroll", "الرواتب"],
    ["Notifications", "الإشعارات"], ["Reports", "التقارير"], ["Mark notification as read", "قراءة الإشعار"], ["قراءة الإشعار", "Mark notification as read"], ["No new notifications.", "لا توجد إشعارات جديدة."], ["تعذر قراءة الإشعار", "Could not mark notification as read"], ["Employee Portal", "بوابة الموظف"],
    ["Workspaces", "مساحات العمل"], ["Logout", "تسجيل الخروج"], ["Log out", "تسجيل الخروج"],
    ["Create Job", "إنشاء وظيفة"], ["Create a job", "إنشاء وظيفة"],
    ["Create Job & Recruitment", "إنشاء وظيفة والتوظيف"], ["Manage HR", "إدارة الموارد البشرية"],
    ["Manage employees, attendance, leave and payroll.", "إدارة الموظفين والحضور والإجازات والرواتب."],
    ["Create jobs and manage candidates, screening and interviews.", "إنشاء الوظائف وإدارة المرشحين والفحص والمقابلات."],
    ["Welcome", "أهلًا"], ["Choose your workspace", "اختر مساحة العمل"],
    ["Your account gives you access to HR management or recruitment.", "حسابك يتيح لك الوصول إلى إدارة الموارد البشرية أو التوظيف."],
    ["Open recruitment", "فتح مساحة التوظيف"], ["Open HR management", "فتح إدارة الموارد البشرية"],
    ["Employee code / username", "كود الموظف / اسم المستخدم"], ["Employee code", "كود الموظف"],
    ["Password", "كلمة المرور"], ["Sign in", "تسجيل الدخول"], ["Sign in to HERA", "تسجيل الدخول إلى HERA"],
    ["Enter your employee code and password", "أدخل كود الموظف وكلمة المرور الخاصة بك"],
    ["Employee code or password is incorrect.", "كود الموظف أو كلمة المرور غير صحيحة."],
    ["Please enter your employee code and password.", "يرجى إدخال كود الموظف وكلمة المرور."],
    ["Current language", "اللغة الحالية"], ["Arabic", "العربية"], ["English", "الإنجليزية"],
    ["Available leave balance", "رصيد الإجازات المتاح"], ["My leave requests", "طلبات الإجازة الخاصة بي"],
    ["Unread notifications", "إشعارات غير مقروءة"], ["Leave requests and approvals", "الإجازات والموافقات"],
    ["Submit a request, track its status and review your balance.", "قدّم الطلب، تابع حالته، وراجع الرصيد مباشرة."],
    ["Attendance", "الحضور"],
    ["Employees", "الموظفون"], ["Categories", "الفئات"], ["Company settings", "إعدادات الشركة"],
    ["Save", "حفظ"], ["Cancel", "إلغاء"], ["Submit", "إرسال"], ["Search", "بحث"],
    ["Status", "الحالة"], ["Date", "التاريخ"], ["Name", "الاسم"], ["Actions", "الإجراءات"],
    ["Present", "حاضر"], ["Absent", "غائب"], ["Late", "متأخر"], ["Pending", "قيد الانتظار"],
    ["Approved", "مقبول"], ["Rejected", "مرفوض"], ["No data available.", "لا توجد بيانات."],
    ["No requests yet.", "لا توجد طلبات حتى الآن."], ["Loading...", "جارٍ التحميل..."],
    ["Home", "الرئيسية"], ["Profile", "الملف الشخصي"], ["Welcome back", "مرحبًا بعودتك"],
    ["Attendance and breaks", "الحضور والاستراحة"], ["Attendance history", "سجل الحضور"],
    ["Detailed profile and salary", "بروفايلي التفصيلي والراتب"], ["My profile and salary", "بروفايلي والراتب"], ["Payslips", "كشوف الراتب"],
    ["View profile", "عرض الملف الشخصي"], ["Select workspace", "اختر مساحة العمل"],
    ["Language", "اللغة"], ["Switch language", "تغيير اللغة"],
    ["Leave requests", "طلبات الإجازات"], ["My payslips", "كشوف الرواتب الخاصة بي"], ["Mark all as read", "تعليم الكل كمقروء"],
    ["Generate report", "إنشاء تقرير"], ["Download", "تنزيل"], ["Print", "طباعة"],
    ["إدارة الموارد البشرية", "HR Management"], ["مساحات العمل", "Workspaces"],
    ["الإجازات", "Leave"], ["الرواتب", "Payroll"], ["سجل الحضور", "Attendance history"], ["بروفايلي والراتب", "My profile and salary"], ["كشوف الراتب", "Payslips"],
    ["الإشعارات", "Notifications"], ["لوحة الإدارة", "Admin Dashboard"], ["بوابة الموظف", "Employee Portal"],
    ["رصيد الإجازات المتاح", "Available leave balance"], ["يوم في السنة الحالية", "Days this year"],
    ["طلبات الإجازة الخاصة بي", "My leave requests"], ["منها قيد المراجعة", "Pending review"],
    ["كل القرارات والتنبيهات هنا", "All decisions and alerts are here"],
    ["الإجازات والموافقات", "Leaves & approvals"], ["قدّم الطلب، تابع حالته، وراجع الرصيد مباشرة.", "Submit a request, track its status and review your balance."],
    ["طلب إجازة جديد", "New leave request"], ["إرسال الطلب", "Submit request"],
    ["طلبات إجازة المدير غير متاحة", "Leave requests are unavailable for administrators"],
    ["حساب مدير النظام مخصص لإدارة المنصة ولا يمكنه تقديم طلب إجازة من هذه البوابة.", "The administrator account manages the platform and cannot submit leave requests from this portal."],
    ["أرصدتي", "My balances"], ["طلباتي", "My requests"], ["النوع", "Type"], ["الفترة", "Period"],
    ["الأيام", "Days"], ["ملاحظات", "Notes"], ["فريقي", "My team"],
    ["عرض الموظفين المسندين إليك مباشرة.", "View employees assigned directly to you."],
    ["موافقات المدير / HR", "Manager / HR approvals"],
    ["طلبات الفريق تصل إلى المدير أولًا، ثم إلى الموارد البشرية للموافقة النهائية.", "Team requests go to the manager first, then HR for final approval."],
    ["الموظف", "Employee"], ["الإجازة", "Leave"], ["السبب", "Reason"], ["الإجراء", "Action"],
    ["أنواع الإجازات", "Leave types"], ["مدفوعة", "Paid"], ["موافقة مدير", "Manager approval"],
    ["حفظ نوع الإجازة", "Save leave type"], ["تعيين مدير فريق", "Assign team manager"],
    ["المدير يتابع فقط الموظفين المسندين إليه.", "Managers can only view employees assigned to them."],
    ["حفظ المدير المباشر", "Save direct manager"], ["الرواتب وكشوف الدفع", "Payroll & payslips"],
    ["الموظف يرى الكشوف المنشورة فقط.", "Employees can only see published payslips."],
    ["إضافة مكوّن قبل إنشاء المسير", "Add a payroll component before creating a run"],
    ["بدل", "Allowance"], ["مكافأة", "Bonus"], ["عمولة", "Commission"],
    ["وقت إضافي", "Overtime"], ["خصم يدوي", "Manual deduction"], ["إضافة المكوّن", "Add component"],
    ["إنشاء مسير رواتب", "Create payroll run"], ["إنشاء مسودة المسير", "Create payroll draft"],
    ["أضف البدلات والمكافآت أولًا، ثم أنشئ المسير وانشره بعد المراجعة.", "Add allowances and bonuses first, then create the payroll run and publish it after review."],
    ["مسيرات الرواتب", "Payroll runs"], ["الفترة", "Period"], ["الموظفون", "Employees"],
    ["إجمالي صافي الرواتب", "Total net payroll"], ["النشر", "Publish"], ["نشر", "Publish"], ["إصدار", "Issue"], ["حفظ / طباعة PDF", "Save / Print PDF"],
    ["التقارير", "Reports"], ["تقرير الحضور", "Attendance report"], ["تقرير الرواتب", "Payroll report"],
    ["من تاريخ", "From date"], ["إلى تاريخ", "To date"], ["تصدير", "Export"],
    ["التقارير والإحصائيات", "Reports & analytics"], ["تسجيل الخروج", "Sign out"], ["خروج", "Sign out"],
    ["مرحبًا", "Welcome"], ["مرحباً", "Welcome"], ["مرحبا", "Welcome"],
    ["تسجيل الدخول للنظام", "Sign in to HERA"], ["أدخل كود الموظف وكلمة المرور الخاصة بك", "Enter your employee code and password"],
    ["كود الموظف / اسم المستخدم", "Employee code / username"], ["كود الموظف أو كلمة المرور غير صحيحة.", "Employee code or password is incorrect."],
    ["يرجى إدخال كود الموظف وكلمة المرور.", "Please enter your employee code and password."],
    ["حسابات للتجربة المباشرة", "Demo accounts"], ["جارٍ التحقق...", "Signing in..."],
    ["العودة للواجهة التعريفية للمؤسسات (Landing Page)", "Back to company landing page"],
    ["بوابة الموظف", "Employee portal"], ["البروفايل", "Profile"],
    ["السجل", "History"], ["الراتب", "Salary"], ["الفئة ومواعيد العمل", "Category & work schedule"],
    ["شفت ليلي (عابر لمنتصف الليل)", "Night shift (crosses midnight)"], ["شفت صباحي", "Day shift"],
    ["ساعات الدوام", "Working hours"], ["وقت الاستراحة", "Break time"], ["مهلة التسجيل", "Check-in grace period"],
    ["تسجيل اليوم", "Today's attendance"], ["وقت الدخول", "Check-in"], ["وقت الخروج", "Check-out"],
    ["الاستراحة (البريك)", "Break"], ["الحالة", "Status"], ["لم يُسجَّل بعد", "Not recorded yet"],
    ["حاضر", "Present"], ["متأخر", "Late"], ["غائب", "Absent"], ["أنت خارج نطاق الشركة", "You are outside the company geofence"],
    ["سجل الحضور (آخر 30 يوماً)", "Attendance history (last 30 days)"], ["التاريخ", "Date"],
    ["المسافة", "Distance"], ["سجل الحضور والانصراف", "Attendance history"], ["سجلات آخر 30 يومًا", "Records from the last 30 days"],
    ["آخر التنبيهات والقرارات الخاصة بك", "Your latest notifications and decisions"], ["عرض الكل", "View all"], ["الإشعارات", "Notifications"],
    ["معلومات الراتب والإجازات", "Salary & leave information"],
    ["الراتب الأساسي", "Base salary"], ["أيام الإجازة السنوية", "Annual leave days"], ["تاريخ الانضمام", "Join date"],
    ["معتمد ✅", "Approved ✅"], ["طلب تعديل ⚠️", "Revision requested ⚠️"], ["تحت المراجعة ⏳", "Under review ⏳"],
    ["حذف", "Delete"], ["الرئيسية", "Home"],
    ["المعتمدة من الإدارة ✅", "Approved by management ✅"], ["طلبات التعديل ⚠️", "Revision requests ⚠️"],
    ["قيد المراجعة ⏳", "Under review ⏳"],
    ["أدخل تفاصيل العمل والمرفقات", "Enter work details and attachments"],
    ["تفاصيل وتقرير العمل المفصل", "Work details and report"], ["حالة التكليف *", "Task status *"],
    ["مكتمل 100%", "Completed 100%"], ["قيد التنفيذ", "In progress"], ["تحت مراجعة الإدارة", "Under management review"],
    ["رابط خارجي (إن وجد)", "External link (optional)"], ["مرفق ملف (مستند PDF / صور / ملفات)", "Attach file (PDF / images / files)"],
    ["الحد الأقصى لحجم الملف: 10 ميجابايت", "Maximum file size: 10 MB"], ["تسجيل الرفع والحفظ", "Upload and save"],
    ["فتح مساحة التوظيف ←", "Open recruitment →"], ["فتح إدارة الموارد البشرية ←", "Open HR management →"],
    ["أهلًا", "Welcome"], ["اختر مساحة العمل", "Choose your workspace"],
    ["حسابك يتيح لك الوصول إلى إدارة الموارد البشرية أو التوظيف.", "Your account provides access to HR management or recruitment."],
    ["إنشاء وظيفة والتوظيف", "Create Job & Recruitment"], ["إنشاء الوظائف وإدارة المرشحين والفحص والمقابلات من منصة HERA للتوظيف.", "Create jobs and manage candidates, screening and interviews in HERA Recruitment."],
    ["متابعة الموظفين والحضور والإجازات والرواتب من نظام إدارة الموارد البشرية.", "Manage employees, attendance, leave and payroll in the HR system."],
    ["التقرير الشامل والملف الشخصي", "Overview & employee profile"], ["جارٍ تحميل بيانات التقرير...", "Loading report data..."],
    ["لا توجد سجلات حضور مسجلة لـ هذا الموظف.", "No attendance records found for this employee."],
    ["صافي الراتب التقديري", "Estimated net salary"], ["بعد الخصومات المستحقة", "After applicable deductions"],
    ["الراتب الأساسي", "Base salary"], ["أجر اليوم (اليومية)", "Daily rate"], ["خصم الغياب", "Absence deduction"],
    ["خصم التأخير", "Late deduction"], ["إجمالي الخصومات المستحقة:", "Total deductions:"],
    ["الراتب الصافي المستحق:", "Net salary due:"], ["خصم يوم كامل عن كل يوم غياب + ربع يوم عن كل تأخير", "One full day deducted per absence + one quarter day per late arrival"],
    ["قوانين الشفت والمهلة", "Shift and grace period rules"], ["بداية ونهاية الدوام", "Shift start and end"],
    ["مواعيد الاستراحة (البريك)", "Break schedule"], ["مدة البريك المسموحة", "Allowed break duration"],
    ["مهلة إغلاق تسجيل الدخول", "Check-in closing grace period"], ["المسافة عن المقر", "Distance from office"],
    ["خريطة الموقع", "Location map"], ["لا توجد طلبات حتى الآن.", "No requests yet."],
    ["لا توجد إشعارات.", "No notifications."], ["لا توجد مسيرات.", "No payroll runs."],
    ["لا توجد طلبات تحتاج إجراء.", "No requests require action."], ["لا توجد كشوف منشورة حتى الآن.", "No payslips have been published yet."],
    ["تم حفظ القرار.", "Decision saved."], ["تم نشر المسير.", "Payroll run published."], ["تم إرسال الطلب.", "Request submitted."], ["تم تحديث الطلب.", "Request updated."],
    ["نظرة عامة", "Overview"], ["فئات ومجموعات العمل", "Work categories & teams"],
    ["سجلات الحضور", "Attendance records"], ["إدارة الموظفين", "Employee management"], ["بوابة HR: الإجازات والرواتب", "HR portal: leave & payroll"],
    ["إعدادات الشركة", "Company settings"], ["مدير", "Admin"], ["المود الفاتح", "Light mode"],
    ["تحديث", "Refresh"], ["معلومات الموظفين", "Employee information"],
    ["التحكم في الحضور", "Attendance controls"], ["إضافة موظف جديد", "Add new employee"],
    ["اسم الموظف", "Employee name"], ["كود الموظف", "Employee code"], ["اسم المستخدم", "Username"],
    ["رقم الهاتف", "Phone number"], ["البريد الإلكتروني", "Email"], ["كلمة المرور", "Password"],
    ["تأكيد كلمة المرور", "Confirm password"], ["اختر الفئة", "Select category"],
    ["إضافة", "Add"], ["تعديل", "Edit"], ["حفظ التعديلات", "Save changes"],
    ["إلغاء", "Cancel"], ["حذف الموظف", "Delete employee"], ["بحث عن موظف...", "Search employees..."],
    ["جميع الموظفين", "All employees"], ["إجمالي الموظفين", "Total employees"],
    ["حضور اليوم", "Today's attendance"], ["حاضر اليوم", "Present today"], ["متأخر اليوم", "Late today"],
    ["غائب اليوم", "Absent today"], ["نسبة الحضور", "Attendance rate"], ["تقرير الحضور اليومي", "Daily attendance report"],
    ["الموقع الجغرافي", "Geofence location"], ["تحديد موقع الشركة", "Set company location"],
    ["نصف القطر المسموح", "Allowed radius"], ["متر", "meters"], ["حفظ الإعدادات", "Save settings"],
    ["تفاصيل الموظف", "Employee details"], ["عرض التقرير", "View report"], ["عرض التفاصيل", "View details"],
    ["لا يوجد موظفون", "No employees"], ["لا توجد بيانات حضور", "No attendance data"],
    ["تم الحفظ بنجاح", "Saved successfully"], ["تم التحديث بنجاح", "Updated successfully"],
    ["هل أنت متأكد من الحذف؟", "Are you sure you want to delete this?"],
    ["لا توجد طلبات.", "No requests."], ["لا توجد إشعارات.", "No notifications."],
    ["موافقة", "Approve"], ["رفض", "Reject"], ["تفاصيل", "Details"], ["تعليق", "Comment"],
    ["من", "From"], ["إلى", "To"], ["اليوم", "Today"], ["هذا الشهر", "This month"],
    ["مدفوع", "Paid"], ["بدون راتب", "Unpaid"], ["لا يوجد مدير", "No manager"],
    ["المدير المباشر", "Direct manager"], ["اختيار المدير", "Select manager"],
    ["تاريخ الإصدار", "Issue date"], ["تاريخ الانتهاء", "Expiry date"], ["اختر ملفًا", "Choose file"],
    ["تنزيل الملف", "Download file"], ["عرض", "View"], ["إشعار جديد", "New notification"],
    ["تعليم الإشعارات كمقروءة", "Mark notifications as read"],
    ["اسم الشركة", "Company name"], ["معلومات الشركة", "Company information"],
    ["وقت بداية الدوام", "Work start time"], ["وقت نهاية الدوام", "Work end time"],
    ["مدة الاستراحة بالدقائق", "Break duration in minutes"], ["حفظ الإعدادات", "Save settings"],
    ["تسجيل الحضور", "Check in"], ["تسجيل الانصراف", "Check out"], ["بدء الاستراحة", "Start break"],
    ["إنهاء الاستراحة", "End break"], ["أنت داخل نطاق الشركة", "You are inside the company geofence"],
    ["جاري تحديد موقعك...", "Getting your location..."], ["تعذر تحديد الموقع", "Unable to get your location"],
    ["تقرير الحضور والغياب", "Attendance & absence report"], ["تفاصيل الرواتب", "Payroll details"],
    ["تسجيل موظف جديد", "Register new employee"], ["اسم المستخدم / كود الموظف", "Username / employee code"],
    ["حسابك يتيح لك الوصول إلى إدارة الموارد البشرية أو التوظيف.", "Your account gives you access to HR management or recruitment."],
    ["Create Job", "إنشاء وظيفة"], ["Edit Job", "تعديل الوظيفة"], ["Job Details", "تفاصيل الوظيفة"],
    ["Screen Candidates", "فحص المرشحين"], ["Candidate Details", "تفاصيل المرشح"],
    ["Application Review", "مراجعة طلب التقديم"], ["Question Set Builder", "منشئ مجموعة الأسئلة"],
    ["AI Settings", "إعدادات الذكاء الاصطناعي"], ["Schedule Interview", "جدولة مقابلة"],
    ["Interview Feedback", "ملاحظات المقابلة"], ["Interview Questions", "أسئلة المقابلة"],
    ["Overview", "نظرة عامة"], ["Hire the right people, faster.", "وظّف الأشخاص المناسبين بسرعة أكبر."],
    ["Manage jobs, screen candidates with AI, and review evaluations —", "أدر الوظائف وافحص المرشحين بالذكاء الاصطناعي وراجع التقييمات —"],
    ["all in one dashboard.", "كل ذلك من لوحة واحدة."], ["Recruitment System", "نظام التوظيف"],
    ["A clearer view of your hiring activity", "رؤية أوضح لنشاط التوظيف لديك"],
    ["Hiring activity", "نشاط التوظيف"],
    ["HERA · AI-ASSISTED, HR-LED", "HERA · ذكاء اصطناعي بقيادة الموارد البشرية"],
    ["Live totals from your current jobs and applications.", "إجماليات مباشرة للوظائف وطلبات التقديم الحالية."],
    ["All recorded applications grouped by role.", "كل طلبات التقديم المسجلة مجمعة حسب الوظيفة."],
    ["Workspace snapshot · all recorded applications", "ملخص مساحة العمل · جميع طلبات التقديم المسجلة"],
    ["Quick actions", "إجراءات سريعة"], ["Recruitment summary", "ملخص التوظيف"],
    ["Today's attendance log", "سجل الحضور اليوم"], ["Company settings", "إعدادات الشركة"],
    ["Work categories & shifts", "فئات ومجموعات العمل"], ["Today's attendance", "الحاضرون اليوم"],
    ["Present + late", "حاضر + متأخر"], ["Past shift start", "تجاوزوا وقت الشفت"],
    ["Absent employees", "الغائبون"], ["Not checked in yet", "لم يسجّلوا بعد"],
    ["Employee", "الموظف"], ["Category / shift", "الفئة / الشفت"],
    ["Check-in", "الدخول"], ["Break", "الاستراحة"], ["Check-out", "الخروج"],
    ["Distance", "المسافة"], ["Location", "الموقع"],
    ["Applications by job", "طلبات التقديم حسب الوظيفة"],
    ["Compare application volume across open and past roles.", "قارن عدد الطلبات بين الوظائف الحالية والسابقة."],
    ["Bar chart of applications for each job", "مخطط أعمدة لطلبات التقديم لكل وظيفة"],
    ["No job application breakdown is available yet.", "لا يتوفر توزيع لطلبات الوظائف حتى الآن."],
    ["When candidates apply to your jobs, their real application activity will appear here.", "عندما يتقدم المرشحون لوظائفك، سيظهر نشاط طلباتهم هنا."],
    ["Live workspace snapshot", "ملخص مساحة العمل المباشر"],
    ["Review applications", "مراجعة طلبات التقديم"], ["Manage jobs", "إدارة الوظائف"],
    ["Live workspace snapshot", "ملخص مساحة العمل المباشر"], ["Review applications", "مراجعة طلبات التقديم"],
    ["Manage jobs", "إدارة الوظائف"], ["Advanced applications", "طلبات متقدمة"],
    ["Candidates with applications", "مرشحون لديهم طلبات"], ["No applications yet", "لا توجد طلبات تقديم حتى الآن"],
    ["Create your first job", "أنشئ أول وظيفة"], ["Create Job Profile", "إنشاء ملف وظيفة"],
    ["Job title", "المسمى الوظيفي"], ["Department", "القسم"], ["Location", "الموقع"],
    ["Employment type", "نوع التوظيف"], ["Experience level", "مستوى الخبرة"],
    ["Job description", "وصف الوظيفة"], ["Requirements", "المتطلبات"], ["Responsibilities", "المسؤوليات"],
    ["Required skills", "المهارات المطلوبة"], ["Preferred skills", "المهارات المفضلة"],
    ["Minimum experience", "الحد الأدنى للخبرة"], ["Education", "التعليم"], ["Salary range", "نطاق الراتب"],
    ["Currency", "العملة"], ["Open", "مفتوحة"], ["Closed", "مغلقة"], ["Draft", "مسودة"],
    ["Publish job", "نشر الوظيفة"], ["Save draft", "حفظ كمسودة"], ["Update job", "تحديث الوظيفة"],
    ["Create job", "إنشاء وظيفة"], ["Cancel", "إلغاء"], ["Back", "رجوع"], ["Next", "التالي"],
    ["Previous", "السابق"], ["Continue", "متابعة"], ["Submit", "إرسال"], ["Save", "حفظ"],
    ["Search jobs...", "ابحث عن وظيفة..."], ["Search candidates...", "ابحث عن مرشح..."],
    ["All jobs", "كل الوظائف"], ["Active", "نشطة"], ["Archived", "مؤرشفة"], ["Created", "تم الإنشاء"],
    ["Candidate", "المرشح"], ["Job", "الوظيفة"], ["Applied On", "تاريخ التقديم"],
    ["AI Match Score", "درجة المطابقة بالذكاء الاصطناعي"], ["AI Review Category", "تصنيف مراجعة الذكاء الاصطناعي"],
    ["Application State", "حالة الطلب"], ["Filter applications", "تصفية الطلبات"],
    ["All applications", "كل طلبات التقديم"], ["Show all applications", "عرض كل الطلبات"],
    ["No applications yet.", "لا توجد طلبات تقديم حتى الآن."], ["No applications match this status.", "لا توجد طلبات تطابق هذه الحالة."],
    ["Must Review", "تحتاج إلى مراجعة"], ["Consider", "مرشح للنظر"], ["Lower Priority", "أولوية أقل"],
    ["Analysis Pending", "التحليل قيد الانتظار"], ["Advanced", "متقدم"], ["All", "الكل"],
    ["Start screening", "بدء الفحص"], ["Review", "مراجعة"], ["View application", "عرض الطلب"],
    ["Screening", "الفحص"], ["Upload resumes", "رفع السير الذاتية"], ["Upload resumes to screen", "ارفع السير الذاتية للفحص"],
    ["Select a job", "اختر وظيفة"], ["Choose a job", "اختر وظيفة"], ["Upload CVs", "رفع السير الذاتية"],
    ["Drag and drop resumes here", "اسحب السير الذاتية وأفلتها هنا"], ["Browse files", "استعراض الملفات"],
    ["Upload and screen", "رفع وفحص"], ["Screening results", "نتائج الفحص"], ["Processing", "قيد المعالجة"],
    ["Completed", "مكتمل"], ["Failed", "فشل"], ["Retry", "إعادة المحاولة"], ["Retrying...", "جارٍ إعادة المحاولة..."],
    ["Success", "نجاح"], ["Error", "خطأ"], ["Candidate name", "اسم المرشح"], ["Email address", "البريد الإلكتروني"],
    ["Phone number", "رقم الهاتف"], ["Experience", "الخبرة"], ["Skills", "المهارات"], ["Education", "التعليم"],
    ["Score", "النتيجة"], ["Match score", "درجة المطابقة"], ["Summary", "الملخص"], ["Evidence", "الأدلة"],
    ["Review candidates", "مراجعة المرشحين"], ["Shortlist", "القائمة المختصرة"], ["Reject", "رفض"],
    ["Move to interview", "نقل إلى المقابلة"], ["Decision", "القرار"], ["Notes", "ملاحظات"],
    ["Add note", "إضافة ملاحظة"], ["Save decision", "حفظ القرار"], ["Interview", "مقابلة"],
    ["Schedule interview", "جدولة مقابلة"], ["Interview date", "تاريخ المقابلة"], ["Interview time", "وقت المقابلة"],
    ["Interviewer", "المحاور"], ["Feedback", "التقييم"], ["Question set", "مجموعة الأسئلة"],
    ["Analytics", "التحليلات"], ["Hiring patterns and outcomes", "أنماط ونتائج التوظيف"],
    ["Current application status", "حالة طلبات التقديم الحالية"], ["Last 30 days", "آخر 30 يومًا"],
    ["Last 90 days", "آخر 90 يومًا"], ["AI Activity", "نشاط الذكاء الاصطناعي"],
    ["No results found", "لم يتم العثور على نتائج"], ["Something went wrong", "حدث خطأ ما"],
    ["لوحة التحكم — نظام الحضور والرواتب والفئات", "Dashboard — attendance, payroll & categories"],
    ["بوابة الموارد البشرية | HERA", "HR Portal | HERA"], ["بوابة الموظف —", "Employee Portal —"],
    ["الملف الشخصي والتقرير التفصيلي — نظام الحضور والرواتب", "Profile & detailed report — attendance and payroll"],
    ["اختيار مساحة العمل — HERA", "Choose a workspace — HERA"], ["تسجيل الدخول — HERA", "Sign in — HERA"],
    ["Try again", "حاول مرة أخرى"], ["Loading...", "جارٍ التحميل..."], ["No data available", "لا توجد بيانات متاحة"],
    ["Name", "الاسم"], ["Email", "البريد الإلكتروني"], ["Role", "الدور"], ["Actions", "الإجراءات"],
    ["Created at", "تاريخ الإنشاء"], ["Updated at", "تاريخ التحديث"], ["Active jobs", "الوظائف النشطة"],
    ["Total candidates", "إجمالي المرشحين"], ["Total applications", "إجمالي طلبات التقديم"],
    ["Avg. match score", "متوسط درجة المطابقة"], ["HERA · AI-ASSISTED, HR-LED", "HERA · الذكاء الاصطناعي يدعم وHR يقرر"],
    ["هوية / إقامة", "National ID / residency"], ["شهادة", "Certificate"], ["عقد", "Contract"],
    ["أخرى", "Other"], ["الصلاحية", "Expiry"],
    ["شهادة خبرة", "Experience certificate"], ["التقارير والتصدير", "Reports & export"],
    ["Excel يُنزَّل مباشرة، والنسخة القابلة للطباعة تسمح بحفظها PDF من المتصفح.", "Excel downloads directly; printable reports can be saved as PDF from your browser."],
    ["Excel الحضور", "Attendance Excel"], ["Excel الإجازات", "Leave Excel"], ["Excel الرواتب", "Payroll Excel"],
    ["PDF / طباعة الحضور", "PDF / print attendance"], ["PDF / طباعة الإجازات", "PDF / print leave"],
    ["PDF / طباعة الرواتب", "PDF / print payroll"], ["تنبيهات الطلبات والقرارات وكشوف الرواتب.", "Alerts for requests, decisions and payslips."],
    ["قراءة الكل", "Mark all as read"], ["لا توجد أنواع إجازات متاحة", "No leave types available"],
    ["لا توجد أرصدة بعد.", "No leave balances yet."], ["المتاح", "Available"], ["المستحق", "Entitled"],
    ["المستخدم", "Used"], ["المدير:", "Manager:"], ["لا يوجد موظفون مسندون للفريق.", "No employees are assigned to this team."],
    ["لا توجد طلبات معلقة.", "No pending requests."], ["رصيد الإجازات", "Leave balance"],
    ["تسجيل الدخول — HERA", "Sign in — HERA"], ["أهلًا ", "Welcome "], ["، اختر مساحة العمل", ", choose your workspace"],
    ["العودة للوحة الرئيسية", "Back to dashboard"], ["طباعة التقرير", "Print report"],
    ["التقرير الشامل والملف الشخصي", "Overview & employee profile"], ["كود الموظف:", "Employee code:"],
    ["الفئة:", "Category:"], ["أيام الحضور اليومي", "Attendance days"], ["تسجيل حضور في الموعد", "On-time check-ins"],
    ["عدد مرات التأخير", "Late arrivals"], ["تأخير عن موعد الشفت", "Late for shift"], ["أيام الغياب", "Absence days"],
    ["لم يتم تسجيل حضور", "No check-in recorded"], ["بعد الخصومات المستحقة", "After applicable deductions"],
    ["حساب تلقائي حسب الحضور والغياب", "Calculated automatically from attendance and absences"],
    ["إجمالي الخصومات المستحقة:", "Total deductions:"], ["خصم يوم كامل عن كل يوم غياب + ربع يوم عن كل تأخير", "One full day deducted per absence + one quarter day per late arrival"],
    ["⏰ قوانين الشفت والمهلة", "⏰ Shift and grace period rules"], ["المسافة عن المقر", "Distance from office"],
    ["خريطة الموقع", "Location map"], ["📍 الخريطة", "📍 Map"], ["لا توجد سجلات حضور لهذا اليوم.", "No attendance records for today."],
    ["لا توجد فئات عمل مضافة.", "No work categories have been added."], ["لا يوجد موظفون بالسيستم.", "There are no employees in the system."],
    ["لا يوجد موظفون.", "No employees."], ["لا توجد سجلات لهذا اليوم.", "No records for today."],
    ["📊 نظرة عامة", "📊 Overview"], ["🏢 الفئات الشفتات", "🏢 Categories & shifts"],
    ["📅 سجلات الحضور", "📅 Attendance records"], ["👥 إدارة الموظفين", "👥 Employee management"], ["🧩 بوابة HR", "🧩 HR portal"], ["⚙️ الإعدادات", "⚙️ Settings"],
    ["إجمالي الموظفين", "Total employees"], ["موظف مسجّل", "Registered employees"], ["الحاضرون اليوم", "Present today"],
    ["حاضر + متأخر", "Present + late"], ["المتأخرون", "Late arrivals"], ["تجاوزوا وقت الشفت", "Past shift start"],
    ["الغائبون", "Absent"], ["لم يسجّلوا بعد", "Not checked in yet"], ["الفئة / الشفت", "Category / shift"],
    ["الدخول", "Check-in"], ["الاستراحة", "Break"], ["الخروج", "Check-out"], ["الموقع", "Location"],
    ["فئات ومجموعات العمل (Shifts & Categories)", "Work categories & shifts"],
    ["تحديد مواعيد العمل، الاستراحة، مهلة الحضور، والنطاق الجغرافي لكل مجموعة.", "Set work hours, breaks, attendance grace period and geofence for each group."],
    ["اسم الفئة", "Category name"], ["مواعيد الدوام", "Work schedule"], ["مهلة التسجيل", "Check-in grace period"],
    ["النطاق الجغرافي", "Geofence"], ["عدد الموظفين", "Employee count"], ["سجل الحضور الكامل — اليوم", "Full attendance log — today"],
    ["الاسم", "Name"], ["الفئة", "Category"], ["خريطة", "Map"], ["الكود", "Code"], ["الدور", "Role"],
    ["أيام الإجازة", "Leave days"],
    ["-- كل حالات الاعتماد --", "-- All review statuses --"], ["⏳ تحت المراجعة", "⏳ Under review"],
    ["✅ معتمد", "✅ Approved"], ["⚠️ طلب تعديل", "⚠️ Revision requested"], ["-- كل الموظفين --", "-- All employees --"],
    ["تحديث 🔄", "Refresh 🔄"],
    ["إعدادات الشركة الرئيسية (الافتراضية)", "Main company settings (defaults)"], ["اسم الشركة", "Company name"],
    ["خط العرض (Latitude)", "Latitude"], ["خط الطول (Longitude)", "Longitude"],
    ["نطاق الدوام المسموح (متر)", "Allowed geofence radius (meters)"], ["النطاق الافتراضي في حال عدم تحديد فئة للموظف", "Default radius when an employee has no category"],
    ["إضافة فئة عمل جديدة", "Add a new work category"], ["اسم الفئة / المجموعة *", "Category / group name *"],
    ["نوع الشفت *", "Shift type *"], ["☀️ شفت صباحي (نهار)", "☀️ Day shift"], ["🌙 شفت مسائي / ليلي (ليل)", "🌙 Evening / night shift"],
    ["بداية العمل *", "Work start *"], ["نهاية العمل *", "Work end *"], ["وقت بدء الاستراحة (البريك)", "Break start time"],
    ["مدة الاستراحة (بالدقائق)", "Break duration (minutes)"], ["⏰ مهلة إغلاق تسجيل الحضور (بالدقائق) *", "⏰ Check-in grace period (minutes) *"],
    ["يمنع تسجيل الدخول بعد انقضاء هذه المهلة من موعد بداية العمل.", "Check-in is blocked after this grace period from the shift start."],
    ["📍 إعدادات الموقع والجغرافيا للفئة", "📍 Category location and geofence settings"], ["النطاق (متر)", "Radius (meters)"],
    ["حفظ الفئة", "Save category"], ["تحديد الموظفين التابعين للفئة", "Assign employees to category"],
    ["اختر الموظفين لنقلهم إلى هذه الفئة/الشفت", "Select employees to assign to this category / shift"],
    ["حدد الموظفين المراد نقلهم لهذه الفئة:", "Select employees to move to this category:"], ["تحديد / إلغاء الجميع", "Select / deselect all"],
    ["حالة الاعتماد والمراجعة *", "Review status *"], ["✅ معتمد ومقبول (Approved)", "✅ Approved"],
    ["⚠️ يطلب تعديلات (Needs Revision)", "⚠️ Needs revision"], ["⏳ قيد المراجعة والانتظار (Pending)", "⏳ Pending review"],
    ["ملاحظات وتعليقات الإدارة للموظف", "Manager notes and feedback"], ["إضافة موظف جديد", "Add new employee"],
    ["الاسم الكامل *", "Full name *"], ["فئة / مجموعة العمل *", "Work category / group *"],
    ["-- اختر الفئة --", "-- Select category --"], ["اتركها فارغة للإبقاء على كلمة المرور الحالية", "Leave blank to keep the current password"],
    ["👤 موظف عادي (Employee)", "👤 Employee"], ["👔 مدير فريق (Manager)", "👔 Team manager"],
    ["💼 مسؤول موارد بشرية (HR)", "💼 HR"], ["🔑 مدير النظام (Admin)", "🔑 Administrator"],
    ["الراتب الأساسي (ريال) *", "Base salary (SAR) *"], ["إضافة الموظف", "Add employee"], ["تأكيد الحذف", "Confirm deletion"],
    ["نعم، احذف", "Yes, delete"],
    ["توجيه الإدارة:", "Manager feedback:"], ["📎 فتح الملف", "📎 Open file"], ["🌐 رابط المشروع", "🌐 Project link"],
  ];
  const translations = new Map();
  for (const [en, ar] of pairs) {
    translations.set(`en:${en}`, ar);
    translations.set(`ar:${ar}`, en);
  }

  const getCookie = () => document.cookie.split(";").map(v => v.trim()).find(v => v.startsWith(`${cookieName}=`))?.split("=")[1];
  const initial = getCookie();
  let language = initial === "ar" || initial === "en" ? initial : (document.documentElement.lang === "ar" ? "ar" : "en");
  const originalText = new WeakMap();
  const originalAttributes = new WeakMap();
  let applying = false;
  const titleSource = document.title;
  const titleSourceLang = /[\u0600-\u06FF]/.test(titleSource) ? "ar" : "en";

  function translateValue(value, sourceLang, targetLang = language) {
    const leading = value.match(/^\s*/)?.[0] || "";
    const trailing = value.match(/\s*$/)?.[0] || "";
    const key = value.trim();
    if (!key || sourceLang === targetLang) return value;
    return leading + (translations.get(`${sourceLang}:${key}`) || key) + trailing;
  }

  function translateNode(node) {
    if (applying || !node || node.nodeType !== Node.TEXT_NODE) return;
    if (node.parentElement?.closest(".hera-language-toggle, .hera-localized-date")) return;
    const current = node.nodeValue || "";
    let record = originalText.get(node);
    if (!record || current !== record.rendered) {
      record = { source: current, sourceLang: /[\u0600-\u06FF]/.test(current) ? "ar" : "en", rendered: current };
    }
    const translated = translateValue(record.source, record.sourceLang, language);
    if (translated !== current) {
      originalText.set(node, { ...record, rendered: translated });
      applying = true;
      node.nodeValue = translated;
      applying = false;
    } else {
      originalText.set(node, { ...record, rendered: current });
    }
  }

  function translateTree(root = document.body) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      if (!walker.currentNode.parentElement?.closest(".hera-language-toggle, .hera-localized-date")) translateNode(walker.currentNode);
    }
    root.querySelectorAll?.("input[placeholder],textarea[placeholder],[title],[aria-label]").forEach(el => {
      let record = originalAttributes.get(el);
      if (!record) {
        record = {};
        for (const attr of ["placeholder", "title", "aria-label"]) {
          if (el.hasAttribute(attr)) record[attr] = { source: el.getAttribute(attr), sourceLang: /[\u0600-\u06FF]/.test(el.getAttribute(attr)) ? "ar" : "en" };
        }
        originalAttributes.set(el, record);
      }
      for (const attr of ["placeholder", "title", "aria-label"]) {
        if (record[attr]) el.setAttribute(attr, translateValue(record[attr].source, record[attr].sourceLang, language));
      }
    });
  }

  function formatLocalizedDates() {
    document.querySelectorAll(".hera-localized-date[data-hera-date]").forEach((el) => {
      const date = new Date(`${el.dataset.heraDate}T12:00:00`);
      if (Number.isNaN(date.getTime())) return;
      el.textContent = new Intl.DateTimeFormat(language === "ar" ? "ar-EG" : "en-GB", {
        weekday: "long", day: "numeric", month: "long", year: "numeric",
      }).format(date);
    });
  }

  function applyLanguage(next) {
    if (language === next) return;
    language = next;
    document.cookie = `${cookieName}=${next}; path=/; max-age=31536000; SameSite=Lax`;
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
    document.body?.setAttribute("dir", next === "ar" ? "rtl" : "ltr");
    document.title = translateValue(titleSource, titleSourceLang, next);
    document.querySelectorAll(".hera-language-toggle").forEach(button => {
      button.setAttribute("aria-label", next === "ar" ? "Switch language to English" : "تغيير اللغة إلى العربية");
      button.querySelector("span").textContent = next === "ar" ? "English" : "العربية";
    });
    formatLocalizedDates();
    translateTree();
    window.dispatchEvent(new CustomEvent("hera:languagechange", { detail: { language: next } }));
  }

  function install() {
    if (!initial) document.cookie = `${cookieName}=${language}; path=/; max-age=31536000; SameSite=Lax`;
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
    document.body.setAttribute("dir", language === "ar" ? "rtl" : "ltr");
    document.title = translateValue(titleSource, titleSourceLang, language);
    formatLocalizedDates();
    const button = document.createElement("button");
    button.type = "button";
    button.className = "hera-language-toggle";
    button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"></path></svg><span></span>';
    button.addEventListener("click", () => applyLanguage(language === "ar" ? "en" : "ar"));
    button.setAttribute("aria-label", language === "ar" ? "Switch language to English" : "تغيير اللغة إلى العربية");
    button.querySelector("span").textContent = language === "ar" ? "English" : "العربية";
    const header = document.querySelector("header");
    if (header) {
      button.classList.add("is-inline");
      const toolbar = header.querySelector(".top-actions, [class*='items-center'][class*='justify-between']") || header;
      toolbar.append(button);
    } else {
      button.classList.add("is-floating");
      document.body.append(button);
    }
    translateTree();
    const observer = new MutationObserver(records => {
      for (const record of records) {
        record.addedNodes.forEach(node => {
          if (node.nodeType === Node.TEXT_NODE) translateNode(node);
          else if (node.nodeType === Node.ELEMENT_NODE) translateTree(node);
        });
        if (record.type === "characterData") translateNode(record.target);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();
})();

<?php
if (empty($_SESSION['employee_chat_csrf'])) {
    $_SESSION['employee_chat_csrf'] = bin2hex(random_bytes(32));
}
$employeeChatCsrf = (string)$_SESSION['employee_chat_csrf'];
?>
<section class="employee-chat" aria-label="مساعد الموظفين">
  <div class="employee-chat-panel" id="employeeChatPanel" hidden>
    <header class="employee-chat-header">
      <div>
        <strong>مساعد الموظفين</strong>
        <span>اسأل عن السياسات أو طلباتك</span>
      </div>
      <button type="button" class="employee-chat-close" id="employeeChatClose" aria-label="إغلاق المحادثة">×</button>
    </header>
    <div class="employee-chat-messages" id="employeeChatMessages" role="log" aria-live="polite">
      <article class="employee-chat-message assistant">
        أهلًا بك. أقدر أساعدك في فهم السياسات، تقديم طلب مدعوم، أو متابعة طلباتك.
      </article>
    </div>
    <p class="employee-chat-status" id="employeeChatStatus" aria-live="polite"></p>
    <form class="employee-chat-form" id="employeeChatForm" data-csrf="<?= htmlspecialchars($employeeChatCsrf, ENT_QUOTES, 'UTF-8') ?>">
      <label class="sr-only" for="employeeChatInput">اكتب رسالتك</label>
      <textarea id="employeeChatInput" rows="1" maxlength="2000" placeholder="اكتب سؤالك أو طلبك…" required></textarea>
      <button type="submit" id="employeeChatSend" aria-label="إرسال الرسالة">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 21 3l-6.5 18-3.2-7.3L3 11.5Zm8.3 2.2L21 3"/></svg>
      </button>
    </form>
  </div>
  <button type="button" class="employee-chat-launcher" id="employeeChatToggle" aria-expanded="false" aria-controls="employeeChatPanel" aria-label="افتح مساعد الموظفين">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H6l-3 2v-6.5A7.5 7.5 0 1 1 20 11.5Z"/><path d="M8 11h8M8 14h5"/></svg>
  </button>
</section>

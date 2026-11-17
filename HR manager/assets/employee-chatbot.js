(() => {
  const toggle = document.getElementById("employeeChatToggle");
  const panel = document.getElementById("employeeChatPanel");
  const close = document.getElementById("employeeChatClose");
  const form = document.getElementById("employeeChatForm");
  const input = document.getElementById("employeeChatInput");
  const messages = document.getElementById("employeeChatMessages");
  const status = document.getElementById("employeeChatStatus");
  const send = document.getElementById("employeeChatSend");
  if (!toggle || !panel || !form || !input || !messages || !status || !send) return;

  const setOpen = (open) => {
    panel.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "أغلق مساعد الموظفين" : "افتح مساعد الموظفين");
    if (open) input.focus();
  };
  const appendMessage = (text, sender) => {
    const message = document.createElement("article");
    message.className = `employee-chat-message ${sender}`;
    message.textContent = text;
    messages.append(message);
    messages.scrollTop = messages.scrollHeight;
  };
  const appendLeaveConfirmation = (draft) => {
    const card = document.createElement("div");
    card.className = "employee-chat-message assistant";
    const summary = document.createElement("p");
    summary.textContent = `الطلب: ${draft.leave_type_name}، من ${draft.start_date} إلى ${draft.end_date}. السبب: ${draft.reason}`;
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "employee-chat-confirm";
    confirm.textContent = "تأكيد إرسال الطلب";
    const requestKey = globalThis.crypto?.randomUUID?.() || `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    confirm.addEventListener("click", async () => {
      confirm.disabled = true;
      status.textContent = "جارٍ تسجيل الطلب…";
      try {
        const response = await fetch("/BIC2_Mvp/api/hr.php", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "submit_leave",
            leave_type_id: draft.leave_type_id,
            start_date: draft.start_date,
            end_date: draft.end_date,
            reason: draft.reason,
            request_key: requestKey,
            chat_csrf: form.dataset.csrf,
          }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.message || "تعذر إرسال الطلب.");
        status.textContent = "";
        confirm.textContent = "تم تسجيل الطلب";
        const confirmation = `تم تسجيل طلبك بنجاح. رقم الطلب: ${result.request_id}. الحالة: ${result.status === "pending_manager" ? "بانتظار موافقة المدير" : "بانتظار مراجعة الموارد البشرية"}.`;
        appendMessage(confirmation, "assistant");
        conversation.push({ role: "assistant", content: confirmation });
      } catch (error) {
        confirm.disabled = false;
        status.textContent = error.message || "تعذر تسجيل الطلب. حاول مرة أخرى.";
      }
    });
    card.append(summary, confirm);
    messages.append(card);
    messages.scrollTop = messages.scrollHeight;
  };
  const appendInfoConfirmation = (draft) => {
    const card = document.createElement("div");
    card.className = "employee-chat-message assistant";
    const details = document.createElement("p");
    details.textContent = `المعلومات: ${draft.details}`;
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "employee-chat-confirm";
    confirm.textContent = "إرسال المعلومات";
    const requestKey = globalThis.crypto?.randomUUID?.() || `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    confirm.addEventListener("click", async () => {
      confirm.disabled = true;
      status.textContent = "جارٍ إرسال المعلومات…";
      try {
        const response = await fetch("/BIC2_Mvp/api/hr.php", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "provide_leave_info",
            request_id: draft.request_id,
            details: draft.details,
            request_key: requestKey,
            chat_csrf: form.dataset.csrf,
          }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.message || "تعذر إرسال المعلومات.");
        status.textContent = "";
        confirm.textContent = "تم إرسال المعلومات";
        const confirmation = `تم إرسال المعلومات لمديرك بخصوص الطلب رقم ${draft.request_id}.`;
        appendMessage(confirmation, "assistant");
        conversation.push({ role: "assistant", content: confirmation });
      } catch (error) {
        confirm.disabled = false;
        status.textContent = error.message || "تعذر إرسال المعلومات. حاول مرة أخرى.";
      }
    });
    card.append(details, confirm);
    messages.append(card);
    messages.scrollTop = messages.scrollHeight;
  };

  toggle.addEventListener("click", () => setOpen(panel.hidden));
  close?.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) setOpen(false);
  });
  const conversation = [];
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    appendMessage(text, "user");
    conversation.push({ role: "user", content: text });
    input.value = "";
    status.textContent = "جارٍ تجهيز المساعد…";
    send.disabled = true;
    try {
      const response = await fetch("/BIC2_Mvp/api/employee_chat.php", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: conversation.slice(-8, -1), csrf: form.dataset.csrf }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.message || "تعذر إرسال الرسالة الآن.");
      appendMessage(result.message, "assistant");
      conversation.push({ role: "assistant", content: result.message });
      if (result.leave_draft) appendLeaveConfirmation(result.leave_draft);
      if (result.leave_info_draft) appendInfoConfirmation(result.leave_info_draft);
      conversation.splice(0, Math.max(0, conversation.length - 8));
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message || "تعذر الاتصال بالمساعد. حاول مرة أخرى.";
    } finally {
      send.disabled = false;
      input.focus();
    }
  });
})();

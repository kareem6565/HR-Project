import React from "react";
import { Inbox } from "lucide-react";

// Generic "nothing here" state, used instead of a blank table/list.
// Usage: <EmptyState message="No candidates found." />
export default function EmptyState({ icon: Icon = Inbox, message = "Nothing here yet.", action }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <Icon size={22} />
      </div>
      <p>{message}</p>
      {action}
    </div>
  );
}

import React from "react";
import { Inbox } from "lucide-react";

// Generic "nothing here" state, used instead of a blank table/list.
// Usage: <EmptyState message="No candidates found." />
export default function EmptyState({ icon: Icon = Inbox, message = "Nothing here yet.", action, illustration }) {
  return (
    <div className="empty-state">
      {illustration ? (
        <img className="empty-state-illustration" src={illustration} alt="" aria-hidden="true" />
      ) : (
        <div className="empty-state-icon">
          <Icon size={22} />
        </div>
      )}
      <p>{message}</p>
      {action}
    </div>
  );
}

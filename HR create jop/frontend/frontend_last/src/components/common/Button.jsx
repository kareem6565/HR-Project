import React from "react";

// Generic button used across the app instead of one-off styled buttons.
// variant: "primary" | "secondary" | "danger"
// motion-btn adds press physics; the sheen span renders the hover light sweep.
export default function Button({
  variant = "primary",
  icon: Icon,
  children,
  className = "",
  ...rest
}) {
  return (
    <button className={`btn btn-${variant} motion-btn ${className}`.trim()} {...rest}>
      {Icon && <Icon size={17} />}
      {children}
      <span className="sheen" aria-hidden="true" />
    </button>
  );
}

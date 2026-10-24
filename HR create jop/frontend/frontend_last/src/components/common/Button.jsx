import React from "react";

// Generic button used across the app instead of one-off styled buttons.
// variant: "primary" | "secondary" | "danger"
export default function Button({
  variant = "primary",
  icon: Icon,
  children,
  className = "",
  ...rest
}) {
  return (
    <button className={`btn btn-${variant} ${className}`.trim()} {...rest}>
      {Icon && <Icon size={17} />}
      {children}
    </button>
  );
}

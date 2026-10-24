import React from "react";

export default function HeraAssistantMark({ size = 28, className = "" }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="1" y="1" width="30" height="30" rx="10" fill="#1B3A3A" />
      <path d="M16 4.5v2.3" stroke="#E9D98A" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="16" cy="4" r="1.7" fill="#E9D98A" />
      <path d="M7.2 13.2c0-2.1 1.7-3.8 3.8-3.8h10c2.1 0 3.8 1.7 3.8 3.8v7.2c0 2.1-1.7 3.8-3.8 3.8H11c-2.1 0-3.8-1.7-3.8-3.8v-7.2Z" fill="#F5EFE2" />
      <rect x="9.5" y="12.1" width="13" height="8.5" rx="4.1" fill="#082A24" />
      <circle cx="13.5" cy="15.8" r="1" fill="#E9D98A" />
      <circle cx="18.5" cy="15.8" r="1" fill="#E9D98A" />
      <path d="M13.8 18.2c.6.7 1.3 1 2.2 1s1.6-.3 2.2-1" stroke="#F5EFE2" strokeWidth="1.15" strokeLinecap="round" />
      <path d="M5.3 15.2v3.1M26.7 15.2v3.1" stroke="#6FA8B8" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

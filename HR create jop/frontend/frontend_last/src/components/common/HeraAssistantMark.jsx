import React from "react";
import "./HeraAssistantMark.css";

// The HERA assistant robot mark, alive in the same spirit as the animated
// logo: it blinks, its smile grows when it "notices" you, the antenna pings,
// and the head tilts a touch. All motion is CSS/SMIL inside the SVG - no JS
// timers, honors reduced motion. Set animated={false} for a static mark.

export default function HeraAssistantMark({ size = 28, className = "", animated = true }) {
  return (
    <svg
      className={`${animated ? "hera-assistant-animated" : ""} ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="1" y="1" width="30" height="30" rx="10" fill="#1B3A3A" />
      {/* antenna: the gold tip pulses and pings a soft ring once per loop */}
      <path d="M16 4.5v2.3" stroke="#E9D98A" strokeWidth="1.6" strokeLinecap="round" />
      <circle className="ha-antenna" cx="16" cy="4" r="1.7" fill="#E9D98A" />
      <circle className="ha-ping" cx="16" cy="4" r="1.7" fill="none" stroke="#E9D98A" strokeWidth="0.7" />
      <g className="ha-head">
        <path d="M7.2 13.2c0-2.1 1.7-3.8 3.8-3.8h10c2.1 0 3.8 1.7 3.8 3.8v7.2c0 2.1-1.7 3.8-3.8 3.8H11c-2.1 0-3.8-1.7-3.8-3.8v-7.2Z" fill="#F5EFE2" />
        <rect x="9.5" y="12.1" width="13" height="8.5" rx="4.1" fill="#082A24" />
        <circle className="ha-eye" cx="13.5" cy="15.8" r="1" fill="#E9D98A" />
        <circle className="ha-eye" cx="18.5" cy="15.8" r="1" fill="#E9D98A" />
        <path
          className="ha-smile"
          d="M13.8 18.2c.6.7 1.3 1 2.2 1s1.6-.3 2.2-1"
          stroke="#F5EFE2"
          strokeWidth="1.15"
          strokeLinecap="round"
          fill="none"
        >
          <animate
            attributeName="d"
            dur="4s"
            repeatCount="indefinite"
            values="M13.8 18.2c.6.7 1.3 1 2.2 1s1.6-.3 2.2-1; M13.8 18.2c.6.7 1.3 1 2.2 1s1.6-.3 2.2-1; M13.2 18.2c.8 1 1.7 1.4 2.8 1.4s2-.4 2.8-1.4; M13.2 18.2c.8 1 1.7 1.4 2.8 1.4s2-.4 2.8-1.4; M13.8 18.2c.6.7 1.3 1 2.2 1s1.6-.3 2.2-1; M13.8 18.2c.6.7 1.3 1 2.2 1s1.6-.3 2.2-1"
            keyTimes="0; 0.4; 0.52; 0.62; 0.74; 1"
          />
        </path>
        <path d="M5.3 15.2v3.1M26.7 15.2v3.1" stroke="#6FA8B8" strokeWidth="1.7" strokeLinecap="round" />
      </g>
    </svg>
  );
}

import React from "react";
import "./AnimatedHeraMark.css";

// The HERA brand mark (the R-with-smile mascot icon) brought to life: it
// blinks, its smile grows when it "notices" you, and the clasp pulses a scan
// every loop. Artwork is identical to /brand/hera-icon-{dark,light}.svg; all
// motion is CSS/SMIL inside the SVG - no JS timers, honors reduced motion.

const COLORS = {
  dark: { bg: "#103B3D", figure: "#F6F1E3", clasp: "#F6F1E3", cape: "#F6D57E", ring: "#5EA6BC" },
  light: { bg: "#F6F1E3", figure: "#103B3D", clasp: "#5EA6BC", cape: "#F6D57E", ring: "#5EA6BC" },
};

export default function AnimatedHeraMark({ size = 40, variant = "dark", title = "HERA" }) {
  const c = COLORS[variant] || COLORS.dark;
  return (
    <svg
      className="hera-mark-animated"
      viewBox="0 0 512 512"
      width={size}
      height={size}
      role="img"
      aria-label={title}
    >
      {/* rounded-square badge */}
      <rect width="512" height="512" rx="116" fill={c.bg} />
      {/* R figure: hood, left arm and left leg */}
      <path
        fill={c.figure}
        d="M 230 96 H 322 C 374 96, 408 134, 408 184 C 386 154, 348 140, 296 140 H 234 C 218 140, 208 150, 208 166 V 242 C 226 232, 250 232, 266 244 C 254 256, 252 274, 262 288 C 228 310, 206 346, 200 398 H 148 V 344 C 104 334, 82 292, 92 246 C 100 208, 128 186, 166 184 V 160 C 166 122, 192 96, 230 96 Z"
      />
      {/* negative-space cutout inside the left arm */}
      <path fill={c.bg} d="M 148 232 C 128 236, 122 264, 134 282 C 138 288, 144 290, 148 288 Z" />
      {/* eyes: blink twice per loop */}
      <circle className="hm-eye" cx="274" cy="186" r="13.5" fill={c.figure} />
      <circle className="hm-eye" cx="336" cy="186" r="13.5" fill={c.figure} />
      {/* smile: grows and relaxes once per loop */}
      <path
        className="hm-smile"
        d="M 290 212 Q 305 227 320 212"
        fill="none"
        stroke={c.figure}
        strokeWidth="11"
        strokeLinecap="round"
      >
        <animate
          attributeName="d"
          dur="4s"
          repeatCount="indefinite"
          values="M 290 212 Q 305 227 320 212; M 290 212 Q 305 227 320 212; M 284 212 Q 305 232 326 212; M 284 212 Q 305 232 326 212; M 290 212 Q 305 227 320 212; M 290 212 Q 305 227 320 212"
          keyTimes="0; 0.4; 0.52; 0.62; 0.74; 1"
        />
      </path>
      {/* clasp: breathes, with a scan ring pinging once per loop */}
      <circle className="hm-lens" cx="288" cy="264" r="17" fill={c.clasp} />
      <circle className="hm-scan" cx="288" cy="264" r="17" fill="none" stroke={c.ring} strokeWidth="6" />
      {/* warm yellow right cape and leg */}
      <path
        fill={c.cape}
        d="M 316 248 L 422 162 C 452 216, 444 286, 394 328 C 412 348, 424 372, 430 398 H 376 C 366 352, 344 316, 310 292 C 322 278, 324 260, 316 248 Z"
      />
    </svg>
  );
}

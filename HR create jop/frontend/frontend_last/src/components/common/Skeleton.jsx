import React from "react";

// Shimmer loading placeholder. Use lines/avatar shapes to mirror the
// content being loaded instead of a bare spinner.
export default function Skeleton({ variant = "line", width, height, className = "", style = {}, ...rest }) {
  const classes = `motion-skeleton skeleton skeleton-${variant} ${className}`.trim();
  const merged = { ...style };
  if (width) merged.width = width;
  if (height) merged.height = height;
  return <div className={classes} style={merged} aria-hidden="true" {...rest} />;
}

export function SkeletonCard({ lines = 2, avatar = true }) {
  return (
    <div className="skeleton-card" role="status" aria-label="Loading">
      {avatar && <Skeleton variant="avatar" />}
      <div className="skeleton-lines">
        {Array.from({ length: lines }, (_, i) => (
          <Skeleton key={i} variant="line" width={i === lines - 1 ? "55%" : "100%"} />
        ))}
      </div>
    </div>
  );
}

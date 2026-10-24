import { getApplications } from "./applicationService";
import { parseScore } from "../utils/score";

const DAY_MS = 24 * 60 * 60 * 1000;
const RANGE_DAYS = { "30d": 30, "90d": 90 };
const STATUS_GROUPS = [
  { stage: "Created", statuses: ["created"] },
  { stage: "Analysis", statuses: ["analysis_pending", "analyzing", "analysis_failed"] },
  { stage: "Ready for review", statuses: ["ready_for_review"] },
  { stage: "Hold", statuses: ["hold"] },
  { stage: "Advanced", statuses: ["advanced"] },
  { stage: "Rejected", statuses: ["rejected"] },
  { stage: "Archived", statuses: ["archived"] },
];

function validRange(range) {
  return Object.hasOwn(RANGE_DAYS, range) ? range : "30d";
}

export function filterApplicationsToRange(apps, range = "30d", now = new Date()) {
  const end = now.getTime();
  const start = end - RANGE_DAYS[validRange(range)] * DAY_MS;
  return apps.filter((app) => {
    const createdAt = Date.parse(app.appliedAt);
    return Number.isFinite(createdAt) && createdAt >= start && createdAt <= end;
  });
}

export function filterApplicationsToLast30Days(apps, now = new Date()) {
  return filterApplicationsToRange(apps, "30d", now);
}

function buildMetrics(apps, range) {
  const periodLabel = `last ${RANGE_DAYS[range]} days`;
  const metrics = [
    {
      key: "applications",
      label: `Applications · ${periodLabel}`,
      value: apps.length,
      deltaLabel: "created in selected period",
    },
    {
      key: "candidates",
      label: `Candidates with applications · ${periodLabel}`,
      value: new Set(apps.map((app) => app.candidateId).filter(Boolean)).size,
      deltaLabel: "unique candidates in selected period",
    },
    {
      key: "advanced_applications",
      label: `Advanced applications · ${periodLabel}`,
      value: apps.filter((app) => app.status === "advanced").length,
      deltaLabel: "current status of in-period applications",
    },
  ];
  const scores = apps.map((app) => parseScore(app.score)).filter((score) => score !== null);
  if (scores.length) {
    const average = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    metrics.push({
      key: "avg_score",
      label: `Average AI score · ${periodLabel}`,
      value: `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(average)}%`,
      deltaLabel: "valid scores in selected period",
    });
  }
  return metrics;
}

function buildStatusBreakdown(apps) {
  const counts = new Map(STATUS_GROUPS.map(({ stage }) => [stage, 0]));
  let otherCount = 0;
  for (const app of apps) {
    const group = STATUS_GROUPS.find(({ statuses }) => statuses.includes(app.status));
    if (group) counts.set(group.stage, counts.get(group.stage) + 1);
    else otherCount += 1;
  }
  if (otherCount) counts.set("Other statuses", otherCount);
  const total = apps.length;
  const rows = Array.from(counts, ([stage, count]) => ({
    stage,
    count,
    percent: total ? Number(((count / total) * 100).toFixed(1)) : 0,
  }));
  if (total && rows.length) {
    const roundedTotal = rows.reduce((sum, row) => sum + row.percent, 0);
    const largestGroup = rows.reduce((largest, row) => row.count > largest.count ? row : largest, rows[0]);
    largestGroup.percent = Number((largestGroup.percent + 100 - roundedTotal).toFixed(1));
  }
  return rows;
}

function buildApplicationTrend(apps, range, now) {
  const days = RANGE_DAYS[range];
  const periodStart = now.getTime() - days * DAY_MS;
  const bucketCount = Math.ceil(days / 7);
  const buckets = Array.from({ length: bucketCount }, (_, index) => {
    const start = periodStart + index * 7 * DAY_MS;
    return {
      label: new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(start)),
      applications: 0,
    };
  });

  for (const app of apps) {
    const createdAt = Date.parse(app.appliedAt);
    if (!Number.isFinite(createdAt)) continue;
    const index = Math.floor((createdAt - periodStart) / (7 * DAY_MS));
    if (index >= 0 && index < buckets.length) buckets[index].applications += 1;
  }
  return buckets;
}

export async function getAnalyticsSnapshot(range = "30d", now = new Date()) {
  const selectedRange = validRange(range);
  const apps = filterApplicationsToRange(await getApplications(), selectedRange, now);
  return {
    metrics: buildMetrics(apps, selectedRange),
    statusBreakdown: buildStatusBreakdown(apps),
    applicationTrend: buildApplicationTrend(apps, selectedRange, now),
    validApplicationDates: apps.length,
    range: selectedRange,
  };
}

// Kept as small helpers for existing consumers and focused service tests.
export async function getAnalyticsMetrics(now = new Date()) {
  return (await getAnalyticsSnapshot("30d", now)).metrics;
}

export async function getApplicationStatusBreakdown(now = new Date()) {
  return (await getAnalyticsSnapshot("30d", now)).statusBreakdown;
}

export async function getCandidateSources() {
  // No candidate-source endpoint or source data is currently available.
  return null;
}

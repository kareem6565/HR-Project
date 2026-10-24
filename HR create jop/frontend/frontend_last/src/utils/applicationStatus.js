import { JobApplicationStatus } from "../types/api";

export const APPLICATION_STATUS_LABELS = Object.freeze({
  [JobApplicationStatus.CREATED]: "Created",
  [JobApplicationStatus.ANALYSIS_PENDING]: "Analysis Pending",
  [JobApplicationStatus.ANALYZING]: "Analyzing",
  [JobApplicationStatus.ANALYSIS_FAILED]: "Analysis Failed",
  [JobApplicationStatus.READY_FOR_REVIEW]: "Ready for Review",
  [JobApplicationStatus.HOLD]: "Hold",
  [JobApplicationStatus.ADVANCED]: "Advanced",
  [JobApplicationStatus.REJECTED]: "Rejected",
  [JobApplicationStatus.ARCHIVED]: "Archived",
});

export const APPLICATION_STATUS_GROUPS = Object.freeze([
  {
    id: "processing",
    label: "Processing status",
    description: "Where the application is in automated processing or awaiting review.",
    statuses: [
      JobApplicationStatus.CREATED,
      JobApplicationStatus.ANALYSIS_PENDING,
      JobApplicationStatus.ANALYZING,
      JobApplicationStatus.ANALYSIS_FAILED,
      JobApplicationStatus.READY_FOR_REVIEW,
    ],
  },
  {
    id: "decision",
    label: "HR decision status",
    description: "Application states mirrored when HR records Hold, Advance, or Reject.",
    statuses: [
      JobApplicationStatus.HOLD,
      JobApplicationStatus.ADVANCED,
      JobApplicationStatus.REJECTED,
    ],
  },
  {
    id: "other",
    label: "Other status",
    description: "Application states outside processing and recorded HR decisions.",
    statuses: [JobApplicationStatus.ARCHIVED],
  },
]);

export function getApplicationStatusGroup(status) {
  return APPLICATION_STATUS_GROUPS.find((group) => group.statuses.includes(status)) || null;
}

export const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];
export const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

export function formatFileSize(bytes) {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function getFileFingerprint(file) {
  const name = file?.name || "";
  const size = file?.size ?? 0;
  const lastMod = file?.lastModified ?? 0;
  return `${name}:${size}:${lastMod}`;
}

export function validateFile(file, existingFingerprints = new Set(), maxFileBytes = null) {
  const name = (file?.name || "").toLowerCase();
  const hasValidExt = ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));

  if (!hasValidExt) {
    return {
      valid: false,
      reason: "Unsupported file format (only PDF and DOCX files are supported).",
      code: "unsupported_type",
    };
  }

  if (Number.isFinite(maxFileBytes) && file.size > maxFileBytes) {
    return {
      valid: false,
      reason: `File exceeds the ${formatFileSize(maxFileBytes)} maximum size limit (${formatFileSize(file.size)}).`,
      code: "size_limit",
    };
  }

  const fingerprint = getFileFingerprint(file);
  if (existingFingerprints.has(fingerprint)) {
    return {
      valid: false,
      reason:
        "Duplicate file already selected (local client hint: matching name, size, and modified date. Server computes authoritative checksums).",
      code: "duplicate_hint",
    };
  }

  return { valid: true, fingerprint };
}

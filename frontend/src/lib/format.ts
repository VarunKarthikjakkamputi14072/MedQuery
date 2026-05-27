export function formatDate(input: string | Date): string {
  const date = typeof input === "string" ? new Date(input) : input;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export function confidenceTone(score: number): {
  label: string;
  className: string;
} {
  if (score >= 0.75)
    return {
      label: "High",
      className: "text-clinical-ok border-clinical-ok/40 bg-clinical-ok/10",
    };
  if (score >= 0.45)
    return {
      label: "Medium",
      className: "text-clinical-warn border-clinical-warn/40 bg-clinical-warn/10",
    };
  return {
    label: "Low",
    className: "text-clinical-risk border-clinical-risk/40 bg-clinical-risk/10",
  };
}

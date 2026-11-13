export default function ClaimStatus({ status, label, description }) {
  const needsAttention = status === "info_required";
  const chipColor = needsAttention ? "bg-accent" : "bg-primary";

  return (
    <div>
      <span
        className={`inline-block ${chipColor} border-2 border-secondary rounded-none px-3 py-1 font-mono text-xs uppercase tracking-wider text-secondary`}
      >
        {label}
      </span>
      {description && (
        <p className="font-body text-sm text-secondary mt-2">{description}</p>
      )}
    </div>
  );
}
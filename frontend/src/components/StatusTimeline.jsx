export default function StatusTimeline({ entries }) {
  if (entries.length === 0) {
    return <p className="font-body text-sm text-secondary">No status updates yet.</p>;
  }

  return (
    <ol className="border-l-2 border-secondary ml-2 space-y-5">
      {entries.map((entry) => (
        <li key={entry.id} className="pl-5 relative">
          <span className="absolute -left-[7px] top-1 w-3 h-3 bg-accent border-2 border-secondary" />
          <p className="font-body text-sm font-semibold text-secondary">{entry.label}</p>
          <p className="font-body text-sm text-secondary">{entry.description}</p>
          <p className="font-mono text-xs text-secondary mt-1">
            {new Date(entry.created_at).toLocaleString()}
          </p>
        </li>
      ))}
    </ol>
  );
}
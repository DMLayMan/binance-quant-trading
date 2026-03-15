interface MetricCardProps {
  title: string;
  value: string;
  change?: number | null;
  subtitle?: string;
}

export default function MetricCard({
  title,
  value,
  change,
  subtitle,
}: MetricCardProps) {
  const changeColor =
    change != null && change >= 0 ? "text-green-500" : "text-red-500";

  return (
    <div className="rounded-xl bg-gray-800 p-5">
      <p className="text-sm text-gray-500">{title}</p>
      <p className="mt-1 text-2xl font-bold text-white">{value}</p>
      {change != null && (
        <p className={`mt-1 text-sm font-medium ${changeColor}`}>
          {change >= 0 ? "+" : ""}
          {change.toFixed(2)}%
        </p>
      )}
      {subtitle && <p className="mt-1 text-xs text-gray-500">{subtitle}</p>}
    </div>
  );
}

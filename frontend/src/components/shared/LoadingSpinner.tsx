export default function LoadingSpinner() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-gray-700 border-t-blue-500" />
    </div>
  );
}

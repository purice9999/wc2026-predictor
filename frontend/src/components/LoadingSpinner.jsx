export default function LoadingSpinner({ size = 'md' }) {
  const s = size === 'sm' ? 'h-5 w-5' : size === 'lg' ? 'h-12 w-12' : 'h-8 w-8'
  return (
    <div className="flex items-center justify-center py-8">
      <div className={`${s} animate-spin rounded-full border-2 border-navy-600 border-t-cyan-400`} />
    </div>
  )
}

export function ErrorMsg({ message }) {
  return (
    <div className="card p-4 text-red-400 text-sm flex items-center gap-2">
      <span>⚠</span>
      <span>{message || 'Eroare la încărcare date.'}</span>
    </div>
  )
}

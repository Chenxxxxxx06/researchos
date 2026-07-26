import { Skeleton } from '@/components/ui/skeleton';

export default function ProjectLoading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-56" />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton.Text lines={3} className="max-w-xl" />
    </div>
  );
}

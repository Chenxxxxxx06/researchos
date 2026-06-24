import { redirect } from 'next/navigation';

export default function HomePage() {
  // Entry point: the workspace middleware will redirect to /login when there is
  // no session cookie.
  redirect('/projects');
}

import Link from 'next/link';

import { Card, CardContent } from '@/components/ui/card';
import { RegisterForm } from '@/features/auth/RegisterForm';

export default function RegisterPage() {
  return (
    <Card>
      <CardContent className="p-6">
        <h2 className="mb-4 text-base font-semibold">Create your account</h2>
        <RegisterForm />
        <p className="mt-4 text-center text-sm text-neutral-500">
          Already have an account?{' '}
          <Link href="/login" className="font-medium text-neutral-900 underline">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

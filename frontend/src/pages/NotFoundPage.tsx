import { Link } from "react-router";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-page px-6 text-center">
      <Logo />
      <h1 className="text-h1 font-semibold tracking-tight">This page doesn’t exist</h1>
      <p className="max-w-sm text-body text-secondary-text">The address may be mistyped, or the run was started on another machine.</p>
      <Button asChild size="lg" className="h-10 px-4">
        <Link to="/">Start a new build</Link>
      </Button>
    </div>
  );
}

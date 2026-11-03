import Link from "next/link";
import { ArrowLeft } from "lucide-react";

/** An explicit home destination, also when a subpage was opened directly. */
export function MainWindowLink() {
  return (
    <Link
      href="/"
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-cyan-400/25 bg-cyan-400/[0.07] px-3 py-2 text-xs font-medium text-cyan-200 transition-colors hover:bg-cyan-400/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300"
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
      Zurück zu Apollo
    </Link>
  );
}

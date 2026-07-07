import Link from "next/link";

export default function GameNotFound() {
  return (
    <div className="pt-24 text-center">
      <div className="text-5xl">🏀</div>
      <h1 className="mt-4 text-2xl font-black">This game hasn&apos;t been analyzed yet</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">
        Every featured and browseable game on the home page has a full breakdown. Pick one from there.
      </p>
      <Link href="/" className="mt-6 inline-block rounded-full border border-line px-6 py-2.5 text-sm font-bold transition hover:bg-white/5">
        ← Back to games
      </Link>
    </div>
  );
}

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://clutchcast-ai.vercel.app"),
  title: {
    default: "ClutchCast AI — NBA Win Probability",
    template: "%s | ClutchCast AI",
  },
  description:
    "Live NBA win probability, turning points, and player impact — powered by a calibration-tested machine learning model.",
  openGraph: {
    title: "ClutchCast AI — NBA Win Probability",
    description: "Every game has a moment it was decided. Find it.",
    siteName: "ClutchCast AI",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "ClutchCast AI — NBA Win Probability",
    description: "Every game has a moment it was decided. Find it.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-50 border-b border-line bg-[rgba(5,7,13,0.8)] backdrop-blur-xl">
          <nav className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5">
            <Link href="/" className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-400 via-orange-500 to-blue-600 text-sm font-black text-white shadow-lg shadow-blue-900/40">
                CC
              </span>
              <span className="text-lg font-black tracking-tight">
                ClutchCast <span className="brand-gradient">AI</span>
              </span>
            </Link>
            <div className="flex items-center gap-1 text-sm font-semibold text-muted">
              <Link href="/" className="rounded-full px-4 py-2 transition hover:bg-white/5 hover:text-foreground">
                Games
              </Link>
              <Link href="/models" className="rounded-full px-4 py-2 transition hover:bg-white/5 hover:text-foreground">
                The Model
              </Link>
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-5 pb-24">{children}</main>
        <footer className="border-t border-line py-8 text-center text-xs text-muted">
          ClutchCast AI · win probabilities from a calibration-tested model · not affiliated with the NBA
        </footer>
      </body>
    </html>
  );
}

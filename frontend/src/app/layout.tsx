import type { Metadata } from "next";
import { DM_Sans, Instrument_Serif } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

/* --------------------------------------------------------------- */
/* Fonts                                                            */
/* --------------------------------------------------------------- */

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  weight: ["400", "500", "600", "700"],
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  variable: "--font-instrument-serif",
  weight: "400",
  style: "normal",
});

const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

/* --------------------------------------------------------------- */
/* Metadata                                                         */
/* --------------------------------------------------------------- */

export const metadata: Metadata = {
  title: "CSRD Compliance Engine",
  description:
    "EU Taxonomy alignment audit against ESRS disclosures and national registry filings.",
};

/* --------------------------------------------------------------- */
/* Root Layout                                                      */
/* --------------------------------------------------------------- */

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`
          ${dmSans.variable}
          ${instrumentSerif.variable}
          ${geistMono.variable}
          font-body antialiased bg-canvas text-slate-900
        `}
      >
        <NavHeader />
        <div className="mx-auto max-w-5xl px-6 pb-16 pt-10">{children}</div>
      </body>
    </html>
  );
}

/* --------------------------------------------------------------- */
/* Persistent Navigation Header                                     */
/* --------------------------------------------------------------- */

function NavHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        {/* Logo / Wordmark with EU authority */}
        <div className="flex items-center gap-2.5">
          <svg viewBox="0 0 24 24" className="h-6 w-6 shrink-0" aria-label="EU flag">
            <rect width="24" height="24" rx="4" fill="#003399" />
            {Array.from({ length: 12 }, (_, i) => {
              const a = (i * 30 - 90) * (Math.PI / 180);
              return <circle key={i} cx={12 + 8 * Math.cos(a)} cy={12 + 8 * Math.sin(a)} r={1.2} fill="#FFD617" />;
            })}
          </svg>
          <span className="text-[15px] font-semibold tracking-tight text-slate-900">
            CSRD Compliance Engine
          </span>
          <span className="hidden rounded bg-accent/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-accent sm:inline">
            ESRS
          </span>
        </div>

        {/* Ticker Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search LEI..."
            className="h-8 w-48 rounded-card border border-slate-200 bg-slate-50 pl-8 pr-3 font-mono text-xs text-slate-700 placeholder:text-slate-400 transition-all focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
          <svg
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
      </div>
    </header>
  );
}

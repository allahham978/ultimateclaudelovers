import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

/* --------------------------------------------------------------- */
/* Fonts                                                            */
/* --------------------------------------------------------------- */

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-plus-jakarta",
  weight: ["300", "400", "500", "600", "700", "800"],
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
  title: "ESGateway — CSRD Compliance Engine",
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
          ${plusJakarta.variable}
          ${geistMono.variable}
          font-body antialiased bg-canvas text-stone-800
        `}
      >
        <NavHeader />
        <div className="mx-auto max-w-6xl px-8 pb-20 pt-12">{children}</div>
      </body>
    </html>
  );
}

/* --------------------------------------------------------------- */
/* Persistent Navigation Header                                     */
/* --------------------------------------------------------------- */

function NavHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-stone-200/40 bg-canvas/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-8">
        {/* Logo / Wordmark */}
        <a href="/" className="flex items-center gap-3">
          <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" aria-label="EU flag">
            <rect width="24" height="24" rx="4" fill="#003399" />
            {Array.from({ length: 12 }, (_, i) => {
              const a = (i * 30 - 90) * (Math.PI / 180);
              return <circle key={i} cx={12 + 8 * Math.cos(a)} cy={12 + 8 * Math.sin(a)} r={1.2} fill="#FFD617" />;
            })}
          </svg>
          <span className="text-[15px] font-semibold tracking-tight text-stone-800">
            ESGateway
          </span>
        </a>

        {/* Search */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search LEI..."
            className="h-8 w-52 rounded-full border-0 bg-stone-100/80 pl-8 pr-3 font-mono text-xs text-stone-600 placeholder:text-stone-400 transition-all focus:bg-white focus:outline-none focus:ring-1 focus:ring-stone-300"
          />
          <svg
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400"
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

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AERIS — Air Emissions Regional Intelligence System",
  description: "TEMPO Pollution Viewer and Weather Based Dispersion Modelling",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen bg-[#0a0a0a] text-[#fafafa]`}
      >
        <header className="border-b border-[#333] px-4 py-3">
          <nav className="max-w-[1080px] mx-auto flex items-center justify-between">
            <Link href="/" className="font-semibold hover:underline">
              AERIS
            </Link>
            <span className="text-sm text-[#888]">
              TEMPO Pollution Viewer
            </span>
          </nav>
        </header>
        <main className="max-w-[1080px] mx-auto px-4 py-6">
          {children}
        </main>
        <footer className="border-t border-[#333] mt-8 px-4 py-4 text-sm text-[#888]">
          <div className="max-w-[1080px] mx-auto">
            Cached data from TempData. Weather integration and pollutant movement prediction available when enabled.
          </div>
        </footer>
      </body>
    </html>
  );
}

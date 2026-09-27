import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const interSans = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin", "latin-ext"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "BetterSaul — Legal Intelligence Platform",
  description: "AI destekli Türkiye hukuk kaynakları araştırma ve dilekçe üretim platformu. Semantic search, içtihat analizi, otomatik dilekçe oluşturma.",
  keywords: ["hukuk", "legal", "AI", "içtihat", "dilekçe", "Yargıtay", "Danıştay", "AYM", "semantic search"],
  authors: [{ name: "BetterSaul" }],
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    title: "BetterSaul — Legal Intelligence Platform",
    description: "AI destekli hukuk araştırma ve dilekçe platformu",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body
        className={`${interSans.variable} ${plexMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}

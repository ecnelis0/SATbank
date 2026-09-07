import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Assistant } from "@/components/app/assistant";
import { Nav } from "@/components/app/nav";
import { MainArea, SidePanelProvider } from "@/components/app/side-panel";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Mistake Bank",
  description: "Every SAT question you got wrong, analysed and scheduled back.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Providers>
          <SidePanelProvider>
            <Nav />
            <MainArea>{children}</MainArea>
            <Assistant />
          </SidePanelProvider>
          <Toaster position="top-center" />
        </Providers>
      </body>
    </html>
  );
}

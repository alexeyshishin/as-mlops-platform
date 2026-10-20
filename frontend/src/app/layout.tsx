import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import localFont from "next/font/local";
import { DialogsRefreshProvider } from "@/components/DialogsRefreshProvider";
import { MobileSidebarProvider } from "@/components/MobileSidebarProvider";
import { MobileTopBar } from "@/components/MobileTopBar";
import { Sidebar } from "@/components/sidebar/Sidebar";
import "./globals.css";

const manrope = localFont({
  src: "../fonts/manrope/Manrope-VariableFont.ttf",
  weight: "200 800",
  variable: "--font-manrope",
  display: "swap",
});

const soyuzGrotesk = localFont({
  src: "../fonts/soyuz-grotesk/SoyuzGroteskBold.otf",
  weight: "700",
  variable: "--font-soyuz-grotesk",
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "глэк.ai",
  description: "MLOps intent routing",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ru"
      className={`${manrope.variable} ${soyuzGrotesk.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex h-screen overflow-hidden">
        <DialogsRefreshProvider>
          <MobileSidebarProvider>
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
              <MobileTopBar />
              <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
                {children}
              </main>
            </div>
          </MobileSidebarProvider>
        </DialogsRefreshProvider>
      </body>
    </html>
  );
}

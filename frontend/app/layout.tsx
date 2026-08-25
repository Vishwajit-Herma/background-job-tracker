import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "Background Job Tracker",
  description: "Monitor and manage background jobs seamlessly.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased text-foreground bg-background">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

const title = "Verity — Fact-checking Control Center";
const description =
  "Commercial administration, trust analytics, pipeline health, and safe database visibility for the Verity fact-checking platform.";

export const metadata: Metadata = {
  metadataBase: new URL("https://duong-xuan-ngan.github.io"),
  title,
  description,
  openGraph: {
    title,
    description,
    images: [
      {
        url: "/check-fake-news-extension/og.png",
        width: 1200,
        height: 630,
        alt: "Verity fact-checking control center",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/check-fake-news-extension/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" style={{ colorScheme: "light" }}>
      <body>{children}</body>
    </html>
  );
}

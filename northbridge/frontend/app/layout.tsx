import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Northbridge Intelligence — North East Property Intelligence Platform',
  description:
    'Northbridge Intelligence aggregates planning data, sold prices, and market signals across all North East councils — giving developers, investors, and planning consultants a serious edge.',
  keywords:
    'property intelligence, North East England, BMV deals, planning applications, property investment, Gateshead, Newcastle, Sunderland, Durham, Teesside',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body style={{ backgroundColor: '#090e1a', color: '#e2e8f0', margin: 0 }}>
        {children}
      </body>
    </html>
  )
}

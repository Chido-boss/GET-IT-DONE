// ── Outreach Desk Types ───────────────────────────────────────────────────────

export type DealSource = 'Rightmove' | 'Auction' | 'OTM' | 'Off-market' | 'Direct'
export type DealStrategy = 'flip' | 'light_refurb' | 'brrr' | 'btl' | 'income_hold' | 'hmo' | 'conversion' | 'auction'
export type Tier = 'S' | 'A' | 'B' | 'C'
export type OutreachStage = 'new' | 'contacted' | 'buyer_sent' | 'follow_up' | 'fee_locked' | 'passed'

export interface DealContact {
  agent_name: string
  agent_phone: string
  agency: string
}

export interface SourcingDeal {
  id: string
  address: string
  postcode: string
  council: string
  property_type: string
  bedrooms: number | null
  strategy: DealStrategy
  source: DealSource
  asking_price: number
  estimated_value: number | null
  gdv: number | null
  discount_pct: number | null
  refurb_cost: number | null
  net_profit: number | null
  roi_pct: number | null
  annual_yield: number | null
  monthly_cashflow: number | null
  overall_score: number
  tier: Tier
  tags: string[]
  days_on_market: number
  price_reductions: number
  contact: DealContact
  opportunity_notes: string
  risk_notes: string
  investor_teaser: string
  agent_script: string
}

export interface OutreachActivity {
  id: string
  timestamp: string
  action: string
  note?: string
}

export interface DealOutreachState {
  deal_id: string
  stage: OutreachStage
  buyer_sent: boolean
  follow_up: boolean
  fee_locked: boolean
  notes: string
  activity: OutreachActivity[]
  updated_at: string
}

export type PipelineMap = Record<string, DealOutreachState>

export interface PipelineFilters {
  search: string
  source: DealSource | ''
  strategy: DealStrategy | ''
  min_score: number | ''
  tier: Tier | ''
  stage: OutreachStage | ''
}

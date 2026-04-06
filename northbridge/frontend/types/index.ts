export interface Listing {
  id: string
  title: string
  address: string
  postcode: string
  council: string | null
  latitude: number | null
  longitude: number | null
  property_type: string // D/S/T/F/O/C
  tenure: string | null
  bedrooms: number | null
  asking_price: number
  previous_price: number | null
  date_listed: string | null
  days_on_market: number | null
  description: string | null
  url: string | null
  status: string
  agent_name: string | null
  price_reduction_count: number
  is_flagged: boolean
  score?: ListingScore
}

export interface ListingScore {
  overall_score: number
  bmv_score: number
  distress_score: number
  momentum_score: number
  planning_score: number
  regeneration_score: number
  confidence_score: number
  estimated_fair_value: number | null
  avg_comparable_price: number | null
  discount_pct: number | null
  score_drivers: ScoreDriver[]
}

export interface ScoreDriver {
  label: string
  impact: number
  icon: string
}

export interface PlanningApplication {
  id: string
  council: string
  application_reference: string
  address: string
  postcode: string | null
  application_type: string | null
  proposal: string | null
  status: string | null
  decision: string | null
  date_received: string | null
  uplift_score: number
  uplift_signals: string[] | null
  url: string | null
}

export interface RegenZone {
  id: string
  name: string
  council: string
  description: string | null
  status: string
  funding_amount: string | null
  announcement_date: string | null
  completion_date: string | null
  postcodes: string | null
  opportunity_notes: string | null
}

export interface AlertEvent {
  id: string
  message: string
  is_read: boolean
  created_at: string
  listing?: Listing
}

export interface DashboardStats {
  total_listings: number
  high_score_count: number
  planning_count: number
  alerts_this_week: number
  avg_score: number
  top_councils: Array<{ council: string; count: number }>
}

export interface User {
  id: string
  email: string
  full_name: string
  is_admin: boolean
}

export interface Deal {
  id: string
  title: string
  address: string
  postcode: string | null
  council: string | null
  property_type: string | null
  bedrooms: number | null
  strategy: string
  exit_strategy: string | null
  source: string | null
  days_on_market: number | null
  price_reductions: number | null

  // Financials
  purchase_price: number
  asking_price: number | null
  estimated_value: number | null
  gdv: number | null
  refurb_cost: number | null
  other_costs: number | null
  total_cost: number | null
  gross_profit: number | null
  net_profit: number | null
  profit: number | null
  roi: number | null
  roi_pct: number | null
  discount_pct: number | null
  annual_yield: number | null
  annual_yield_pct: number | null
  monthly_cashflow: number | null

  // Intelligence flags
  is_undervalued: boolean
  has_planning_upside: boolean
  is_high_roi: boolean
  is_distressed: boolean
  near_regen_zone: boolean

  // Component scores
  score_roi: number | null
  score_discount: number | null
  score_risk: number | null
  score_liquidity: number | null

  // Overall
  overall_score: number | null
  roi_score: number | null
  risk_score: number | null
  planning_uplift_score: number | null
  market_score: number | null
  score_drivers: any[] | null

  // Classification
  tier: string | null
  confidence: string | null
  risk_level: string | null

  // Context
  tags: string[] | null
  summary: string | null
  risk_notes: string | null
  opportunity_notes: string | null
  description: string | null

  status: string
  rank: number | null
  created_at: string
}

export interface DealsResponse {
  items: Deal[]
  total: number
  kpis: {
    active_deals: number
    avg_score: number
    top_strategy: string
    councils_covered: number
  }
}

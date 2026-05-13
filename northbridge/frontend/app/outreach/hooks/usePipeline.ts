'use client'

import { useState, useCallback, useMemo, useEffect } from 'react'
import type {
  SourcingDeal, DealOutreachState, PipelineMap,
  PipelineFilters, OutreachStage, OutreachActivity,
} from '../types'

const STORAGE_KEY = 'nb_outreach_pipeline_v1'

// ── Seed deals ────────────────────────────────────────────────────────────────

export const SEED_DEALS: SourcingDeal[] = [
  {
    id: 'd001',
    address: '14 Bensham Road, Gateshead',
    postcode: 'NE8 1AA', council: 'Gateshead',
    property_type: 'Terraced', bedrooms: 3,
    strategy: 'flip', source: 'Rightmove',
    asking_price: 62_000, estimated_value: 97_000, gdv: 97_000,
    discount_pct: 36.1, refurb_cost: 18_000, net_profit: 8_660, roi_pct: 10.6,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 72.4, tier: 'A',
    tags: ['Distressed', 'Chain Free', 'High BMV'],
    days_on_market: 91, price_reductions: 2,
    contact: { agent_name: 'John Mason', agent_phone: '0191 478 2200', agency: 'Reeds Rains Gateshead' },
    opportunity_notes: '3-bed mid-terrace in Bensham. Two price cuts in 91 days — vendor is motivated. Comparables at £95-100k once refurbed.',
    risk_notes: 'Full refurb required. Confirm structural survey before exchange. Buyer pool mainly investors.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n3-bed terraced, Bensham, Gateshead NE8 1AA\nAsk: £62,000 | Est. Value: £97,000 | Discount: 36%\nRefurb: ~£18k | Net Profit: ~£8.7k | ROI: ~10.6%\nStrategy: Flip | Tier: A | Score: 72\n\nVacant possession. Chain free. 2 price reductions. Motivated vendor.\nComparables: £95-100k post-refurb on same street.\n\nReply YES to receive full underwriting pack.\nNorthbridge Intelligence | northbridgeintel.co.uk`,
    agent_script: `Hi, is that ${'{agent_name}'}? This is [YOUR NAME] from Northbridge. I'm calling about the 3-bed at 14 Bensham Road listed at £62k.\n\nWe have investor clients actively looking in this area for this type of property. We can move quickly — cash buyer, no chain, could complete in 3-4 weeks.\n\nIs the vendor open to a conversation at £58,000? ... What's their main driver — speed or price?`,
  },
  {
    id: 'd002',
    address: '37 Ellison Road, Dunston, Gateshead',
    postcode: 'NE11 9PQ', council: 'Gateshead',
    property_type: 'Terraced', bedrooms: 2,
    strategy: 'light_refurb', source: 'Rightmove',
    asking_price: 74_000, estimated_value: 104_000, gdv: 104_000,
    discount_pct: 28.8, refurb_cost: 11_000, net_profit: 12_310, roi_pct: 14.0,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 78.1, tier: 'A',
    tags: ['Light Refurb', 'Chain Free', 'Quick Flip'],
    days_on_market: 54, price_reductions: 1,
    contact: { agent_name: 'Sarah Patel', agent_phone: '0191 460 3100', agency: 'Hunters Gateshead' },
    opportunity_notes: 'Cosmetic update only. Kitchen, bathroom, decoration. Refurbed 2-beds in Dunston sell at £100-110k reliably.',
    risk_notes: 'Get firm refurb quotes before exchange. Owner-occupier demand only — limited investor buyer pool.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n2-bed terraced, Dunston, Gateshead NE11 9PQ\nAsk: £74,000 | Est. Value: £104,000 | Discount: 29%\nRefurb: ~£11k (light touch) | Net Profit: ~£12.3k | ROI: ~14%\nStrategy: Light Refurb Flip | Tier: A | Score: 78\n\nChain free. 1 price reduction. Light cosmetic work only.\nTimeline: 10-12 weeks.\n\nReply YES to receive full underwriting pack.`,
    agent_script: `Hi, is that ${'{agent_name}'}? [YOUR NAME] from Northbridge.\n\nCalling about 37 Ellison Road, Dunston — the 2-bed at £74k.\n\nWe represent cash buyers looking for light-refurb opportunities in Gateshead. We can complete quickly.\n\nIs the vendor flexible? What's the lowest they'd accept for a quick cash sale?`,
  },
  {
    id: 'd003',
    address: '112 Fenham Hall Drive, Newcastle upon Tyne',
    postcode: 'NE4 9XB', council: 'Newcastle',
    property_type: 'Semi-Detached', bedrooms: 4,
    strategy: 'flip', source: 'Rightmove',
    asking_price: 115_000, estimated_value: 162_000, gdv: 162_000,
    discount_pct: 29.0, refurb_cost: 22_000, net_profit: 14_180, roi_pct: 10.1,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 69.3, tier: 'B',
    tags: ['4-Bed', 'Semi', 'Chain Free', 'Value-Add'],
    days_on_market: 67, price_reductions: 1,
    contact: { agent_name: 'Tom Bradley', agent_phone: '0191 273 8800', agency: 'Your Move Newcastle' },
    opportunity_notes: 'Large 4-bed semi in popular Fenham with good school catchment. 29% discount to comparable refurbed stock.',
    risk_notes: 'Heavier refurb at £22k — get fixed-price contracts. Owner-occupier buyer pool only.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n4-bed semi-detached, Fenham, Newcastle NE4 9XB\nAsk: £115,000 | Est. Value: £162,000 | Discount: 29%\nRefurb: ~£22k | Net Profit: ~£14.2k | ROI: ~10.1%\nStrategy: Flip | Tier: B | Score: 69\n\nChain free. Vacant possession. School catchment — strong owner-occupier demand.\n\nReply YES to receive full underwriting pack.`,
    agent_script: `Hi, this is [YOUR NAME] from Northbridge regarding 112 Fenham Hall Drive.\n\nWe have cash buyers for Fenham at this price point. 4-beds with school catchment are very sellable.\n\nVendor's situation — is it a sale due to relocation, probate? What's driving the timeline?`,
  },
  {
    id: 'd004',
    address: 'Flat 4, 89 Shields Road, Newcastle upon Tyne',
    postcode: 'NE6 1DL', council: 'Newcastle',
    property_type: 'Flat', bedrooms: 1,
    strategy: 'btl', source: 'Rightmove',
    asking_price: 55_000, estimated_value: 66_000, gdv: null,
    discount_pct: 16.7, refurb_cost: 3_500, net_profit: null, roi_pct: null,
    annual_yield: 8.7, monthly_cashflow: 230,
    overall_score: 67.2, tier: 'B',
    tags: ['BTL', 'High Yield', 'Metro Access'],
    days_on_market: 38, price_reductions: 0,
    contact: { agent_name: 'Karen Ellis', agent_phone: '0191 265 4400', agency: 'Purplebricks Newcastle' },
    opportunity_notes: 'Tenant in situ at £475/month. 8.7% gross yield. 400m from Byker Metro. 17% below estimated value.',
    risk_notes: 'Leasehold — verify service charge and ground rent. Capital growth may lag NE2/NE3.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n1-bed flat, Byker, Newcastle NE6 1DL\nAsk: £55,000 | Est. Value: £66,000 | Discount: 17%\nTenant in situ @ £475/mo | Yield: 8.7% gross\nStrategy: BTL | Tier: B | Score: 67\n\nNo void on completion. 400m from Metro. Leasehold 88 years.\n\nReply YES for full underwriting pack.`,
    agent_script: `Hi, this is [YOUR NAME] from Northbridge. Calling about Flat 4, 89 Shields Road.\n\nWe have investors specifically looking for tenanted BTL properties in NE6. What's the current rent — is the tenancy periodic or fixed term?\n\nAny flexibility on the £55k ask for a quick cash buyer?`,
  },
  {
    id: 'd005',
    address: '5 Framwellgate, Durham',
    postcode: 'DH1 5TU', council: 'Durham',
    property_type: 'Terraced', bedrooms: 2,
    strategy: 'btl', source: 'Rightmove',
    asking_price: 98_000, estimated_value: 118_000, gdv: null,
    discount_pct: 16.9, refurb_cost: 6_000, net_profit: null, roi_pct: null,
    annual_yield: 6.8, monthly_cashflow: 200,
    overall_score: 59.8, tier: 'C',
    tags: ['Durham City', 'Heritage', 'Capital Growth'],
    days_on_market: 45, price_reductions: 0,
    contact: { agent_name: 'Paul Nicholson', agent_phone: '0191 384 6550', agency: 'Dowen Durham' },
    opportunity_notes: 'Cathedral city cottage. University staff/postgrad tenant demand year-round. 17% below estimated value.',
    risk_notes: 'Low cashflow at £200/month — interest rate sensitivity elevated. Heritage zone may restrict works.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n2-bed cottage, Durham City DH1 5TU\nAsk: £98,000 | Est. Value: £118,000 | Discount: 17%\nYield: 6.8% | Cashflow: ~£200/mo\nStrategy: BTL / Capital Growth | Score: 60\n\nDurham city rents up 12% in 24 months. University demand year-round.\n\nReply YES for full underwriting pack.`,
    agent_script: `Hi, this is [YOUR NAME] from Northbridge regarding the cottage at 5 Framwellgate, Durham.\n\nWe represent investors looking for long-term income properties in Durham city. Is the vendor open to a conversation below asking price for a quick chain-free sale?`,
  },
  {
    id: 'd006',
    address: '19 Osborne Road, Jesmond, Newcastle',
    postcode: 'NE2 2AL', council: 'Newcastle',
    property_type: 'Detached', bedrooms: 5,
    strategy: 'income_hold', source: 'Off-market',
    asking_price: 320_000, estimated_value: 340_000, gdv: null,
    discount_pct: 5.9, refurb_cost: 15_000, net_profit: null, roi_pct: null,
    annual_yield: 11.2, monthly_cashflow: 1_850,
    overall_score: 74.9, tier: 'A',
    tags: ['HMO', 'Jesmond', 'High Yield', 'Off-Market'],
    days_on_market: 29, price_reductions: 0,
    contact: { agent_name: 'Marcus Webb', agent_phone: '0191 281 7700', agency: 'Direct / Off-market' },
    opportunity_notes: '5-room HMO in prime Jesmond. £740/room. 11.2% gross yield. Off-market — vendor retiring from property.',
    risk_notes: 'Article 4 applies in Jesmond — HMO licence essential. Management complexity vs BTL.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — OFF-MARKET ALERT\n\n5-bed HMO, Jesmond, Newcastle NE2 2AL\nAsk: £320,000 | Yield: 11.2% | Cashflow: ~£1,850/mo\nRooms: 5 @ ~£740/mo | Strategy: Income Hold | Score: 75\n\nOff-market. Vendor retiring. No chain. Quick completion preferred.\nArticle 4 area — licence required.\n\nReply YES for introduction.`,
    agent_script: `Hi Marcus, this is [YOUR NAME] from Northbridge. Following up on the Jesmond HMO opportunity.\n\nWe have qualified HMO investors who understand Article 4 and can move quickly. What's the vendor's preferred timeline — and are they open to any negotiation on the £320k?`,
  },
  {
    id: 'd007',
    address: '34 Welbeck Road, Walker, Newcastle',
    postcode: 'NE6 3PB', council: 'Newcastle',
    property_type: 'Terraced', bedrooms: 4,
    strategy: 'income_hold', source: 'Direct',
    asking_price: 78_000, estimated_value: 84_000, gdv: null,
    discount_pct: 7.1, refurb_cost: 10_000, net_profit: null, roi_pct: null,
    annual_yield: 14.5, monthly_cashflow: 920,
    overall_score: 81.2, tier: 'S',
    tags: ['HMO', 'Licensed', 'S-Tier', 'Top Yield'],
    days_on_market: 14, price_reductions: 0,
    contact: { agent_name: 'Darren Shaw', agent_phone: '07712 445 890', agency: 'Direct from Vendor' },
    opportunity_notes: '4-bed licensed HMO at 14.5% gross yield. Rooms at £400-430/mo. Vendor retiring — urgency is real.',
    risk_notes: 'Walker is improving but manage tenant quality carefully. Stress-test refurb costs on-site.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — S-TIER DEAL ALERT\n\n4-bed Licensed HMO, Walker, Newcastle NE6 3PB\nAsk: £78,000 | Yield: 14.5% | Cashflow: ~£920/mo\nLicensed and operational | Strategy: Income Hold | Score: 81\n\nDIRECT vendor contact. Vendor retiring — preferred quick completion.\nLowest achievable yield in NE at this price point.\n\nReply YES immediately — this will not last.`,
    agent_script: `Hi Darren, this is [YOUR NAME] from Northbridge.\n\nThank you for reaching out about Welbeck Road. 14.5% yield at this price is exceptional.\n\nOur investors are highly motivated to move quickly. Can we arrange a viewing this week? And is there any flexibility at all on the £78,000?`,
  },
  {
    id: 'd008',
    address: '22 Fawcett Street, Sunderland',
    postcode: 'SR1 1RH', council: 'Sunderland',
    property_type: 'Flat', bedrooms: 2,
    strategy: 'flip', source: 'Auction',
    asking_price: 48_000, estimated_value: 75_000, gdv: 75_000,
    discount_pct: 36.0, refurb_cost: 14_000, net_profit: 5_860, roi_pct: 9.0,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 68.4, tier: 'B',
    tags: ['Executor Sale', 'Auction', 'Sunderland Riverside'],
    days_on_market: 78, price_reductions: 2,
    contact: { agent_name: 'Rachel Holt', agent_phone: '0191 510 7700', agency: 'Auction House North East' },
    opportunity_notes: 'Executor sale. 36% below comparable refurbed flats. Sunderland Riverside regen zone.',
    risk_notes: 'Auction — finance must be arranged before bidding. Check lease terms carefully.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — AUCTION ALERT\n\n2-bed flat, Sunderland City SR1 1RH\nGuide: £48,000 | Est. Value: £75,000 | Discount: 36%\nRefurb: ~£14k | Net Profit: ~£5.9k\nExecutor sale. Sunderland Riverside regen zone.\n\nAuction — finance must be pre-arranged. Reply YES for pack.`,
    agent_script: `Hi Rachel, [YOUR NAME] from Northbridge.\n\nWe have investors registered for the Fawcett Street auction lot. Can you confirm the guide is £48k?\n\nIs there any legal pack available to view now? We want to bring a qualified buyer to the auction.`,
  },
  {
    id: 'd009',
    address: '14 Milburn Road, Ashington, Northumberland',
    postcode: 'NE63 0RL', council: 'Northumberland',
    property_type: 'Semi-Detached', bedrooms: 3,
    strategy: 'light_refurb', source: 'Rightmove',
    asking_price: 67_000, estimated_value: 94_000, gdv: 94_000,
    discount_pct: 28.7, refurb_cost: 10_000, net_profit: 10_260, roi_pct: 12.1,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 73.6, tier: 'A',
    tags: ['Northumberland', 'Light Refurb', 'High ROI'],
    days_on_market: 112, price_reductions: 2,
    contact: { agent_name: 'Claire Morton', agent_phone: '01670 814 700', agency: 'Rook Matthews Sayer Ashington' },
    opportunity_notes: '3-bed semi, 29% below comparables. Two price reductions in 112 days. Vendor negotiable.',
    risk_notes: 'Smaller market — buyer pool mainly local. Confirm heating system condition.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n3-bed semi, Ashington, Northumberland NE63 0RL\nAsk: £67,000 | Est. Value: £94,000 | Discount: 29%\nRefurb: ~£10k (light) | Net Profit: ~£10.3k | ROI: ~12%\n\n2 price reductions. 112 days on market. Vendor ready to deal.\n\nReply YES for full underwriting pack.`,
    agent_script: `Hi Claire, this is [YOUR NAME] from Northbridge.\n\nCalling about the 3-bed semi on Milburn Road — 112 days on, two reductions. We represent cash buyers for NE63.\n\nOur client is looking at £62,000 for quick completion. Is that a conversation the vendor would have?`,
  },
  {
    id: 'd010',
    address: '22 Grange Road, Hartlepool',
    postcode: 'TS24 8EY', council: 'Hartlepool',
    property_type: 'Terraced', bedrooms: 3,
    strategy: 'auction', source: 'Auction',
    asking_price: 55_000, estimated_value: 79_000, gdv: 79_000,
    discount_pct: 30.4, refurb_cost: 14_000, net_profit: 3_530, roi_pct: 5.0,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 63.8, tier: 'B',
    tags: ['Auction', 'Marina Regen', 'Flexible Exit'],
    days_on_market: 22, price_reductions: 0,
    contact: { agent_name: 'Mike Faraday', agent_phone: '01429 862 100', agency: 'auction.co.uk Hartlepool' },
    opportunity_notes: 'Near Hartlepool Marina regen zone. Dual exit: flip or BTL (8-10% yield in TS24).',
    risk_notes: 'Auction — 28-day completion. Finance pre-arranged required.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — AUCTION ALERT\n\n3-bed terrace, Hartlepool TS24 8EY\nGuide: £55,000 | Est. Value: £79,000 | Discount: 30%\nMarina regen zone. Flip or BTL dual exit.\nBTL yield in TS24: 8-10%.\n\nReply YES for legal pack.`,
    agent_script: `Hi Mike, this is [YOUR NAME] from Northbridge regarding the Grange Road lot.\n\nWe have registered buyers for Hartlepool auctions. Is the legal pack ready to view?\n\nAny indication of where the vendor's reserve sits?`,
  },
  {
    id: 'd011',
    address: '38 High Street West, Sunderland',
    postcode: 'SR1 3EX', council: 'Sunderland',
    property_type: 'Commercial', bedrooms: null,
    strategy: 'conversion', source: 'Off-market',
    asking_price: 95_000, estimated_value: null, gdv: 280_000,
    discount_pct: null, refurb_cost: 120_000, net_profit: 31_250, roi_pct: 14.5,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 71.8, tier: 'A',
    tags: ['Commercial Conv.', 'Class MA', 'Riverside Regen', 'High GDV'],
    days_on_market: 55, price_reductions: 0,
    contact: { agent_name: 'Terry Lamb', agent_phone: '0191 565 8800', agency: 'Commercial Direct' },
    opportunity_notes: 'Former retail, 1,200 sqft. Class MA prior approval route. GDV £280k as 3-4 units. Sunderland Riverside zone.',
    risk_notes: 'Planning required. Heavy budget. Contractor management is key risk.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — CONVERSION OPPORTUNITY\n\nFormer Retail, Sunderland City Centre SR1 3EX\nAsk: £95,000 | GDV (3-4 units): ~£280,000\nRefurb: ~£120k | Net Profit: ~£31k | ROI: ~14.5%\nClass MA prior approval route | Riverside Regen Zone\n\nReply YES for full development appraisal.`,
    agent_script: `Hi Terry, this is [YOUR NAME] from Northbridge.\n\nWe're looking at the High Street West unit for residential conversion under Class MA.\n\nHas prior approval been explored? What's the vendor's flexibility on the £95k ask for a developer client?`,
  },
  {
    id: 'd012',
    address: '7 Dunston Road, Gateshead',
    postcode: 'NE8 4AQ', council: 'Gateshead',
    property_type: 'Terraced', bedrooms: 3,
    strategy: 'brrr', source: 'Rightmove',
    asking_price: 72_000, estimated_value: 115_000, gdv: 115_000,
    discount_pct: 37.4, refurb_cost: 20_000, net_profit: 14_790, roi_pct: 14.5,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 78.9, tier: 'A',
    tags: ['BRRR', 'High BMV', 'Refinance Play', 'Gateshead'],
    days_on_market: 43, price_reductions: 1,
    contact: { agent_name: 'Sue Carroll', agent_phone: '0191 460 1100', agency: 'Countrywide Gateshead' },
    opportunity_notes: 'Strong BRRR. Post-refurb valuation ~£115k. Refinance at 75% LTV returns ~£86k. Rental demand strong at £650-700/mo.',
    risk_notes: 'Refinance valuation is hinge point — confirm with surveyor. Conservative ARV recommended.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — BRRR DEAL\n\n3-bed terrace, Gateshead NE8 4AQ\nAsk: £72,000 | ARV: ~£115,000 | Discount: 37%\nRefurb: ~£20k | Net Profit: ~£14.8k | ROI: ~14.5%\nBRRR: Refinance at 75% LTV recovers ~£86k capital\n\nChain free. Cash buyers. 1 price reduction.\n\nReply YES for full underwriting.`,
    agent_script: `Hi Sue, this is [YOUR NAME] from Northbridge. We have a BRRR investor looking specifically for NE8 terraces.\n\nThe Dunston Road property at £72k — any room to negotiate for a quick cash buyer? We're aiming for £67-68k.`,
  },
  {
    id: 'd013',
    address: '16 Renwick Road, Blyth, Northumberland',
    postcode: 'NE24 2RR', council: 'Northumberland',
    property_type: 'Terraced', bedrooms: 2,
    strategy: 'light_refurb', source: 'Rightmove',
    asking_price: 58_000, estimated_value: 82_000, gdv: 82_000,
    discount_pct: 29.3, refurb_cost: 9_000, net_profit: 9_080, roi_pct: 12.9,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 76.3, tier: 'A',
    tags: ['Blyth Estuary Zone', 'Regen', 'Light Refurb'],
    days_on_market: 88, price_reductions: 1,
    contact: { agent_name: 'Neil Forster', agent_phone: '01670 353 636', agency: 'Rook Matthews Sayer Blyth' },
    opportunity_notes: 'Within Blyth Estuary regen zone. 29% below comparables. Light cosmetic work only. Port investment driving appreciation.',
    risk_notes: 'Smaller market — confirm rental demand if BTL fallback. Buyer pool narrower than Newcastle.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — REGEN ZONE DEAL\n\n2-bed terrace, Blyth NE24 2RR — Blyth Estuary Regen Zone\nAsk: £58,000 | Est. Value: £82,000 | Discount: 29%\nRefurb: ~£9k (cosmetic) | Net Profit: ~£9k | ROI: ~13%\n\nBlyth Estuary investment driving appreciation. 88 days, 1 price cut.\n\nReply YES for full underwriting.`,
    agent_script: `Hi Neil, [YOUR NAME] from Northbridge regarding Renwick Road. 88 days on with one reduction — vendor ready to move?\n\nCash buyer. We can complete in 4 weeks. Is £54,000 a conversation?`,
  },
  {
    id: 'd014',
    address: '88 Toward Road, Sunderland',
    postcode: 'SR2 7EH', council: 'Sunderland',
    property_type: 'Terraced', bedrooms: 4,
    strategy: 'income_hold', source: 'Direct',
    asking_price: 88_000, estimated_value: 96_000, gdv: null,
    discount_pct: 8.3, refurb_cost: 8_000, net_profit: null, roi_pct: null,
    annual_yield: 13.8, monthly_cashflow: 780,
    overall_score: 75.5, tier: 'A',
    tags: ['HMO', 'Licensed', 'Student Quarter', 'High Yield'],
    days_on_market: 31, price_reductions: 0,
    contact: { agent_name: 'Kim Davison', agent_phone: '07891 234 567', agency: 'Direct from Vendor' },
    opportunity_notes: '4-room licensed HMO. 4 rooms @ £450/mo. £1,800 gross income. 13.8% yield.',
    risk_notes: 'Student demand seasonal — ensure ASTs have summer holding provisions.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — HMO INCOME DEAL\n\n4-bed Licensed HMO, Sunderland University SR2 7EH\nAsk: £88,000 | Yield: 13.8% | Cashflow: ~£780/mo\n4 rooms @ £450/mo | Licensed and operational\n\nDirect vendor. No chain. Quick completion.\n\nReply YES for introduction.`,
    agent_script: `Hi Kim, [YOUR NAME] from Northbridge — following up on the Toward Road HMO.\n\nOur investors love the 13.8% yield. What's the current licence status — and is the vendor open at all on price for a quick cash sale?`,
  },
  {
    id: 'd015',
    address: '45 Commercial Road, South Shields',
    postcode: 'NE33 1RQ', council: 'South Tyneside',
    property_type: 'Terraced', bedrooms: 3,
    strategy: 'flip', source: 'OTM',
    asking_price: 68_000, estimated_value: 98_000, gdv: 98_000,
    discount_pct: 30.6, refurb_cost: 16_000, net_profit: 6_790, roi_pct: 7.9,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 65.1, tier: 'B',
    tags: ['South Shields', 'Waterfront Zone', 'Chain Free'],
    days_on_market: 74, price_reductions: 1,
    contact: { agent_name: 'Jade Lawson', agent_phone: '0191 455 1300', agency: 'Peter Heron South Shields' },
    opportunity_notes: 'Near South Shields waterfront regen scheme. 31% below comparables. 74 days on — vendor negotiable.',
    risk_notes: 'South Shields market slower than Newcastle; plan for 3-4 month flip timeline.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n3-bed terrace, South Shields NE33 1RQ\nAsk: £68,000 | Est. Value: £98,000 | Discount: 31%\nRefurb: ~£16k | Net Profit: ~£6.8k\nNear South Shields Waterfront regen zone.\n\nReply YES for full underwriting.`,
    agent_script: `Hi Jade, [YOUR NAME] from Northbridge. The 3-bed on Commercial Road — 74 days, one price cut.\n\nWe have cash buyers for South Shields at this price point. Would the vendor take £63k for a 3-4 week completion?`,
  },
  {
    id: 'd016',
    address: 'Flat 1, 3 Ocean Road, South Shields',
    postcode: 'NE33 2JA', council: 'South Tyneside',
    property_type: 'Flat', bedrooms: 1,
    strategy: 'auction', source: 'Auction',
    asking_price: 42_000, estimated_value: 68_000, gdv: 68_000,
    discount_pct: 38.2, refurb_cost: 12_000, net_profit: 5_220, roi_pct: 9.3,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 70.2, tier: 'A',
    tags: ['Auction', 'Probate', 'Seafront', 'Deep BMV'],
    days_on_market: 18, price_reductions: 0,
    contact: { agent_name: 'Lisa Parke', agent_phone: '0191 447 8800', agency: 'Auction House NE' },
    opportunity_notes: 'Probate sale. 38% below comparables. Seafront location. Near South Shields Waterfront regen zone.',
    risk_notes: 'Leasehold flat — check lease length and service charge. Auction — pre-arranged finance required.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — AUCTION PROBATE\n\n1-bed flat, South Shields Seafront NE33 2JA\nGuide: £42,000 | Est. Value: £68,000 | Discount: 38%\nProbate sale. Seafront. Waterfront regen zone.\nRefurb: ~£12k | Net Profit: ~£5.2k\n\nReply YES for legal pack.`,
    agent_script: `Hi Lisa, [YOUR NAME] from Northbridge. Registering interest in the Ocean Road lot — guide £42k.\n\nIs the legal pack available? We want to bring a qualified cash buyer. Is there a reserve above guide?`,
  },
  {
    id: 'd017',
    address: '67 Linthorpe Road, Middlesbrough',
    postcode: 'TS1 3QQ', council: 'Middlesbrough',
    property_type: 'Semi-Detached', bedrooms: 3,
    strategy: 'auction', source: 'Auction',
    asking_price: 68_000, estimated_value: 92_000, gdv: 92_000,
    discount_pct: 26.1, refurb_cost: 16_000, net_profit: 2_730, roi_pct: 3.2,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 57.4, tier: 'C',
    tags: ['Auction', 'Middlesbrough', 'Chain Free'],
    days_on_market: 15, price_reductions: 0,
    contact: { agent_name: 'Craig Bourne', agent_phone: '01642 222 400', agency: 'Pattinson Middlesbrough' },
    opportunity_notes: 'Auction lot. 26% below comparables. Chain free with vacant possession.',
    risk_notes: 'Thin margin at guide price — do not overpay at auction. ROI only works below £65k.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — AUCTION ALERT\n\n3-bed semi, Middlesbrough TS1 3QQ\nGuide: £68,000 | Est. Value: £92,000 | Discount: 26%\nTight margin — only viable under £65k.\n\nAuction — pre-arrange finance.`,
    agent_script: `Hi Craig, [YOUR NAME] from Northbridge. What's the feedback on the Linthorpe Road lot? Reserve price — any steer on that?`,
  },
  {
    id: 'd018',
    address: '31 Pallion New Road, Sunderland',
    postcode: 'SR4 6QD', council: 'Sunderland',
    property_type: 'Terraced', bedrooms: 3,
    strategy: 'flip', source: 'Rightmove',
    asking_price: 58_000, estimated_value: 88_000, gdv: 88_000,
    discount_pct: 34.1, refurb_cost: 15_000, net_profit: 6_910, roi_pct: 9.1,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 66.3, tier: 'B',
    tags: ['Sunderland', 'High BMV', 'Full Refurb'],
    days_on_market: 63, price_reductions: 1,
    contact: { agent_name: 'Angela Smart', agent_phone: '0191 534 1100', agency: 'Hunters Sunderland' },
    opportunity_notes: '34% below comparables. 63 days with one reduction. Vendor motivated.',
    risk_notes: 'Full refurb needed. Pallion area — confirm buyer pool depth before proceeding.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n3-bed terrace, Pallion, Sunderland SR4 6QD\nAsk: £58,000 | Est. Value: £88,000 | Discount: 34%\nRefurb: ~£15k | Net Profit: ~£6.9k\n\n63 days, 1 price cut. Vendor motivated.\n\nReply YES for full pack.`,
    agent_script: `Hi Angela, [YOUR NAME] from Northbridge. The Pallion New Road property — 63 days on. Cash buyer, can complete in 3-4 weeks. What's the vendor's bottom line?`,
  },
  {
    id: 'd019',
    address: '18 Station Road, Washington, Tyne and Wear',
    postcode: 'NE38 7PQ', council: 'Sunderland',
    property_type: 'Semi-Detached', bedrooms: 3,
    strategy: 'flip', source: 'Rightmove',
    asking_price: 89_000, estimated_value: 126_000, gdv: 126_000,
    discount_pct: 29.4, refurb_cost: 18_000, net_profit: 9_890, roi_pct: 8.7,
    annual_yield: null, monthly_cashflow: null,
    overall_score: 65.7, tier: 'B',
    tags: ['Washington', 'Semi', 'Chain Free'],
    days_on_market: 55, price_reductions: 1,
    contact: { agent_name: 'Gary Hewitt', agent_phone: '0191 416 0600', agency: 'Bridgefords Washington' },
    opportunity_notes: '3-bed semi, 29% below comparables. Washington has strong owner-occupier demand. Chain free.',
    risk_notes: 'Refurb at £18k — get fixed-price quotes. Market can be slower than Newcastle.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — DEAL ALERT\n\n3-bed semi, Washington NE38 7PQ\nAsk: £89,000 | Est. Value: £126,000 | Discount: 29%\nRefurb: ~£18k | Net Profit: ~£9.9k\n\nChain free. 1 price reduction. Strong area demand.\n\nReply YES for full underwriting.`,
    agent_script: `Hi Gary, [YOUR NAME] from Northbridge. The Station Road semi in Washington — cash buyer, no chain, 4-week completion. Would the vendor consider £84,000?`,
  },
  {
    id: 'd020',
    address: '4 Ellison Street, Jarrow',
    postcode: 'NE32 3JR', council: 'South Tyneside',
    property_type: 'Terraced', bedrooms: 2,
    strategy: 'btl', source: 'OTM',
    asking_price: 42_000, estimated_value: 58_000, gdv: null,
    discount_pct: 27.6, refurb_cost: 5_000, net_profit: null, roi_pct: null,
    annual_yield: 9.5, monthly_cashflow: 165,
    overall_score: 62.1, tier: 'B',
    tags: ['BTL', 'Jarrow', 'Low Entry', 'High Yield'],
    days_on_market: 102, price_reductions: 2,
    contact: { agent_name: 'Tim Gray', agent_phone: '0191 489 0011', agency: 'Peter Heron Jarrow' },
    opportunity_notes: 'Very low entry point. 9.5% gross yield. 27% below estimated value. 102 days on — vendor very negotiable.',
    risk_notes: 'Jarrow — modest capital growth expectations. Tenant quality management important.',
    investor_teaser: `NORTHBRIDGE INTELLIGENCE — LOW ENTRY BTL\n\n2-bed terrace, Jarrow NE32 3JR\nAsk: £42,000 | Est. Value: £58,000 | Discount: 28%\nYield: 9.5% | Cashflow: ~£165/mo\n\n102 days, 2 price cuts. Very negotiable vendor.\n\nReply YES for full pack.`,
    agent_script: `Hi Tim, [YOUR NAME] from Northbridge. 102 days on market with two cuts — vendor clearly wants out. Cash buyer, quick completion. Would they take £38,000?`,
  },
]

// ── Default outreach state ────────────────────────────────────────────────────

function defaultState(deal_id: string): DealOutreachState {
  return {
    deal_id,
    stage: 'new',
    buyer_sent: false,
    follow_up: false,
    fee_locked: false,
    notes: '',
    activity: [],
    updated_at: new Date().toISOString(),
  }
}

function makeActivityEntry(action: string, note?: string): OutreachActivity {
  return {
    id: Math.random().toString(36).slice(2),
    timestamp: new Date().toISOString(),
    action,
    note,
  }
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function usePipeline() {
  const [pipeline, setPipeline] = useState<PipelineMap>({})
  const [filters, setFilters] = useState<PipelineFilters>({
    search: '', source: '', strategy: '', min_score: '', tier: '', stage: '',
  })

  // Load from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) setPipeline(JSON.parse(raw))
    } catch { /* ignore */ }
  }, [])

  // Persist to localStorage
  const savePipeline = useCallback((next: PipelineMap) => {
    setPipeline(next)
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* ignore */ }
  }, [])

  const getDealState = useCallback((id: string): DealOutreachState => {
    return pipeline[id] || defaultState(id)
  }, [pipeline])

  const updateDealState = useCallback((id: string, updates: Partial<DealOutreachState>, activityNote?: string) => {
    const current = pipeline[id] || defaultState(id)
    const activity = activityNote
      ? [makeActivityEntry(activityNote), ...current.activity].slice(0, 50)
      : current.activity
    const next = { ...pipeline, [id]: { ...current, ...updates, activity, updated_at: new Date().toISOString() } }
    savePipeline(next)
  }, [pipeline, savePipeline])

  const setStage = useCallback((id: string, stage: OutreachStage) => {
    updateDealState(id, { stage }, `Stage → ${stage.replace('_', ' ')}`)
  }, [updateDealState])

  const toggleBuyerSent = useCallback((id: string) => {
    const current = getDealState(id)
    const next = !current.buyer_sent
    updateDealState(id, { buyer_sent: next }, next ? 'Buyer Sent ✓' : 'Buyer Sent removed')
  }, [getDealState, updateDealState])

  const toggleFollowUp = useCallback((id: string) => {
    const current = getDealState(id)
    const next = !current.follow_up
    updateDealState(id, { follow_up: next }, next ? 'Follow Up flagged' : 'Follow Up cleared')
  }, [getDealState, updateDealState])

  const toggleFeeLocked = useCallback((id: string) => {
    const current = getDealState(id)
    const next = !current.fee_locked
    updateDealState(id, {
      fee_locked: next,
      stage: next ? 'fee_locked' : getDealState(id).stage,
    }, next ? '🔒 Fee Locked!' : 'Fee Locked removed')
  }, [getDealState, updateDealState])

  const setNotes = useCallback((id: string, notes: string) => {
    const current = pipeline[id] || defaultState(id)
    const next = { ...pipeline, [id]: { ...current, notes, updated_at: new Date().toISOString() } }
    savePipeline(next)
  }, [pipeline, savePipeline])

  // Filtered deals
  const filteredDeals = useMemo(() => {
    return SEED_DEALS.filter(deal => {
      const state = pipeline[deal.id] || defaultState(deal.id)
      if (filters.search) {
        const q = filters.search.toLowerCase()
        if (!deal.address.toLowerCase().includes(q) &&
            !deal.council.toLowerCase().includes(q) &&
            !deal.strategy.toLowerCase().includes(q) &&
            !deal.postcode.toLowerCase().includes(q)) return false
      }
      if (filters.source && deal.source !== filters.source) return false
      if (filters.strategy && deal.strategy !== filters.strategy) return false
      if (filters.tier && deal.tier !== filters.tier) return false
      if (filters.stage && state.stage !== filters.stage) return false
      if (filters.min_score !== '' && deal.overall_score < Number(filters.min_score)) return false
      return true
    })
  }, [filters, pipeline])

  // Stats
  const stats = useMemo(() => {
    const stageCounts: Record<string, number> = {
      new: 0, contacted: 0, buyer_sent: 0, follow_up: 0, fee_locked: 0, passed: 0,
    }
    const feeLockedDeals: SourcingDeal[] = []
    for (const deal of SEED_DEALS) {
      const state = pipeline[deal.id] || defaultState(deal.id)
      stageCounts[state.stage] = (stageCounts[state.stage] || 0) + 1
      if (state.fee_locked) feeLockedDeals.push(deal)
    }
    const avgScore = SEED_DEALS.reduce((s, d) => s + d.overall_score, 0) / SEED_DEALS.length
    const sTier = SEED_DEALS.filter(d => d.tier === 'S').length
    const potentialRevenue = feeLockedDeals.length * 3500  // £3,500 avg sourcing fee estimate
    return { stageCounts, avgScore: avgScore.toFixed(1), sTier, potentialRevenue, feeLockedDeals }
  }, [pipeline])

  return {
    deals: SEED_DEALS,
    filteredDeals,
    filters,
    setFilters,
    getDealState,
    updateDealState,
    setStage,
    toggleBuyerSent,
    toggleFollowUp,
    toggleFeeLocked,
    setNotes,
    stats,
    pipelineCount: SEED_DEALS.length,
  }
}

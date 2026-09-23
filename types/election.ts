export type EntityType = 'candidate' | 'party' | 'option' | 'other'

export type UnitKind =
  | 'precinct'
  | 'territorial_commission'
  | 'district'
  | 'municipality'
  | 'region'
  | 'national'
  | 'other'

export interface ElectionEntity {
  id: string
  name: string
  type: EntityType
  party_id?: string
  party_name?: string
}

export interface ElectionResultRow {
  entity: ElectionEntity
  votes: number
}

export interface ElectionUnit {
  id: string
  name: string
  number?: string
  kind: UnitKind
  administrative_path?: ElectionUnit[]
}

export interface Turnout {
  registered: number
  issued: number
  valid: number
  invalid: number
}

export interface ResultFile {
  standard: 'vibori-election-result/v1'
  source?: {
    url?: string
    retrieved_at?: string
    publisher?: string
  }
  election: {
    id: string
    name: string
    country: string
    date: string
    scope?: 'national' | 'regional' | 'municipal' | 'other'
  }
  unit: ElectionUnit
  ballot: {
    id: string
    title: string
    kind: 'party_list' | 'single_member' | 'referendum' | 'ranked' | 'other'
  }
  turnout: Turnout
  results: ElectionResultRow[]
}

export interface AggregatedRow extends ElectionEntity {
  votes: number
}

export interface AggregateResult {
  turnout: Turnout
  rows: AggregatedRow[]
}

export interface CatalogUnit {
  id: string
  name: string
  number?: string
  count: number
  kind: UnitKind
}

export interface CatalogPrecinct {
  id: string
  name: string
  number?: string
  region: string
}

export interface OfficialResultEntry {
  file: string
  unit: ElectionUnit
}

export interface CatalogElection {
  id: string
  name: string
  date: string
  country: string
  scope?: 'national' | 'regional' | 'municipal' | 'other'
  ballot_title: string
  ballot_kind?: ResultFile['ballot']['kind']
  national_id: string
  precinct_count: number
  region_count: number
}

export interface ElectionCatalogDetail extends CatalogElection {
  entities: ElectionEntity[]
  official_results: Record<string, string>
  computed_results: Record<string, string>
  tree_root: string
  precinct_pages: number
  candidates_file?: string
}

export interface CandidateSummary {
  id: string
  name: string
  party_id?: string
  party_name?: string
  district_number?: number | string
  regional_group?: string
  number_in_list?: number
  status?: string
}

export interface CandidateRecord extends CandidateSummary {
  standard: 'vibori-candidate/v1'
  election_id: string
  source: { url: string, retrieved_at: string, publisher?: string }
  party?: { id: string, name: string } | null
  birth_date?: string
  birth_place?: string
  address?: string
  education?: string
  work?: string
  position?: string
  convictions?: unknown[] | string | null
  foreign_agent?: unknown
  candidate_vrn?: string
  nomination?: string
  registration?: string
  registration_date?: string
}

export interface PartyRecord {
  id: string
  name: string
  logo: string
  aliases?: string[]
  source: { url: string, retrieved_at: string, publisher?: string }
}

export type AnalysisPoint = [turnout: number, valid: number, results: number[]]

export interface NationalChartAnalysis {
  standard: 'vibori-chart-analysis/v2' | 'vibori-chart-analysis/v3'
  entities: ElectionEntity[]
  points?: AnalysisPoint[]
  clusters?: Array<Array<[turnout: number, votes: number, count: number]>>
  absolute?: Array<Array<[turnout: number, votes: number, count: number]>>
  absolute1?: Array<Array<[turnout: number, votes: number, count: number]>>
  absoluteRaw?: Array<Array<[turnout: number, votes: number, count: number]>>
}

export interface RegionalChartAnalysis {
  standard: 'vibori-chart-analysis/v2' | 'vibori-chart-analysis/v3'
  points: AnalysisPoint[]
  units: Record<string, number[]>
  clusters?: Array<Array<[turnout: number, votes: number, count: number]>>
  absolute?: Array<Array<[turnout: number, votes: number, count: number]>>
  absolute1?: Array<Array<[turnout: number, votes: number, count: number]>>
}

export interface ElectionCatalog {
  standard: 'vibori-catalog/v1'
  generated_at: string
  elections: CatalogElection[]
}

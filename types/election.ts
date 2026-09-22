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
  count: number
  kind: UnitKind
}

export interface CatalogPrecinct {
  id: string
  name: string
  number?: string
  region: string
  file: string
  path_ids: string[]
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
  ballot_title: string
  national_id: string
  files: string[]
  official_results?: Record<string, OfficialResultEntry>
  precinct_count: number
  regions: CatalogUnit[]
  districts: CatalogUnit[]
  tiks: CatalogUnit[]
  region_count: number
  precincts: CatalogPrecinct[]
}

export interface ElectionCatalog {
  standard: 'vibori-catalog/v1'
  generated_at: string
  elections: CatalogElection[]
}

import type { AggregateResult, AggregatedRow, CandidateSummary, ElectionEntity, NationalChartAnalysis, PartyRecord, RegionalChartAnalysis } from '~/types/election'

const unalignedId = 'self-nomination'

function partyEntity(entity: ElectionEntity, candidates: CandidateSummary[], parties: PartyRecord[]): ElectionEntity {
  if (entity.type !== 'candidate') return entity
  const party = partyForEntity(parties, candidates, entity)
  if (party) return { id: party.id, name: party.name, type: 'party' }
  const partyId = entity.party_id || candidates.find(item => item.id === entity.id)?.party_id
  const partyName = partyNameForEntity(candidates, entity)
  if (partyId || partyName) return { id: partyId || `national-party-${partyName}`, name: partyName || 'Партия без названия', type: 'party' }
  return { id: unalignedId, name: 'Самовыдвижение', type: 'other' }
}

export function nationalPartyRows(total: AggregateResult, candidates: CandidateSummary[], parties: PartyRecord[]): AggregatedRow[] {
  const grouped = new Map<string, AggregatedRow>()
  for (const row of total.rows) {
    const entity = partyEntity(row, candidates, parties)
    const current = grouped.get(entity.id) || { ...entity, votes: 0 }
    current.votes += row.votes
    grouped.set(entity.id, current)
  }
  return [...grouped.values()]
}

export const partyRows = nationalPartyRows

export function nationalPartyAnalysis(analysis: NationalChartAnalysis, candidates: CandidateSummary[], parties: PartyRecord[]): NationalChartAnalysis {
  if (!analysis.points) return analysis
  const entities: ElectionEntity[] = []
  const indexes = new Map<string, number>()
  const sourceIndexes = analysis.entities.map(entity => {
    const grouped = partyEntity(entity, candidates, parties)
    let index = indexes.get(grouped.id)
    if (index === undefined) {
      index = entities.length
      entities.push(grouped)
      indexes.set(grouped.id, index)
    }
    return index
  })
  return {
    standard: analysis.standard,
    entities,
    points: analysis.points.map(([turnout, valid, results]) => {
      const votes = new Map<number, number>()
      for (let offset = 0; offset < results.length; offset += 2) {
        const target = sourceIndexes[results[offset]!]
        if (target !== undefined) votes.set(target, (votes.get(target) || 0) + results[offset + 1]!)
      }
      return [turnout, valid, [...votes].flatMap(([index, count]) => [index, count])]
    }),
  }
}

export function regionalPartyAnalysis(analysis: RegionalChartAnalysis, entities: ElectionEntity[], candidates: CandidateSummary[], parties: PartyRecord[]): { analysis: RegionalChartAnalysis, entities: ElectionEntity[] } {
  const groupedEntities: ElectionEntity[] = []
  const indexes = new Map<string, number>()
  const sourceIndexes = entities.map(entity => {
    const grouped = partyEntity(entity, candidates, parties)
    let index = indexes.get(grouped.id)
    if (index === undefined) {
      index = groupedEntities.length
      groupedEntities.push(grouped)
      indexes.set(grouped.id, index)
    }
    return index
  })
  return {
    entities: groupedEntities,
    analysis: { ...analysis, points: analysis.points.map(([turnout, valid, results]) => {
      const votes = new Map<number, number>()
      for (let offset = 0; offset < results.length; offset += 2) {
        const target = sourceIndexes[results[offset]!]
        if (target !== undefined) votes.set(target, (votes.get(target) || 0) + results[offset + 1]!)
      }
      return [turnout, valid, [...votes].flatMap(([index, count]) => [index, count])]
    }) },
  }
}

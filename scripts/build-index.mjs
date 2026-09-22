import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const sourceRoot = pathToFileURL(`${resolve(process.argv[2] || 'public/data')}/`)
const root = process.argv[3] ? pathToFileURL(`${resolve(process.argv[3])}/`) : sourceRoot
await mkdir(root, { recursive: true })
const collator = new Intl.Collator('ru', { numeric: true })
const pageSize = 500
const directoryEntries = await readdir(sourceRoot, { withFileTypes: true })
const electionIds = directoryEntries.filter(entry => entry.isDirectory()).map(entry => entry.name).sort()
const elections = []

async function jsonNames(electionId, folderName) {
  try {
    return (await readdir(new URL(`${electionId}/${folderName}/`, sourceRoot))).filter(name => name.endsWith('.json')).sort()
  } catch (error) {
    if (error.code !== 'ENOENT') throw error
    return []
  }
}

async function readResult(electionId, folderName, name) {
  return JSON.parse(await readFile(new URL(`${electionId}/${folderName}/${name}`, sourceRoot), 'utf8'))
}

for (const id of electionIds) {
  const precinctNames = await jsonNames(id, 'precincts')
  if (!precinctNames.length) continue

  const first = await readResult(id, 'precincts', precinctNames[0])
  const grouped = new Map()
  const entities = new Map()
  const rawPoints = []
  const memberships = []
  const precincts = []
  const computed = new Map()
  const treeChildren = new Map()
  const tikPrecincts = new Map()
  const addChild = (parent, child) => {
    if (!parent || !child) return
    const children = treeChildren.get(parent.id) || new Map()
    const current = children.get(child.id) || { id: child.id, name: child.name, number: child.number, kind: child.kind, count: 0 }
    current.count += 1
    children.set(child.id, current)
    treeChildren.set(parent.id, children)
  }
  const addGroup = (unit) => {
    const count = (grouped.get(unit.id)?.count || 0) + 1
    grouped.set(unit.id, { id: unit.id, name: unit.name, number: unit.number, kind: unit.kind, count })
  }

  // Bound open files and process each batch in stable filename order.
  for (let offset = 0; offset < precinctNames.length; offset += 32) {
    const batch = await Promise.all(precinctNames.slice(offset, offset + 32).map(name => readResult(id, 'precincts', name)))
    for (const data of batch) {
      const results = []
      for (const result of data.results) {
        entities.set(result.entity.id, result.entity)
        results.push(result.entity.id, result.votes)
      }
      const path = data.unit.administrative_path || []
      const units = new Map(path.map(unit => [unit.kind, unit]))
      rawPoints.push([
        data.turnout.registered ? data.turnout.issued / data.turnout.registered * 10000 : 0,
        data.turnout.valid,
        results,
      ])
      memberships.push({ region: units.get('region')?.id, units: path.map(unit => unit.id) })
      for (const [pathIndex, unit] of path.entries()) {
        if (['region', 'district', 'territorial_commission'].includes(unit.kind)) addGroup(unit)
        if (!['national', 'region', 'district', 'territorial_commission'].includes(unit.kind)) continue
        const current = computed.get(unit.id) || {
          unit: { ...unit, administrative_path: path.slice(0, pathIndex) },
          turnout: { registered: 0, issued: 0, valid: 0, invalid: 0 }, votes: new Map(),
        }
        current.turnout.registered += data.turnout.registered
        current.turnout.issued += data.turnout.issued
        current.turnout.valid += data.turnout.valid
        current.turnout.invalid += data.turnout.invalid
        for (const result of data.results) {
          current.votes.set(result.entity.id, (current.votes.get(result.entity.id) || 0) + result.votes)
        }
        computed.set(unit.id, current)
      }
      precincts.push({ id: data.unit.id, name: data.unit.name, number: data.unit.number, region: units.get('region')?.name || '—' })
      const firstLevel = units.get('district') || units.get('region')
      const tik = units.get('territorial_commission')
      addChild(units.get('national'), firstLevel)
      addChild(firstLevel, tik)
      if (tik) {
        const list = tikPrecincts.get(tik.id) || []
        list.push({ id: data.unit.id, name: data.unit.name, number: data.unit.number, region: units.get('region')?.name || '—' })
        tikPrecincts.set(tik.id, list)
      }
    }
  }
  const entityList = [...entities.values()]
  const entityIndexes = new Map(entityList.map((entity, index) => [entity.id, index]))
  const points = rawPoints.map(([turnout, valid, results]) => [
    turnout,
    valid,
    results.map((value, index) => index % 2 ? value : entityIndexes.get(value)),
  ])
  const byKind = kind => [...grouped.values()]
    .filter(unit => unit.kind === kind)
    .sort((left, right) => collator.compare(left.name, right.name))
  precincts.sort((left, right) => collator.compare(String(left.number), String(right.number)))

  const analysisRoot = new URL(`${id}/analysis/`, root)
  const precinctPageRoot = new URL(`${id}/precinct-pages/`, root)
  const computedRoot = new URL(`${id}/computed/`, root)
  const treeRoot = new URL(`${id}/tree/`, root)
  await rm(analysisRoot, { recursive: true, force: true })
  await rm(precinctPageRoot, { recursive: true, force: true })
  await rm(computedRoot, { recursive: true, force: true })
  await rm(treeRoot, { recursive: true, force: true })
  await mkdir(analysisRoot, { recursive: true })
  await mkdir(precinctPageRoot, { recursive: true })
  await mkdir(computedRoot, { recursive: true })
  await mkdir(treeRoot, { recursive: true })
  await writeFile(new URL('national.json', analysisRoot), `${JSON.stringify({
    standard: 'vibori-chart-analysis/v3', entities: entityList, points,
  })}\n`)

  const regional = new Map()
  for (const [sourceIndex, membership] of memberships.entries()) {
    if (!membership.region) continue
    const entry = regional.get(membership.region) || { points: [], units: {} }
    const index = entry.points.push(points[sourceIndex]) - 1
    for (const unitId of membership.units) {
      if (!unitId) continue
      ;(entry.units[unitId] ||= []).push(index)
    }
    regional.set(membership.region, entry)
  }
  for (const [regionId, entry] of regional) {
    await writeFile(new URL(`${regionId}.json`, analysisRoot), `${JSON.stringify({
      standard: 'vibori-chart-analysis/v3', points: entry.points, units: entry.units,
    })}\n`)
  }

  for (let page = 0; page * pageSize < precincts.length; page += 1) {
    await writeFile(new URL(`${page}.json`, precinctPageRoot), `${JSON.stringify(precincts.slice(page * pageSize, (page + 1) * pageSize))}\n`)
  }

  const aggregateNames = await jsonNames(id, 'aggregates')
  const officialResults = {}
  const computedResults = {}
  let nationalAggregate
  for (const name of aggregateNames) {
    const data = await readResult(id, 'aggregates', name)
    officialResults[data.unit.id] = `aggregates/${name}`
    if (data.unit.kind === 'national') {
      nationalAggregate = data.unit.id
    }
  }
  for (const [unitId, result] of computed) {
    if (officialResults[unitId]) continue
    const file = `computed/${unitId}.json`
    await writeFile(new URL(`${unitId}.json`, computedRoot), `${JSON.stringify({
      standard: 'vibori-election-result/v1',
      source: { publisher: 'Calculated from precinct protocols' },
      election: first.election, unit: result.unit, ballot: first.ballot,
      turnout: result.turnout,
      results: [...result.votes].map(([entityId, votes]) => ({ entity: entities.get(entityId), votes })),
    })}\n`)
    computedResults[unitId] = file
  }
  const nationalId = nationalAggregate || (first.unit.administrative_path || []).find(unit => unit.kind === 'national')?.id || first.unit.id
  for (const [parentId, children] of treeChildren) {
    const nodes = [...children.values()].sort((left, right) => collator.compare(left.name, right.name))
    await writeFile(new URL(`${parentId}.json`, treeRoot), `${JSON.stringify(nodes)}\n`)
  }
  for (const [tikId, list] of tikPrecincts) {
    list.sort((left, right) => collator.compare(String(left.number), String(right.number)))
    for (let page = 0; page * pageSize < list.length; page += 1) {
      await writeFile(new URL(`${tikId}-${page}.json`, treeRoot), `${JSON.stringify(list.slice(page * pageSize, (page + 1) * pageSize))}\n`)
    }
  }
  const regions = byKind('region')
  const election = {
    id, name: first.election.name, date: first.election.date, country: first.election.country,
    scope: first.election.scope, ballot_title: first.ballot.title, ballot_kind: first.ballot.kind, national_id: nationalId,
    precinct_count: precinctNames.length, region_count: regions.length, entities: entityList,
    tree_root: nationalId,
    official_results: officialResults, computed_results: computedResults,
    precinct_pages: Math.ceil(precincts.length / pageSize),
  }
  await writeFile(new URL(`${id}/index.json`, root), `${JSON.stringify(election)}\n`)
  await rm(new URL(`${id}/analysis.json`, root), { force: true })
  const { entities: ignoredEntities, official_results: ignoredOfficialResults, computed_results: ignoredComputedResults, precinct_pages: ignoredPages, tree_root: ignoredTreeRoot, ...catalogEntry } = election
  elections.push(catalogEntry)
  global.gc?.()
}

const catalog = { standard: 'vibori-catalog/v1', generated_at: new Date().toISOString(), elections }
elections.sort((left, right) => Number(right.scope === 'national') - Number(left.scope === 'national') || right.date.localeCompare(left.date) || collator.compare(left.name, right.name) || left.id.localeCompare(right.id))
await writeFile(new URL('index.json', root), `${JSON.stringify(catalog)}\n`)
await writeFile(new URL('routes.json', root), '["/"]\n')
console.log(`Catalog updated: ${elections.length} elections`)

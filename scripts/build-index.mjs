import { readdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

const root = new URL('../public/data/', import.meta.url)
const dirs = (await readdir(root, { withFileTypes: true })).filter(x => x.isDirectory()).map(x => x.name)
const elections = []; const routes = ['/']
for (const id of dirs) {
  const folder = new URL(`${id}/precincts/`, root)
  let names; try { names = (await readdir(folder)).filter(x => x.endsWith('.json')) } catch { continue }
  const loaded = await Promise.all(names.map(async n => ({ file: `precincts/${n}`, data: JSON.parse(await readFile(new URL(n, folder), 'utf8')) })))
  if (!loaded.length) continue
  const first = loaded[0].data; const grouped = (kind) => {
    const map = new Map()
    loaded.forEach(({data}) => (data.unit.administrative_path || []).filter(x => x.kind === kind).forEach(x => map.set(x.id, {...x, count: (map.get(x.id)?.count || 0) + 1})))
    return [...map.values()].sort((a,b) => a.name.localeCompare(b.name, 'ru'))
  }
  const precincts = loaded.map(({file,data}) => ({ id:data.unit.id, name:data.unit.name, number:data.unit.number, region:(data.unit.administrative_path || []).find(x=>x.kind==='region')?.name || '—', file })).sort((a,b)=>String(a.number).localeCompare(String(b.number), 'ru', {numeric:true}))
  const regions = grouped('region'), tiks = grouped('territorial_commission')
  const national_id = (first.unit.administrative_path || []).find(x => x.kind === 'national')?.id || first.unit.id
  const units = [...regions, ...tiks, ...precincts, {id:national_id}]
  units.forEach(unit => routes.push(`/result/${id}/${encodeURIComponent(unit.id)}`))
  new Set(loaded.flatMap(({data}) => data.results.map(r => r.entity.id))).forEach(entityId => routes.push(`/entity/${encodeURIComponent(entityId)}`))
  elections.push({ id, name:first.election.name, date:first.election.date, country:first.election.country, ballot_title:first.ballot.title, national_id, files:loaded.map(x=>x.file), precinct_count:loaded.length, regions, tiks, region_count:regions.length, precincts })
}
await writeFile(new URL('index.json', root), JSON.stringify({ standard:'vibori-catalog/v1', generated_at:new Date().toISOString(), elections }, null, 2) + '\n')
await writeFile(new URL('routes.json', root), JSON.stringify([...new Set(routes)], null, 2) + '\n')
console.log(`Каталог обновлён: ${elections.length} голосований`)

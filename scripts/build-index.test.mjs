import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

test('indexes all precinct pages, preserves source files and prefers official totals', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'vibori-test-'))
  try {
    const source = join(directory, 'source')
    const output = join(directory, 'output')
    const precincts = join(source, 'sample', 'precincts')
    const aggregates = join(source, 'sample', 'aggregates')
    const candidates = join(source, 'sample', 'candidates')
    await mkdir(precincts, { recursive: true })
    await mkdir(aggregates, { recursive: true })
    await mkdir(candidates, { recursive: true })
    const path = [
      { id: 'country', name: 'Country', kind: 'national' },
      { id: 'region', name: 'Region', kind: 'region' },
      { id: 'tik', name: 'Commission', kind: 'territorial_commission' },
    ]
    const record = {
      standard: 'vibori-election-result/v1',
      source: { url: 'https://example.org/protocol', retrieved_at: '2026-01-01T00:00:00Z' },
      election: { id: 'sample', name: 'Election', date: '2026-01-01', country: 'RU' },
      ballot: { id: 'ballot', title: 'Ballot', kind: 'single_member' },
      turnout: { registered: 100, issued: 51, valid: 50, invalid: 1 },
      results: [{ entity: { id: 'candidate', name: 'Candidate', type: 'candidate' }, votes: 50 }],
    }
    for (let index = 0; index < 501; index++) {
      await writeFile(join(precincts, index + '.json'), JSON.stringify({ ...record, unit: { id: String(index), name: 'Precinct ' + index, number: String(index), kind: 'precinct', administrative_path: path } }))
    }
    const official = JSON.stringify({ ...record, unit: path[0] })
    await writeFile(join(aggregates, 'country.json'), official)
    await writeFile(join(candidates, 'candidate.json'), JSON.stringify({ id: 'candidate', name: 'Candidate', party: { id: 'party', name: 'Party' }, district_number: 1, status: 'registered' }))
    execFileSync(process.execPath, ['scripts/build-index.mjs', source, output])
    const json = async file => JSON.parse(await readFile(join(output, 'sample', file), 'utf8'))
    const catalog = await json('index.json')
    assert.equal(catalog.precinct_count, 501)
    assert.equal(catalog.official_results.country, 'aggregates/country.json')
    assert.equal(catalog.computed_results.country, undefined)
    assert.equal(catalog.candidates_file, 'candidates.json')
    assert.deepEqual(await json('candidates.json'), [{ id: 'candidate', name: 'Candidate', party_id: 'party', party_name: 'Party', district_number: 1, status: 'registered' }])
    assert.equal((await json('tree/tik-0.json')).length, 500)
    assert.equal((await json('tree/tik-1.json')).length, 1)
    const computed = await json('computed/tik.json')
    assert.equal(computed.turnout.valid, 25050)
    assert.equal(computed.results[0].votes, 25050)
    assert.deepEqual(computed.unit.administrative_path, path.slice(0, 2))
    const analysis = await json('analysis/national.json')
    assert.equal(analysis.standard, 'vibori-chart-analysis/v3')
    assert.equal(analysis.points.length, 501)
    assert.deepEqual(analysis.points[0], [5100, 50, [0, 50]])
    assert.equal(analysis.clusters, undefined)
    assert.equal((await json('analysis/region.json')).units.tik.length, 501)
    assert.equal(await readFile(join(aggregates, 'country.json'), 'utf8'), official)
    await assert.rejects(readFile(join(source, 'index.json')), { code: 'ENOENT' })
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

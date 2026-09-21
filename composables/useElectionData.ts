export type ResultFile = any

export async function catalog() {
  return await $fetch<any>('/data/index.json')
}
export async function resultsFor(electionId: string) {
  const c = await catalog()
  const election = c.elections.find((x: any) => x.id === electionId)
  if (!election) throw new Error('Голосование не найдено')
  return await Promise.all(election.files.map((file: string) => $fetch<ResultFile>(`/data/${electionId}/${file}`)))
}
export function pct(votes: number, valid: number) { return valid ? votes / valid * 100 : 0 }
export function aggregate(files: ResultFile[]) {
  const turnout = { registered: 0, issued: 0, valid: 0, invalid: 0 }
  const entities = new Map<string, any>()
  files.forEach(file => {
    Object.keys(turnout).forEach(k => turnout[k as keyof typeof turnout] += file.turnout[k] || 0)
    file.results.forEach((r: any) => {
      const old = entities.get(r.entity.id) || { ...r.entity, votes: 0 }
      old.votes += r.votes; entities.set(r.entity.id, old)
    })
  })
  return { turnout, rows: [...entities.values()] }
}
export function unitName(files: ResultFile[], id: string) {
  const root = files.find(f => f.unit.id === id)?.unit
  if (root) return root
  return files.flatMap(f => f.unit.administrative_path || []).find((x: any) => x.id === id)
}

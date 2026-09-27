/* eslint-disable @typescript-eslint/no-require-imports */
const { PrismaClient } = require('@prisma/client')
const db = new PrismaClient()

async function main() {
  const decisions = await db.legalDecision.count()
  const withEmb = await db.legalDecision.count({ where: { embedding: { not: null } } })
  const chunks = await db.legalDecisionChunk.count()
  const yargitay = await db.legalDecision.count({ where: { court: { contains: 'Yargıtay' } } })
  const importJobs = await db.importJob.count()
  const completedJobs = await db.importJob.count({ where: { status: 'completed' } })

  console.log('═══ BetterSaul DB Stats ═══')
  console.log(`LegalDecision total:    ${decisions}`)
  console.log(`  - with embedding:     ${withEmb}`)
  console.log(`  - Yargıtay:           ${yargitay}`)
  console.log(`LegalDecisionChunk:     ${chunks}`)
  console.log(`ImportJob total:        ${importJobs}`)
  console.log(`  - completed:          ${completedJobs}`)

  // Sample 3 recent decisions
  console.log('\n═══ Sample decisions ═══')
  const recent = await db.legalDecision.findMany({
    take: 3,
    orderBy: { createdAt: 'desc' },
    select: { title: true, court: true, decisionNumber: true, embeddingModel: true, chunkCount: true },
  })
  for (const d of recent) {
    console.log(`  • ${d.title}`)
    console.log(`    ${d.court} | ${d.decisionNumber}`)
    console.log(`    emb: ${d.embeddingModel} | chunks: ${d.chunkCount}`)
  }
}
main().finally(() => db.$disconnect())

/* eslint-disable @typescript-eslint/no-require-imports */
/* Clean up old ImportJob records and stale jobs */
const { PrismaClient } = require('@prisma/client')
const db = new PrismaClient()

async function main() {
  // Delete all ImportJob records (fresh start)
  const deleted = await db.importJob.deleteMany({})
  console.log(`Deleted ${deleted.count} ImportJob records`)
  
  // List current legal decisions count
  const decisions = await db.legalDecision.count()
  console.log(`Current LegalDecision count: ${decisions}`)
  
  // Check how many have embeddings
  const withEmb = await db.legalDecision.count({ where: { embedding: { not: null } } })
  console.log(`With embedding: ${withEmb}`)
  
  // Check LegalDecisionChunk count
  const chunks = await db.legalDecisionChunk.count()
  console.log(`LegalDecisionChunk count: ${chunks}`)
}
main().finally(() => db.$disconnect())

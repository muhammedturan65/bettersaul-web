/**
 * BetterSaul Import Pipeline — Async Job Queue
 * 
 * In-memory job queue (since no Redis in this environment).
 * Production: replace with BullMQ + Redis.
 * 
 * Pipeline: Import → Queue → Parse → Chunk → Embed → Vector DB → Index
 */

import { db } from '@/lib/db'
import { embed, chunkText } from '@/lib/legal-engine/embeddings'

export interface ImportJob {
  id: string
  sourceName: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'paused'
  totalItems: number
  processedItems: number
  failedItems: number
  startedAt: Date | null
  completedAt: Date | null
  errorMessage?: string
  progress: number // 0-100
  currentStep?: string
  log: Array<{ ts: Date; level: 'info' | 'warn' | 'error'; msg: string }>
}

// In-memory job store (production: Redis/BullMQ)
const jobs = new Map<string, ImportJob>()
const jobHandlers = new Map<string, NodeJS.Timeout>()

export function getJob(jobId: string): ImportJob | undefined {
  return jobs.get(jobId)
}

export function listJobs(): ImportJob[] {
  return Array.from(jobs.values()).sort((a, b) => {
    const aTime = a.startedAt?.getTime() || 0
    const bTime = b.startedAt?.getTime() || 0
    return bTime - aTime
  })
}

export function createJob(sourceName: string, totalItems: number): ImportJob {
  const id = `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const job: ImportJob = {
    id,
    sourceName,
    status: 'queued',
    totalItems,
    processedItems: 0,
    failedItems: 0,
    startedAt: null,
    completedAt: null,
    progress: 0,
    log: [{ ts: new Date(), level: 'info', msg: `Job created: ${sourceName} (${totalItems} items)` }],
  }
  jobs.set(id, job)
  return job
}

export function startJob(jobId: string) {
  const job = jobs.get(jobId)
  if (!job) return

  job.status = 'running'
  job.startedAt = new Date()
  job.log.push({ ts: new Date(), level: 'info', msg: 'Job started' })

  // Simulate async processing (production: real source scraping + parsing + embedding)
  let processed = 0
  const batchSize = Math.max(1, Math.floor(job.totalItems / 100))

  const interval = setInterval(async () => {
    const currentJob = jobs.get(jobId)
    if (!currentJob || currentJob.status !== 'running') {
      clearInterval(interval)
      return
    }

    try {
      // Process a batch
      const batchEnd = Math.min(processed + batchSize, currentJob.totalItems)
      currentJob.currentStep = `Parse + chunk + embed: ${processed}-${batchEnd} / ${currentJob.totalItems}`

      // For each item in batch, simulate:
      // 1. Parse document (mock)
      // 2. Chunk text
      // 3. Generate embedding
      // 4. Store in DB
      // In production, this would actually pull from the source

      // Update progress
      processed = batchEnd
      currentJob.processedItems = processed
      currentJob.progress = Math.round((processed / currentJob.totalItems) * 100)

      // Periodically log
      if (processed % (batchSize * 5) === 0 || processed === currentJob.totalItems) {
        currentJob.log.push({
          ts: new Date(),
          level: 'info',
          msg: `Processed ${processed}/${currentJob.totalItems} (${currentJob.progress}%)`,
        })
      }

      // Persist to DB ImportJob table (occasionally)
      if (processed % (batchSize * 10) === 0 || processed === currentJob.totalItems) {
        await db.importJob.upsert({
          where: { id: jobId },
          update: {
            status: currentJob.status,
            processedItems: currentJob.processedItems,
            failedItems: currentJob.failedItems,
          },
          create: {
            id: jobId,
            sourceName: currentJob.sourceName,
            status: currentJob.status,
            totalItems: currentJob.totalItems,
            processedItems: currentJob.processedItems,
            failedItems: currentJob.failedItems,
            startedAt: currentJob.startedAt,
          },
        })
      }

      if (processed >= currentJob.totalItems) {
        currentJob.status = 'completed'
        currentJob.completedAt = new Date()
        currentJob.progress = 100
        currentJob.log.push({ ts: new Date(), level: 'info', msg: `Job completed: ${currentJob.processedItems} items processed` })
        clearInterval(interval)
        jobHandlers.delete(jobId)

        await db.importJob.upsert({
          where: { id: jobId },
          update: {
            status: 'completed',
            processedItems: currentJob.processedItems,
            completedAt: currentJob.completedAt,
          },
          create: {
            id: jobId,
            sourceName: currentJob.sourceName,
            status: 'completed',
            totalItems: currentJob.totalItems,
            processedItems: currentJob.processedItems,
            startedAt: currentJob.startedAt,
            completedAt: currentJob.completedAt,
          },
        })
      }
    } catch (e: any) {
      currentJob.failedItems += batchSize
      currentJob.log.push({ ts: new Date(), level: 'error', msg: `Batch error: ${e.message}` })
    }
  }, 400) // 400ms between batches

  jobHandlers.set(jobId, interval)
}

export function pauseJob(jobId: string): boolean {
  const job = jobs.get(jobId)
  if (!job || job.status !== 'running') return false
  job.status = 'paused'
  job.log.push({ ts: new Date(), level: 'warn', msg: 'Job paused' })
  const handler = jobHandlers.get(jobId)
  if (handler) {
    clearInterval(handler)
    jobHandlers.delete(jobId)
  }
  return true
}

export function resumeJob(jobId: string): boolean {
  const job = jobs.get(jobId)
  if (!job || job.status !== 'paused') return false
  startJob(jobId)
  return true
}

export function cancelJob(jobId: string): boolean {
  const job = jobs.get(jobId)
  if (!job) return false
  job.status = 'failed'
  job.errorMessage = 'Cancelled by user'
  job.completedAt = new Date()
  job.log.push({ ts: new Date(), level: 'warn', msg: 'Job cancelled' })
  const handler = jobHandlers.get(jobId)
  if (handler) {
    clearInterval(handler)
    jobHandlers.delete(jobId)
  }
  return true
}

// Compute embeddings for existing decisions (used by /api/embeddings/reindex)
export async function reindexEmbeddings(): Promise<{ updated: number; total: number }> {
  const decisions = await db.legalDecision.findMany()
  let updated = 0
  for (const d of decisions) {
    if (d.embedding) continue // Skip if already has embedding
    const text = `${d.title || ''} ${d.summary || ''} ${d.fullText || ''}`
    const embedding = embed(text)
    const chunks = chunkText(d.fullText || '', 800, 200)
    await db.legalDecision.update({
      where: { id: d.id },
      data: {
        embedding: JSON.stringify(embedding),
        embeddingModel: 'tfidf-hash-256-tr-v1',
        chunkCount: chunks.length,
      },
    })
    // Create chunks with embeddings
    for (let i = 0; i < chunks.length; i++) {
      await db.legalDecisionChunk.upsert({
        where: {
          decisionId_chunkIndex: { decisionId: d.id, chunkIndex: i },
        },
        update: {
          chunkText: chunks[i],
          embedding: JSON.stringify(embed(chunks[i])),
        },
        create: {
          decisionId: d.id,
          chunkIndex: i,
          chunkText: chunks[i],
          embedding: JSON.stringify(embed(chunks[i])),
        },
      })
    }
    updated++
  }
  return { updated, total: decisions.length }
}

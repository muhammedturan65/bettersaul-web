/* eslint-disable @typescript-eslint/no-require-imports */
/* Quick script to update demo user role to admin */
const { PrismaClient } = require('@prisma/client')
const db = new PrismaClient()

async function main() {
  const user = await db.user.update({
    where: { email: 'demo@bettersaul.legal' },
    data: { role: 'admin' },
  })
  console.log(`Updated: ${user.email} → role: ${user.role}`)
}
main().finally(() => db.$disconnect())

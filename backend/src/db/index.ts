// backend/src/db/index.ts
import { PrismaClient } from '@prisma/client';


export const prisma = new PrismaClient();

// Simple health check for the database
export async function testDatabaseConnection() {
    try {
        await prisma.user.findMany({ take: 1 });
        console.log('[DB] ✅ Database connection established');
    } catch (error) {
        console.error('[DB] ❌ Failed to connect to database:', error);
    }
}

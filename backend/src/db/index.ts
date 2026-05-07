// backend/src/db/index.ts
import { PrismaClient } from '@prisma/client';

// Initialize Prisma Client globally
export const prisma = new PrismaClient();

// Simple health check for the database
export async function testDatabaseConnection() {
    try {
        // Test connection by selecting all users
        await prisma.user.findMany({ take: 1 });
        console.log('[DB] ✅ Database connection established');
    } catch (error) {
        console.error('[DB] ❌ Failed to connect to database:', error);
    }
}

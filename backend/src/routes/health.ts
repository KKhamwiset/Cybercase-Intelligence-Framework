import { Elysia } from "elysia";
import { prisma } from "../db";

export const healthRoutes = new Elysia({ prefix: "/health" })
  .get("/", async () => {
    let dbStatus = "disconnected";
    try {
      // Execute a simple query to test connection
      await prisma.$queryRaw`SELECT 1`;
      dbStatus = "connected";
    } catch (error) {
      console.error("Database connection error:", error);
      dbStatus = "error";
    }

    return {
      status: "ok",
      database: dbStatus,
      version: "0.1.0",
    };
  });

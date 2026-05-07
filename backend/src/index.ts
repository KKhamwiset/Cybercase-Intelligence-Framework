import { Elysia } from "elysia";
import { cors } from "@elysiajs/cors";
import { config, getCorsOrigins } from "./config";
import { healthRoutes } from "./routes/health";
import { userRoutes } from "./routes/user";

const app = new Elysia()
  .use(
    cors({
      origin: getCorsOrigins(),
      credentials: true,
      allowedHeaders: ["*"],
      methods: ["*"],
    })
  )
  .group("/api/v1", (app) => app.use(healthRoutes).use(userRoutes))
  .listen(config.port);

console.log(
  `[STARTUP] 🦊 Elysia is running at ${app.server?.hostname}:${app.server?.port}`
);

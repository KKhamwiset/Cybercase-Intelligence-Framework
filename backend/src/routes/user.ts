import { Elysia, t } from "elysia";
import { prisma } from "../db";

export const userRoutes = new Elysia({ prefix: "/users" })
  .get("/", async () => {
    return await prisma.user.findMany();
  })
  .post(
    "/",
    async ({ body }) => {
      const user = await prisma.user.create({
        data: {
          email: body.email,
          display_name: body.display_name,
        },
      });
      return user;
    },
    {
      body: t.Object({
        email: t.String({ format: "email" }),
        display_name: t.Optional(t.String()),
      }),
    }
  );

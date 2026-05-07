export const config = {
  database_url: process.env.DATABASE_URL || "postgresql://postgres:postgres@localhost:5432/tsr_mitre",
  cors_origins: process.env.CORS_ORIGINS || "http://localhost:3000",
  debug: process.env.DEBUG === "true",
  anthropic_api_key: process.env.ANTHROPIC_API_KEY || "",
  port: parseInt(process.env.PORT || "8000", 10),
};

export const getCorsOrigins = () => {
  return config.cors_origins.split(",").map((o) => o.trim());
};

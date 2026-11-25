import { PrismaClient } from "@prisma/client";
import { createApiServer } from "./api-server.js";
import { required } from "./config.js";

const token = required("GRAPHQL_SERVICE_TOKEN");
const rawPort = process.env.PORT;
const port = rawPort ? Number(rawPort) : 4000;
if (!Number.isInteger(port) || port < 0 || port > 65535) {
  throw new Error(`Invalid PORT: ${rawPort}`);
}

const prisma = new PrismaClient();
const api = await createApiServer({ token, orders: prisma.order });

await new Promise<void>((resolve, reject) => {
  api.httpServer.once("error", reject);
  api.httpServer.listen(port, () => {
    api.httpServer.off("error", reject);
    resolve();
  });
});

console.info(`Apollo listening on port ${port}`);

let closing = false;
const shutdown = async () => {
  if (closing) return;
  closing = true;
  try {
    await api.close();
  } finally {
    await prisma.$disconnect();
  }
};

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => {
    void shutdown().catch((error) => {
      console.error("Failed to shut down API server cleanly", error);
      process.exitCode = 1;
    });
  });
}

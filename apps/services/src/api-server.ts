import { timingSafeEqual } from "node:crypto";
import {
  createServer,
  type IncomingMessage,
  type RequestListener,
  type Server,
  type ServerResponse,
} from "node:http";
import { ApolloServer, HeaderMap, type HTTPGraphQLRequest } from "@apollo/server";
import { ApolloServerPluginDrainHttpServer } from "@apollo/server/plugin/drainHttpServer";
import type { PrismaClient } from "@prisma/client";
import { createOrderStatusLookup } from "./order-status.js";

export const DEFAULT_MAX_BODY_BYTES = 64 * 1024;

export type OrderLookupStore = Pick<PrismaClient["order"], "findFirst">;

export interface ApiServerOptions {
  token: string;
  orders: OrderLookupStore;
  maxBodyBytes?: number;
}

export interface ApiServerHandle {
  httpServer: Server;
  apolloServer: ApolloServer;
  close: () => Promise<void>;
}

const typeDefs = `#graphql
  type OrderStatus {
    stage: Int!
    status: String!
    finished: Boolean!
    reason: String!
  }
  type Query {
    orderStatus(id: ID!, owner: String!, customerId: ID): OrderStatus
  }
`;

class HttpError extends Error {
  constructor(
    readonly statusCode: number,
    message: string,
    readonly headers?: Record<string, string>,
  ) {
    super(message);
  }
}

function sendJson(
  res: ServerResponse,
  statusCode: number,
  payload: unknown,
  headers?: Record<string, string>,
): void {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (headers) {
    for (const [key, value] of Object.entries(headers)) {
      res.setHeader(key, value);
    }
  }
  res.end(JSON.stringify(payload));
}

function isJsonMediaType(contentType: string | undefined): boolean {
  if (!contentType) return false;
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json" || /^application\/[a-z0-9.+-]+\+json$/.test(mediaType);
}

async function readJsonObjectBody(req: IncomingMessage, maxBodyBytes: number): Promise<Record<string, unknown>> {
  const rawContentLength = req.headers["content-length"];
  if (rawContentLength !== undefined) {
    const trimmed = rawContentLength.trim();
    if (!/^\d+$/.test(trimmed)) {
      throw new HttpError(400, "Invalid Content-Length header");
    }
    const contentLength = Number(trimmed);
    if (!Number.isSafeInteger(contentLength) || contentLength > maxBodyBytes) {
      throw new HttpError(413, "Payload Too Large", { Connection: "close" });
    }
  }

  const chunks: Buffer[] = [];
  let totalBytes = 0;

  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    totalBytes += buffer.length;
    if (totalBytes > maxBodyBytes) {
      throw new HttpError(413, "Payload Too Large", { Connection: "close" });
    }
    chunks.push(buffer);
  }

  const rawText = Buffer.concat(chunks).toString("utf8");
  if (!rawText.trim()) {
    throw new HttpError(400, "Invalid JSON body");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch {
    throw new HttpError(400, "Invalid JSON body");
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new HttpError(400, "Request body must be a JSON object");
  }

  return parsed as Record<string, unknown>;
}

function toHeaderMap(rawHeaders: IncomingMessage["headers"]): HeaderMap {
  const headers = new HeaderMap();
  for (const [key, value] of Object.entries(rawHeaders)) {
    if (value !== undefined) {
      headers.set(key, Array.isArray(value) ? value.join(", ") : value);
    }
  }
  return headers;
}

export async function createApiServer(options: ApiServerOptions): Promise<ApiServerHandle> {
  if (!options.token) {
    throw new Error("Missing GRAPHQL_SERVICE_TOKEN");
  }
  const maxBodyBytes = options.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES;
  if (!Number.isFinite(maxBodyBytes) || maxBodyBytes <= 0) {
    throw new RangeError("maxBodyBytes must be a positive number");
  }

  const expectedAuthorization = Buffer.from(`Bearer ${options.token}`);

  let requestHandler: RequestListener = (_req, res) => {
    res.statusCode = 503;
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.end("Starting\n");
  };

  const httpServer = createServer((req, res) => {
    requestHandler(req, res);
  });

  const apolloServer = new ApolloServer({
    typeDefs,
    introspection: false,
    includeStacktraceInErrorResponses: false,
    stopOnTerminationSignals: false,
    plugins: [ApolloServerPluginDrainHttpServer({ httpServer })],
    resolvers: {
      Query: { orderStatus: createOrderStatusLookup(options.orders) },
    },
  });

  await apolloServer.start();

  const handleRequest = async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    const rawUrl = req.url ?? "/";
    const queryIndex = rawUrl.indexOf("?");
    const pathname = queryIndex === -1 ? rawUrl : rawUrl.slice(0, queryIndex);
    const search = queryIndex === -1 ? "" : rawUrl.slice(queryIndex);
    const method = (req.method ?? "GET").toUpperCase();

    if (pathname === "/healthz") {
      if (method !== "GET" && method !== "HEAD") {
        sendJson(res, 405, { errors: [{ message: "Method Not Allowed" }] }, { Allow: "GET, HEAD" });
        return;
      }
      res.statusCode = 200;
      res.setHeader("Content-Type", "text/plain; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(method === "HEAD" ? undefined : "ok\n");
      return;
    }

    if (pathname !== "/graphql" && pathname !== "/") {
      sendJson(res, 404, { errors: [{ message: "Not Found" }] });
      return;
    }

    const received = Buffer.from(req.headers.authorization ?? "");
    if (received.length !== expectedAuthorization.length || !timingSafeEqual(received, expectedAuthorization)) {
      sendJson(
        res,
        401,
        { errors: [{ message: "Unauthorized", extensions: { code: "UNAUTHENTICATED" } }] },
        { "WWW-Authenticate": "Bearer" },
      );
      return;
    }

    if (method !== "POST" && method !== "GET") {
      sendJson(res, 405, { errors: [{ message: "Method Not Allowed" }] }, { Allow: "GET, POST" });
      return;
    }

    let body: unknown;
    if (method === "POST") {
      if (!isJsonMediaType(req.headers["content-type"])) {
        sendJson(res, 415, { errors: [{ message: "Unsupported Media Type" }] });
        return;
      }
      try {
        body = await readJsonObjectBody(req, maxBodyBytes);
      } catch (error) {
        if (error instanceof HttpError) {
          sendJson(res, error.statusCode, { errors: [{ message: error.message }] }, error.headers);
          return;
        }
        throw error;
      }
    }

    const httpGraphQLRequest: HTTPGraphQLRequest = {
      method,
      headers: toHeaderMap(req.headers),
      search,
      body,
    };

    const response = await apolloServer.executeHTTPGraphQLRequest({
      httpGraphQLRequest,
      context: async () => ({}),
    });

    for (const [key, value] of response.headers) {
      res.setHeader(key, value);
    }
    res.statusCode = response.status ?? 200;

    if (response.body.kind === "complete") {
      res.end(response.body.string);
      return;
    }

    for await (const chunk of response.body.asyncIterator) {
      res.write(chunk);
    }
    res.end();
  };

  requestHandler = (req, res) => {
    void handleRequest(req, res).catch((error) => {
      if (!res.headersSent) {
        sendJson(res, 500, { errors: [{ message: "Internal Server Error" }] });
      } else {
        res.destroy(error instanceof Error ? error : undefined);
      }
    });
  };

  let closePromise: Promise<void> | null = null;

  return {
    httpServer,
    apolloServer,
    close: () => {
      closePromise ??= apolloServer.stop();
      return closePromise;
    },
  };
}

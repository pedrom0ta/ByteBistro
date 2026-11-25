import assert from "node:assert/strict";
import { Readable } from "node:stream";
import { test } from "node:test";
import { createApiServer } from "../dist/api-server.js";

const TOKEN = "test-service-token-1234";
const ORDER_ID = "024cc3e4-cf83-4f9c-a30c-43b732673179";
const OWNER = "dcf0fcb6cc1a4a03bda5b717d09be2ea";

const ORDER_STATUS_QUERY = `
  query OrderStatus($id: ID!, $owner: String!, $customerId: ID) {
    orderStatus(id: $id, owner: $owner, customerId: $customerId) {
      stage
      status
      finished
      reason
    }
  }
`;

async function startTestServer(t, options = {}) {
  const orders = options.orders ?? {
    findFirst: async () => ({ stage: 1, mode: "delivery", reason: "" }),
  };
  const api = await createApiServer({
    token: TOKEN,
    orders,
    maxBodyBytes: options.maxBodyBytes,
  });
  await new Promise((resolve, reject) => {
    api.httpServer.once("error", reject);
    api.httpServer.listen(0, "127.0.0.1", () => {
      api.httpServer.off("error", reject);
      resolve();
    });
  });
  t.after(() => api.close());
  const address = api.httpServer.address();
  assert.ok(address && typeof address === "object");
  return `http://127.0.0.1:${address.port}`;
}

test("createApiServer rejects an empty token", async () => {
  await assert.rejects(
    createApiServer({ token: "", orders: { findFirst: async () => null } }),
    { message: "Missing GRAPHQL_SERVICE_TOKEN" },
  );
});

test("GET /healthz and GET /healthz?probe=1 return 200 without authentication", async (t) => {
  const baseUrl = await startTestServer(t);

  for (const path of ["/healthz", "/healthz?probe=1"]) {
    const response = await fetch(`${baseUrl}${path}`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("content-type"), "text/plain; charset=utf-8");
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(await response.text(), "ok\n");
  }
});

test("HEAD /healthz returns 200 with empty body without authentication", async (t) => {
  const baseUrl = await startTestServer(t);

  const response = await fetch(`${baseUrl}/healthz`, { method: "HEAD" });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "text/plain; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(await response.text(), "");
});

test("POST /healthz returns 405 and /healthz/ or unknown paths return 404", async (t) => {
  const baseUrl = await startTestServer(t);

  const postHealth = await fetch(`${baseUrl}/healthz`, { method: "POST" });
  assert.equal(postHealth.status, 405);
  assert.equal(postHealth.headers.get("allow"), "GET, HEAD");

  for (const path of ["/healthz/", "/unknown", "//healthz"]) {
    const notFound = await fetch(`${baseUrl}${path}`);
    assert.equal(notFound.status, 404);
    assert.deepEqual(await notFound.json(), { errors: [{ message: "Not Found" }] });
  }
});

test("POST /graphql and POST / reject missing, short, and wrong-same-length tokens with 401", async (t) => {
  const baseUrl = await startTestServer(t, {
    orders: { findFirst: async () => assert.fail("DB must not be queried on unauthorized requests") },
  });
  const wrongSameLength = `Bearer ${"x".repeat(TOKEN.length)}`;

  for (const path of ["/graphql", "/"]) {
    for (const authHeader of [undefined, "Bearer short", wrongSameLength]) {
      const headers = { "Content-Type": "application/json" };
      if (authHeader !== undefined) {
        headers.Authorization = authHeader;
      }
      const response = await fetch(`${baseUrl}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query: ORDER_STATUS_QUERY, variables: { id: ORDER_ID, owner: OWNER } }),
      });
      assert.equal(response.status, 401);
      assert.equal(response.headers.get("www-authenticate"), "Bearer");
      const payload = await response.json();
      assert.equal(payload.errors[0].extensions.code, "UNAUTHENTICATED");
    }
  }
});

test("POST /graphql and POST / execute OrderStatus query with valid token", async (t) => {
  const seenQueries = [];
  const baseUrl = await startTestServer(t, {
    orders: {
      findFirst: async (query) => {
        seenQueries.push(query);
        return { stage: 2, mode: "delivery", reason: "" };
      },
    },
  });

  for (const path of ["/graphql", "/"]) {
    const response = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${TOKEN}`,
      },
      body: JSON.stringify({
        query: ORDER_STATUS_QUERY,
        variables: { id: ORDER_ID, owner: OWNER, customerId: null },
      }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      data: {
        orderStatus: {
          stage: 2,
          status: "Pronto para entrega",
          finished: false,
          reason: "",
        },
      },
    });
  }
  assert.equal(seenQueries.length, 2);
});

test("POST /graphql rejects invalid JSON, empty body, and non-object JSON with 400", async (t) => {
  const baseUrl = await startTestServer(t);

  for (const body of ["{bad", "", "   ", "[]", "123", "null"]) {
    const response = await fetch(`${baseUrl}/graphql`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${TOKEN}`,
      },
      body,
    });
    assert.equal(response.status, 400);
    const payload = await response.json();
    assert.ok(Array.isArray(payload.errors) && payload.errors.length === 1);
  }
});

test("POST /graphql rejects non-JSON Content-Type with 415 and unsupported method with 405", async (t) => {
  const baseUrl = await startTestServer(t);

  const response = await fetch(`${baseUrl}/graphql`, {
    method: "POST",
    headers: {
      "Content-Type": "text/plain",
      Authorization: `Bearer ${TOKEN}`,
    },
    body: JSON.stringify({ query: "{ __typename }" }),
  });
  assert.equal(response.status, 415);
  assert.deepEqual(await response.json(), { errors: [{ message: "Unsupported Media Type" }] });

  const putResponse = await fetch(`${baseUrl}/graphql`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN}`,
    },
    body: "{}",
  });
  assert.equal(putResponse.status, 405);
  assert.equal(putResponse.headers.get("allow"), "GET, POST");
});

test("POST /graphql rejects oversized payload with 413", async (t) => {
  const baseUrl = await startTestServer(t, { maxBodyBytes: 128 });
  const oversized = JSON.stringify({ query: ORDER_STATUS_QUERY, pad: "a".repeat(256) });

  const contentLengthResponse = await fetch(`${baseUrl}/graphql`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN}`,
    },
    body: oversized,
  });
  assert.equal(contentLengthResponse.status, 413);
  assert.deepEqual(await contentLengthResponse.json(), { errors: [{ message: "Payload Too Large" }] });

  const streamedResponse = await fetch(`${baseUrl}/graphql`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN}`,
    },
    duplex: "half",
    body: Readable.toWeb(Readable.from([oversized.slice(0, 64), oversized.slice(64)])),
  });
  assert.equal(streamedResponse.status, 413);
  assert.deepEqual(await streamedResponse.json(), { errors: [{ message: "Payload Too Large" }] });
});

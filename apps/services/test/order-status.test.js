import assert from "node:assert/strict";
import { test } from "node:test";
import { createOrderStatusLookup } from "../dist/order-status.js";

const id = "024cc3e4-cf83-4f9c-a30c-43b732673179";
const owner = "dcf0fcb6cc1a4a03bda5b717d09be2ea";

test("scopes the lookup to the order ID and to the session or customer", async () => {
  const lookup = createOrderStatusLookup({
    async findFirst(query) {
      assert.deepEqual(query, {
        where: { id, OR: [{ owner }, { customerId: 9223372036854775807n }] },
        select: { stage: true, mode: true, reason: true },
      });
      return null;
    },
  });

  assert.equal(await lookup(null, { id, owner, customerId: "9223372036854775807" }), null);
});

test("uses only the session for missing or invalid customer IDs", async () => {
  const lookup = createOrderStatusLookup({
    async findFirst(query) {
      assert.deepEqual(query.where, { id, OR: [{ owner }] });
      return null;
    },
  });

  for (const customerId of [null, "0", "1.2", "9223372036854775808"]) {
    assert.equal(await lookup(null, { id, owner, customerId }), null);
  }
});

test("skips the database for an invalid order or session identity", async () => {
  const lookup = createOrderStatusLookup({ findFirst: () => assert.fail("unexpected lookup") });

  assert.equal(await lookup(null, { id: "bad-id", owner }), null);
  assert.equal(await lookup(null, { id, owner: "bad-owner" }), null);
});

test("matches the Django status contract for table and delivery orders", async () => {
  const cases = [
    { mode: "restaurante", stage: 0, progress: 0, status: "Pedido recebido", finished: false, reason: "" },
    { mode: "restaurante", stage: 2, progress: 2, status: "Pronto", finished: true, reason: "" },
    { mode: "delivery", stage: 2, progress: 2, status: "Pronto para entrega", finished: false, reason: "" },
    { mode: "delivery", stage: 3, progress: 3, status: "Saiu para entrega", finished: false, reason: "" },
    { mode: "delivery", stage: 4, progress: 4, status: "Entregue", finished: true, reason: "" },
    { mode: "restaurante", stage: 90, progress: 0, status: "Recusado", finished: false, reason: "Loja fechada" },
    { mode: "delivery", stage: 91, progress: 0, status: "Cancelado", finished: false, reason: "Pedido duplicado" },
  ];

  for (const expected of cases) {
    const { mode, stage, progress, status, finished, reason } = expected;
    const lookup = createOrderStatusLookup({ findFirst: async () => ({ mode, stage, reason }) });
    assert.deepEqual(await lookup(null, { id, owner }), { stage: progress, status, finished, reason });
  }
});

test("reports an unavailable status for an unsupported stored stage", async () => {
  const lookup = createOrderStatusLookup({
    findFirst: async () => ({ mode: "delivery", stage: 5, reason: "" }),
  });

  await assert.rejects(lookup(null, { id, owner }), { message: "Order status is unavailable" });
});

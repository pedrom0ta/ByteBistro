import assert from "node:assert/strict";
import { test } from "node:test";
import { PublishCommand } from "@aws-sdk/client-sns";
import { DeleteMessageCommand, ReceiveMessageCommand } from "@aws-sdk/client-sqs";
import {
  buildOrderCreatedNotification,
  consumeOnce,
  formatOrderNumber,
  processNotification,
} from "../dist/worker-notifications.js";

const OUTBOX_ID = "7f1c3a10-2b30-4c9a-91d2-1234567890ab";
const ORDER_ID = "024cc3e4-cf83-4f9c-a30c-43b732673179";
const TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:bytebistro-notifications";
const QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/bytebistro-orders";

test("formatOrderNumber matches Django Order.number", () => {
  assert.equal(formatOrderNumber(ORDER_ID), "024CC3E4");
});

test("buildOrderCreatedNotification returns pure-ASCII Subject <= 100 chars and PII-free JSON payload", () => {
  const created = new Date("2026-11-24T19:00:00.000Z");
  const { subject, message } = buildOrderCreatedNotification(OUTBOX_ID, ORDER_ID, {
    mode: "delivery",
    total: 6780,
    payment: "Pix",
    created,
  });

  assert.ok(subject.length <= 100);
  assert.match(subject, /^[\x20-\x7E]+$/);
  assert.equal(subject, "ByteBistro - Novo pedido #024CC3E4");

  const parsed = JSON.parse(message);
  assert.deepEqual(parsed, {
    id: OUTBOX_ID,
    type: "order.created",
    orderId: ORDER_ID,
    orderNumber: "024CC3E4",
    mode: "delivery",
    totalCents: 6780,
    payment: "Pix",
    createdAt: "2026-11-24T19:00:00.000Z",
  });
});

test("processNotification & consumeOnce enrich SNS message, commit OrderEvent, and delete SQS message", async () => {
  const fixedNow = new Date("2026-11-24T19:30:00.000Z");
  const snsCommands = [];
  const sqsCommands = [];
  const txOutboxUpdates = [];
  const txOrderEvents = [];

  const prisma = {
    outbox: {
      async findUnique(args) {
        assert.deepEqual(args, {
          where: { id: OUTBOX_ID },
          select: { orderId: true, notifiedAt: true },
        });
        return { orderId: ORDER_ID, notifiedAt: null };
      },
      async updateMany(args) {
        assert.equal(args.where.id, OUTBOX_ID);
        assert.equal(args.where.notifiedAt, null);
        assert.equal(args.data.notifyLeaseToken, "lease-token-1");
        return { count: 1 };
      },
    },
    order: {
      async findUnique(args) {
        assert.deepEqual(args, {
          where: { id: ORDER_ID },
          select: { mode: true, total: true, payment: true, created: true },
        });
        return {
          mode: "delivery",
          total: 6780,
          payment: "Pix",
          created: new Date("2026-11-24T19:29:00.000Z"),
        };
      },
    },
    async $transaction(fn) {
      return fn({
        outbox: {
          async updateMany(args) {
            txOutboxUpdates.push(args);
            return { count: 1 };
          },
        },
        orderEvent: {
          async createMany(args) {
            txOrderEvents.push(args);
            return { count: args.data.length };
          },
        },
      });
    },
  };

  const sns = {
    async send(command) {
      snsCommands.push(command);
      return {};
    },
  };

  const sqs = {
    async send(command) {
      sqsCommands.push(command);
      if (command instanceof ReceiveMessageCommand) {
        return {
          Messages: [{ Body: OUTBOX_ID, ReceiptHandle: "receipt-1" }],
        };
      }
      return {};
    },
  };

  await consumeOnce({
    prisma,
    sns,
    sqs,
    queueUrl: QUEUE_URL,
    topicArn: TOPIC_ARN,
    now: () => fixedNow,
    generateToken: () => "lease-token-1",
  });

  assert.equal(snsCommands.length, 1);
  assert.ok(snsCommands[0] instanceof PublishCommand);
  assert.equal(snsCommands[0].input.TopicArn, TOPIC_ARN);
  assert.match(snsCommands[0].input.Subject, /^[\x20-\x7E]{1,100}$/);
  assert.deepEqual(JSON.parse(snsCommands[0].input.Message), {
    id: OUTBOX_ID,
    type: "order.created",
    orderId: ORDER_ID,
    orderNumber: "024CC3E4",
    mode: "delivery",
    totalCents: 6780,
    payment: "Pix",
    createdAt: "2026-11-24T19:29:00.000Z",
  });

  assert.equal(txOutboxUpdates.length, 1);
  assert.deepEqual(txOutboxUpdates[0], {
    where: { id: OUTBOX_ID, notifyLeaseToken: "lease-token-1", notifiedAt: null },
    data: { notifiedAt: fixedNow, notifyLeaseToken: null, notifyLeaseUntil: null },
  });

  assert.equal(txOrderEvents.length, 1);
  assert.deepEqual(txOrderEvents[0], {
    data: [
      {
        orderId: ORDER_ID,
        action: "notified",
        actorId: null,
        reason: "",
        created: fixedNow,
      },
    ],
  });

  assert.equal(sqsCommands.length, 2);
  assert.ok(sqsCommands[1] instanceof DeleteMessageCommand);
  assert.deepEqual(sqsCommands[1].input, {
    QueueUrl: QUEUE_URL,
    ReceiptHandle: "receipt-1",
  });
});

test("lost-lease race skips orderEvent.createMany, returns false, and does not delete SQS message", async () => {
  const sqsCommands = [];
  let createManyCalled = false;

  const prisma = {
    outbox: {
      async findUnique() {
        return { orderId: ORDER_ID, notifiedAt: null };
      },
      async updateMany() {
        return { count: 1 };
      },
    },
    order: {
      async findUnique() {
        return {
          mode: "restaurante",
          total: 4200,
          payment: "No restaurante",
          created: new Date("2026-11-24T19:29:00.000Z"),
        };
      },
    },
    async $transaction(fn) {
      return fn({
        outbox: {
          async updateMany() {
            return { count: 0 };
          },
        },
        orderEvent: {
          async createMany() {
            createManyCalled = true;
            return { count: 1 };
          },
        },
      });
    },
  };

  await consumeOnce({
    prisma,
    sns: { async send() { return {}; } },
    sqs: {
      async send(command) {
        sqsCommands.push(command);
        if (command instanceof ReceiveMessageCommand) {
          return { Messages: [{ Body: OUTBOX_ID, ReceiptHandle: "receipt-race" }] };
        }
        return {};
      },
    },
    queueUrl: QUEUE_URL,
    topicArn: TOPIC_ARN,
  });

  assert.equal(createManyCalled, false);
  assert.equal(sqsCommands.length, 1);
});

test("already notified event skips lease, SNS publish, and transaction, and deletes SQS message", async () => {
  const sqsCommands = [];
  let leaseCalled = false;
  let snsCalled = false;
  let txCalled = false;

  const prisma = {
    outbox: {
      async findUnique() {
        return { orderId: ORDER_ID, notifiedAt: new Date("2026-11-24T19:00:00.000Z") };
      },
      async updateMany() {
        leaseCalled = true;
        return { count: 1 };
      },
    },
    order: {
      async findUnique() {
        assert.fail("order.findUnique should not be called when already notified");
      },
    },
    async $transaction() {
      txCalled = true;
      return 1;
    },
  };

  await consumeOnce({
    prisma,
    sns: {
      async send() {
        snsCalled = true;
        return {};
      },
    },
    sqs: {
      async send(command) {
        sqsCommands.push(command);
        if (command instanceof ReceiveMessageCommand) {
          return { Messages: [{ Body: OUTBOX_ID, ReceiptHandle: "receipt-dup" }] };
        }
        return {};
      },
    },
    queueUrl: QUEUE_URL,
    topicArn: TOPIC_ARN,
  });

  assert.equal(leaseCalled, false);
  assert.equal(snsCalled, false);
  assert.equal(txCalled, false);
  assert.equal(sqsCommands.length, 2);
  assert.ok(sqsCommands[1] instanceof DeleteMessageCommand);
});

test("missing outbox, failed lease claim, and missing order return false without SNS publish or OrderEvent", async () => {
  let snsCalled = false;
  let txCalled = false;
  const sns = {
    async send() {
      snsCalled = true;
      return {};
    },
  };

  const missingOutboxResult = await processNotification(OUTBOX_ID, {
    prisma: {
      outbox: {
        async findUnique() { return null; },
        async updateMany() { return { count: 0 }; },
      },
      order: { async findUnique() { return null; } },
      async $transaction() {
        txCalled = true;
        return 0;
      },
    },
    sns,
    topicArn: TOPIC_ARN,
  });
  assert.equal(missingOutboxResult, false);

  const failedClaimResult = await processNotification(OUTBOX_ID, {
    prisma: {
      outbox: {
        async findUnique() { return { orderId: ORDER_ID, notifiedAt: null }; },
        async updateMany() { return { count: 0 }; },
      },
      order: {
        async findUnique() {
          assert.fail("order.findUnique should not be called when lease claim fails");
        },
      },
      async $transaction() {
        txCalled = true;
        return 0;
      },
    },
    sns,
    topicArn: TOPIC_ARN,
  });
  assert.equal(failedClaimResult, false);

  const missingOrderResult = await processNotification(OUTBOX_ID, {
    prisma: {
      outbox: {
        async findUnique() { return { orderId: ORDER_ID, notifiedAt: null }; },
        async updateMany() { return { count: 1 }; },
      },
      order: { async findUnique() { return null; } },
      async $transaction() {
        txCalled = true;
        return 0;
      },
    },
    sns,
    topicArn: TOPIC_ARN,
  });
  assert.equal(missingOrderResult, false);

  assert.equal(snsCalled, false);
  assert.equal(txCalled, false);
});

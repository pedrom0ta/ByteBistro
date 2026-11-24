import { randomUUID } from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";
import { PrismaClient } from "@prisma/client";
import { PublishCommand, SNSClient } from "@aws-sdk/client-sns";
import {
  DeleteMessageCommand, ReceiveMessageCommand, SendMessageCommand, SQSClient,
} from "@aws-sdk/client-sqs";
import { required, uuidPattern } from "./config.js";

const prisma = new PrismaClient();
const queueUrl = required("BYTEBISTRO_QUEUE_URL");
const topicArn = required("BYTEBISTRO_NOTIFICATION_TOPIC_ARN");
const sqs = new SQSClient({ maxAttempts: 3 });
const sns = new SNSClient({ maxAttempts: 3 });
const stop = new AbortController();

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => stop.abort());
}

async function publishOutbox() {
  const due = { OR: [{ leaseUntil: null }, { leaseUntil: { lte: new Date() } }] };
  const events = await prisma.outbox.findMany({
    where: { sentAt: null, ...due },
    orderBy: { createdAt: "asc" },
    take: 10,
    select: { id: true },
  });

  for (const event of events) {
    if (stop.signal.aborted) break;
    const leaseToken = randomUUID();
    const claim = await prisma.outbox.updateMany({
      where: { id: event.id, sentAt: null, ...due },
      data: { leaseToken, leaseUntil: new Date(Date.now() + 60_000) },
    });
    if (!claim.count) continue;
    try {
      await sqs.send(new SendMessageCommand({ QueueUrl: queueUrl, MessageBody: event.id }), {
        abortSignal: AbortSignal.timeout(20_000),
      });
      await prisma.outbox.updateMany({
        where: { id: event.id, leaseToken },
        data: { sentAt: new Date(), leaseToken: null, leaseUntil: null },
      });
    } catch (error) {
      console.error("Outbox publication failed", event.id, error instanceof Error ? error.name : "unknown");
    }
  }
}

async function consume() {
  const response = await sqs.send(new ReceiveMessageCommand({
    QueueUrl: queueUrl,
    MaxNumberOfMessages: 1,
    WaitTimeSeconds: 20,
  }), { abortSignal: AbortSignal.any([stop.signal, AbortSignal.timeout(35_000)]) });

  for (const message of response.Messages ?? []) {
    if (stop.signal.aborted) break;
    const id = message.Body;
    const receipt = message.ReceiptHandle;
    if (!id || !receipt || !uuidPattern.test(id)) {
      console.warn("Invalid queue message; left for the DLQ.");
      continue;
    }
    const event = await prisma.outbox.findUnique({
      where: { id },
      select: { orderId: true, notifiedAt: true },
    });
    if (!event) {
      console.warn("Outbox event missing; message left for the DLQ.", id);
      continue;
    }
    if (!event.notifiedAt) {
      const notifyLeaseToken = randomUUID();
      const claim = await prisma.outbox.updateMany({
        where: {
          id, notifiedAt: null,
          OR: [{ notifyLeaseUntil: null }, { notifyLeaseUntil: { lte: new Date() } }],
        },
        data: { notifyLeaseToken, notifyLeaseUntil: new Date(Date.now() + 60_000) },
      });
      if (!claim.count) continue;
      await sns.send(new PublishCommand({
        TopicArn: topicArn,
        Message: JSON.stringify({ id, type: "order.created", orderId: event.orderId }),
      }), { abortSignal: AbortSignal.timeout(20_000) });
      const updated = await prisma.outbox.updateMany({
        where: { id, notifyLeaseToken },
        data: { notifiedAt: new Date(), notifyLeaseToken: null, notifyLeaseUntil: null },
      });
      if (!updated.count) continue;
    }
    await sqs.send(new DeleteMessageCommand({ QueueUrl: queueUrl, ReceiptHandle: receipt }), {
      abortSignal: AbortSignal.timeout(20_000),
    });
  }
}

async function processLoop(task: () => Promise<void>, delay: number) {
  while (!stop.signal.aborted) {
    let pause = delay;
    try {
      await task();
    } catch (error) {
      if (stop.signal.aborted) break;
      console.error("Worker operation failed", error instanceof Error ? error.name : "unknown");
      pause = 3000 + Math.round(Math.random() * 2000);
    }
    if (pause) await sleep(pause, undefined, { signal: stop.signal }).catch(() => {});
  }
}

try {
  await Promise.all([processLoop(publishOutbox, 2000), processLoop(consume, 0)]);
} finally {
  sqs.destroy();
  sns.destroy();
  await prisma.$disconnect();
}

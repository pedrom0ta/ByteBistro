import { randomUUID } from "node:crypto";
import { setTimeout as sleep } from "node:timers/promises";
import { PrismaClient } from "@prisma/client";
import { SNSClient } from "@aws-sdk/client-sns";
import { SendMessageCommand, SQSClient } from "@aws-sdk/client-sqs";
import { required } from "./config.js";
import { consumeOnce } from "./worker-notifications.js";

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
  await consumeOnce({
    prisma,
    sqs,
    sns,
    queueUrl,
    topicArn,
    signal: stop.signal,
  });
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

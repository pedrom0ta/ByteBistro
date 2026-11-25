import { randomUUID } from "node:crypto";
import { PublishCommand, type SNSClient } from "@aws-sdk/client-sns";
import {
  DeleteMessageCommand,
  ReceiveMessageCommand,
  type SQSClient,
} from "@aws-sdk/client-sqs";
import { uuidPattern } from "./config.js";

export interface OrderNotificationData {
  mode: string;
  total: number;
  payment: string;
  created: Date;
}

export interface OrderCreatedNotification {
  subject: string;
  message: string;
}

export interface WorkerNotificationTx {
  outbox: {
    updateMany(args: {
      where: { id: string; notifyLeaseToken: string; notifiedAt: null };
      data: { notifiedAt: Date; notifyLeaseToken: null; notifyLeaseUntil: null };
    }): Promise<{ count: number }>;
  };
  orderEvent: {
    createMany(args: {
      data: Array<{
        orderId: string;
        action: string;
        actorId: null;
        reason: string;
        created: Date;
      }>;
    }): Promise<{ count: number }>;
  };
}

export interface WorkerNotificationPrisma {
  outbox: {
    findUnique(args: {
      where: { id: string };
      select: { orderId: true; notifiedAt: true };
    }): Promise<{ orderId: string; notifiedAt: Date | null } | null>;
    updateMany(args: {
      where: {
        id: string;
        notifiedAt: null;
        OR: [{ notifyLeaseUntil: null }, { notifyLeaseUntil: { lte: Date } }];
      };
      data: { notifyLeaseToken: string; notifyLeaseUntil: Date };
    }): Promise<{ count: number }>;
  };
  order: {
    findUnique(args: {
      where: { id: string };
      select: { mode: true; total: true; payment: true; created: true };
    }): Promise<OrderNotificationData | null>;
  };
  $transaction<T>(fn: (tx: WorkerNotificationTx) => Promise<T>): Promise<T>;
}

export interface WorkerNotificationDeps {
  prisma: WorkerNotificationPrisma;
  sns: Pick<SNSClient, "send">;
  topicArn: string;
  now?: () => Date;
  generateToken?: () => string;
}

export interface WorkerConsumeDeps extends WorkerNotificationDeps {
  sqs: Pick<SQSClient, "send">;
  queueUrl: string;
  signal?: AbortSignal;
}

export function formatOrderNumber(orderId: string): string {
  return orderId.replace(/-/g, "").slice(0, 8).toUpperCase();
}

export function buildOrderCreatedNotification(
  outboxId: string,
  orderId: string,
  order: OrderNotificationData,
): OrderCreatedNotification {
  const orderNumber = formatOrderNumber(orderId);
  const subject = `ByteBistro - Novo pedido #${orderNumber}`.slice(0, 100);
  const message = JSON.stringify({
    id: outboxId,
    type: "order.created",
    orderId,
    orderNumber,
    mode: order.mode,
    totalCents: order.total,
    payment: order.payment,
    createdAt: order.created.toISOString(),
  });
  return { subject, message };
}

export async function processNotification(id: string, deps: WorkerNotificationDeps): Promise<boolean> {
  const nowFn = deps.now ?? (() => new Date());
  const generateToken = deps.generateToken ?? randomUUID;

  const event = await deps.prisma.outbox.findUnique({
    where: { id },
    select: { orderId: true, notifiedAt: true },
  });
  if (!event) {
    console.warn("Outbox event missing; message left for the DLQ.", id);
    return false;
  }
  if (event.notifiedAt !== null) {
    return true;
  }

  const notifyLeaseToken = generateToken();
  const leaseTimestamp = nowFn();
  const claim = await deps.prisma.outbox.updateMany({
    where: {
      id,
      notifiedAt: null,
      OR: [{ notifyLeaseUntil: null }, { notifyLeaseUntil: { lte: leaseTimestamp } }],
    },
    data: {
      notifyLeaseToken,
      notifyLeaseUntil: new Date(leaseTimestamp.getTime() + 60_000),
    },
  });
  if (!claim.count) {
    return false;
  }

  const order = await deps.prisma.order.findUnique({
    where: { id: event.orderId },
    select: { mode: true, total: true, payment: true, created: true },
  });
  if (!order) {
    console.warn("Order missing for outbox event; message left for the DLQ.", id, event.orderId);
    return false;
  }

  const { subject, message } = buildOrderCreatedNotification(id, event.orderId, order);
  await deps.sns.send(
    new PublishCommand({
      TopicArn: deps.topicArn,
      Subject: subject,
      Message: message,
    }),
    { abortSignal: AbortSignal.timeout(20_000) },
  );

  const committedAt = nowFn();
  const updatedCount = await deps.prisma.$transaction(async (tx) => {
    const updated = await tx.outbox.updateMany({
      where: { id, notifyLeaseToken, notifiedAt: null },
      data: { notifiedAt: committedAt, notifyLeaseToken: null, notifyLeaseUntil: null },
    });
    if (updated.count > 0) {
      await tx.orderEvent.createMany({
        data: [
          {
            orderId: event.orderId,
            action: "notified",
            actorId: null,
            reason: "",
            created: committedAt,
          },
        ],
      });
    }
    return updated.count;
  });

  return updatedCount > 0;
}

export async function consumeOnce(deps: WorkerConsumeDeps): Promise<void> {
  const abortSignal = deps.signal
    ? AbortSignal.any([deps.signal, AbortSignal.timeout(35_000)])
    : AbortSignal.timeout(35_000);

  const response = await deps.sqs.send(
    new ReceiveMessageCommand({
      QueueUrl: deps.queueUrl,
      MaxNumberOfMessages: 1,
      WaitTimeSeconds: 20,
    }),
    { abortSignal },
  );

  for (const message of response.Messages ?? []) {
    if (deps.signal?.aborted) break;
    const id = message.Body;
    const receipt = message.ReceiptHandle;
    if (!id || !receipt || !uuidPattern.test(id)) {
      console.warn("Invalid queue message; left for the DLQ.");
      continue;
    }
    const completed = await processNotification(id, deps);
    if (!completed) continue;
    await deps.sqs.send(
      new DeleteMessageCommand({ QueueUrl: deps.queueUrl, ReceiptHandle: receipt }),
      { abortSignal: AbortSignal.timeout(20_000) },
    );
  }
}

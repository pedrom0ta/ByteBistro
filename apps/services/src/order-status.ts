import type { PrismaClient } from "@prisma/client";
import { uuidPattern } from "./config.js";

interface OrderStatusArgs {
  id: string;
  owner: string;
  customerId?: string | null;
}

const ownerPattern = /^[0-9a-f]{32}$/i;
const maxCustomerId = 9223372036854775807n;
const deliveryStages = ["Pedido recebido", "Em preparo", "Pronto para entrega", "Saiu para entrega", "Entregue"];
const restaurantStages = ["Pedido recebido", "Em preparo", "Pronto", "Entregue"];

function parseCustomerId(value: OrderStatusArgs["customerId"]): bigint | null {
  if (!value || !/^[0-9]{1,19}$/.test(value)) return null;
  const id = BigInt(value);
  return id > 0n && id <= maxCustomerId ? id : null;
}

export function createOrderStatusLookup(orders: Pick<PrismaClient["order"], "findFirst">) {
  return async (_parent: unknown, { id, owner, customerId }: OrderStatusArgs) => {
    if (!uuidPattern.test(id) || !ownerPattern.test(owner)) return null;

    const customer = parseCustomerId(customerId);
    const order = await orders.findFirst({
      where: { id, OR: [{ owner }, ...(customer === null ? [] : [{ customerId: customer }])] },
      select: { stage: true, mode: true, reason: true },
    });
    if (!order) return null;

    const { stage, mode, reason } = order;
    if (stage === 90 || stage === 91) {
      return { stage: 0, status: stage === 90 ? "Recusado" : "Cancelado", finished: false, reason };
    }

    const stages = mode === "delivery" ? deliveryStages : restaurantStages;
    const status = stages[stage];
    if (status === undefined) throw new Error("Order status is unavailable");

    return {
      stage,
      status,
      finished: stage === stages.length - 1 || (mode === "restaurante" && stage === 2),
      reason,
    };
  };
}

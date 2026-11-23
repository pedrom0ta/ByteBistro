import { timingSafeEqual } from "node:crypto";
import { ApolloServer } from "@apollo/server";
import { startStandaloneServer } from "@apollo/server/standalone";
import { PrismaClient } from "@prisma/client";
import { GraphQLError } from "graphql";
import { required, uuidPattern } from "./config.js";

const token = Buffer.from(required("GRAPHQL_SERVICE_TOKEN"));
const prisma = new PrismaClient();
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

const server = new ApolloServer({
  typeDefs,
  introspection: false,
  includeStacktraceInErrorResponses: false,
  resolvers: {
    Query: {
      async orderStatus(_parent: unknown, args: { id: string; owner: string; customerId?: string }) {
        if (!uuidPattern.test(args.id) || !/^[0-9a-f]{32}$/i.test(args.owner)) return null;
        const customerId = args.customerId;
        const hasCustomer = customerId && /^[0-9]{1,19}$/.test(customerId)
          && BigInt(customerId) <= 9223372036854775807n;
        const order = await prisma.order.findFirst({
          where: {
            id: args.id,
            OR: [{ owner: args.owner }, ...(hasCustomer ? [{ customerId: BigInt(customerId) }] : [])],
          },
          select: { stage: true, mode: true, reason: true },
        });
        if (!order) return null;
        const stages = order.mode === "delivery"
          ? ["Pedido recebido", "Em preparo", "Pronto para entrega", "Saiu para entrega", "Entregue"]
          : ["Pedido recebido", "Em preparo", "Pronto", "Entregue"];
        return {
          stage: order.stage >= 90 ? 0 : order.stage,
          status: order.stage === 90 ? "Recusado" : order.stage === 91 ? "Cancelado" : stages[order.stage],
          finished: order.stage === stages.length - 1 || (order.mode === "restaurante" && order.stage === 2),
          reason: order.reason,
        };
      },
    },
  },
});

await startStandaloneServer(server, {
  listen: { port: 4000 },
  context: async ({ req }) => {
    const received = Buffer.from(req.headers.authorization ?? "");
    const expected = Buffer.concat([Buffer.from("Bearer "), token]);
    if (received.length !== expected.length || !timingSafeEqual(received, expected)) {
      throw new GraphQLError("Unauthorized", { extensions: { code: "UNAUTHENTICATED", http: { status: 401 } } });
    }
    return {};
  },
});
console.info("Apollo listening on port 4000");

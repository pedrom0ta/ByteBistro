import { timingSafeEqual } from "node:crypto";
import { ApolloServer } from "@apollo/server";
import { startStandaloneServer } from "@apollo/server/standalone";
import { PrismaClient } from "@prisma/client";
import { GraphQLError } from "graphql";
import { required } from "./config.js";
import { createOrderStatusLookup } from "./order-status.js";

const authorization = Buffer.from(`Bearer ${required("GRAPHQL_SERVICE_TOKEN")}`);
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
    Query: { orderStatus: createOrderStatusLookup(prisma.order) },
  },
});

await startStandaloneServer(server, {
  listen: { port: 4000 },
  context: async ({ req }) => {
    const received = Buffer.from(req.headers.authorization ?? "");
    if (received.length !== authorization.length || !timingSafeEqual(received, authorization)) {
      throw new GraphQLError("Unauthorized", { extensions: { code: "UNAUTHENTICATED", http: { status: 401 } } });
    }
    return {};
  },
});
console.info("Apollo listening on port 4000");

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings


class GraphQLUnavailable(Exception):
    pass


def order_status(order_id, owner, customer_id):
    payload = json.dumps({
        "query": """
            query OrderStatus($id: ID!, $owner: String!, $customerId: ID) {
                orderStatus(id: $id, owner: $owner, customerId: $customerId) {
                    stage status finished reason
                }
            }
        """,
        "variables": {
            "id": str(order_id),
            "owner": owner,
            "customerId": str(customer_id) if customer_id is not None else None,
        },
    }).encode()
    request = Request(
        settings.BYTEBISTRO_GRAPHQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.GRAPHQL_SERVICE_TOKEN}",
        },
    )
    try:
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        if "errors" in result:
            raise GraphQLUnavailable()
        return result["data"]["orderStatus"]
    except (URLError, TimeoutError, ValueError, KeyError, TypeError) as error:
        raise GraphQLUnavailable() from error

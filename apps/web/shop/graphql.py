import json
from http.client import HTTPException
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
    try:
        request = Request(
            settings.BYTEBISTRO_GRAPHQL_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.GRAPHQL_SERVICE_TOKEN}",
            },
        )
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        if not isinstance(result, dict) or result.get("errors"):
            raise GraphQLUnavailable()
        status = result["data"]["orderStatus"]
        if status is None:
            return None
        stage = status["stage"]
        label = status["status"]
        finished = status["finished"]
        reason = status["reason"]
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        raise GraphQLUnavailable() from error

    if (
        type(stage) is not int or not 0 <= stage <= 4
        or not isinstance(label, str) or not label.strip()
        or not isinstance(finished, bool) or not isinstance(reason, str)
    ):
        raise GraphQLUnavailable()
    return {"stage": stage, "status": label, "finished": finished, "reason": reason}

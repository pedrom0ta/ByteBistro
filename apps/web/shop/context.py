def navigation(request):
    return {"count": sum(x["qty"] for x in request.session.get("cart", [])), "active": request.resolver_match.url_name if request.resolver_match else ""}

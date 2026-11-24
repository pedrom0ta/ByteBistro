from .models import Category, MenuProduct, Restaurant, Table

def products():
    return MenuProduct.objects.filter(archived=False, category__active=True).select_related("category")

def categories():
    return Category.objects.filter(active=True).order_by("position", "name").values_list("name", flat=True)

def restaurant():
    return Restaurant.objects.get(pk=1)

def tables():
    return Table.objects.filter(active=True).order_by("number")

def photo(image):
    if image.startswith("https://"):
        return image
    return "/static/images/" + (image or "logo.webp")


from django.db import migrations

def seed(apps, schema_editor):
    from shop.catalog import CATEGORIES, PRODUCTS
    category = apps.get_model("shop", "Category")
    product = apps.get_model("shop", "MenuProduct")
    table = apps.get_model("shop", "Table")
    order = apps.get_model("shop", "Order")
    event = apps.get_model("shop", "OrderEvent")
    categories = {name: category.objects.create(name=name, position=i) for i, name in enumerate(CATEGORIES)}
    for item in PRODUCTS:
        product.objects.create(slug=item.slug, name=item.name, category=categories[item.category],
                               description=item.description, price=item.price, image=item.image,
                               options=list(item.options), extras=list(item.extras), discount=item.discount)
    table.objects.bulk_create([table(number=n) for n in range(1, 7)])
    apps.get_model("shop", "Restaurant").objects.create(pk=1, payments=["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"])
    for record in order.objects.iterator():
        event.objects.create(order=record, action="received", created=record.created)
        event.objects.filter(order=record, action="received").update(created=record.created)

class Migration(migrations.Migration):
    dependencies = [("shop", "0002_category_ingredient_restaurant_table_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

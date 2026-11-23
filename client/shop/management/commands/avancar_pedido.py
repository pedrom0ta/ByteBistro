from django.core.management.base import BaseCommand, CommandError
from shop.models import Order
from shop.operations import actions, transition

class Command(BaseCommand):
    help = "Registra a próxima etapa de um pedido demonstrativo pelo número exibido."

    def add_arguments(self, parser):
        parser.add_argument("numero")

    def handle(self, numero, **options):
        matches = list(Order.objects.filter(id__startswith=numero.lower())[:2])
        if len(matches) != 1:
            raise CommandError("Informe um número de pedido válido e único.")
        order = matches[0]
        action = next(iter(actions(order, {"orders", "kitchen"})), None)
        if not action:
            raise CommandError("O pedido está encerrado.")
        try:
            transition(order, action, None)
        except ValueError as error:
            raise CommandError(str(error)) from error
        order.refresh_from_db()
        self.stdout.write(order.status)

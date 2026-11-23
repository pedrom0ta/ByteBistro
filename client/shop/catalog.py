from dataclasses import dataclass
import unicodedata

@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    category: str
    description: str
    price: int
    image: str
    options: tuple = ()
    extras: tuple = ()
    discount: int = 0
    available: bool = True

    @property
    def final(self):
        return self.price - self.discount

CATEGORIES = ["Hambúrgueres", "Pizzas", "Pratos", "Bebidas", "Acompanhamentos", "Sobremesas"]
PRODUCTS = [
    Product("smash", "Smash da Casa", CATEGORIES[0], "Pão brioche tostado, carne na chapa, cheddar, salada fresca e molho da casa.", 3490, "burger.jpg", ("Ao ponto", "Bem-passado"), (("Bacon", 600), ("Queijo extra", 400), ("Hambúrguer adicional", 900), ("Molho especial", 200)), 700),
    Product("pizza", "Pizza Margherita", CATEGORIES[1], "Massa de longa fermentação, molho de tomate, muçarela e manjericão fresco.", 4290, "pizza.jpg", (), (("Queijo extra", 400),)),
    Product("massa", "Farfalle ao pesto", CATEGORIES[2], "Farfalle ao pesto de manjericão com tomates-cereja e folhas frescas.", 3890, "prato.jpg", (), (("Parmesão", 300),)),
    Product("suco", "Suco de laranja", CATEGORIES[3], "Laranja espremida na hora, servido com gelo. Copo de 400 ml.", 1190, "bebida.jpg", ("Com açúcar", "Sem açúcar")),
    Product("fritas", "Fritas douradas", CATEGORIES[4], "Porção de batatas crocantes com parmesão e ervas.", 1590, "acompanhamento.jpg", (), (("Molho especial", 200),)),
    Product("brownie", "Brownie de chocolate", CATEGORIES[5], "Brownie de chocolate com casquinha delicada e centro macio.", 1690, "sobremesa.jpg"),
]
CATALOG = {p.slug: p for p in PRODUCTS}

def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(c))

def search(query, category):
    return [p for p in PRODUCTS if (not category or p.category == category) and normalize(query) in normalize(f"{p.name} {p.category} {p.description}")]

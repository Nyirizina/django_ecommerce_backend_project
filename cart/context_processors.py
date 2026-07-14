from .cart import Cart

# create a context processor function that will make the cart data available to all templates in the project

def cart(request):
    # return default data from the cart
    return {'cart': Cart(request)}
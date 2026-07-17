from store.models import Product

class Cart():
    def __init__(self, request):
        # create a session for the cart that helps the cart data temporarily persist in the database
        self.session = request.session

        # Get the current session key if it exists.
        cart = self.session.get('session_key')

        # if the user is new there should be no session key. creating one!
        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}

        #make the cart data available to all pages of site
        self.cart = cart
    
    def add(self, product):
        product_id = str(product.id)

        #logic
        if product_id in self.cart:
            pass
        else:
            self.cart[product_id] = {'price': str(product.price)}

        self.session.modified = True


    # returning length of the items in the array
    def __len__(self):
        return len(self.cart)
    
    def get_products(self):
        # get ids from cart
        product_ids = self.cart.keys()
        # use ids to lookup products in database
        products = Product.objects.filter(id__in=product_ids)

        # return the looked products
        return products


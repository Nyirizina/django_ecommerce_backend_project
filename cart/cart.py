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
    
    def add(self, product, quantity):
        product_id = str(product.id)
        product_qty = str(quantity)

        #logic
        if product_id in self.cart:
            pass
        else:
            #self.cart[product_id] = {'price': str(product.price)}
            self.cart[product_id] = int(product_qty)

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
    
    def get_quants(self):
        quantities = self.cart
        return quantities

    def update(self, product, quantity):
        product_id = str(product)
        product_qty = int(quantity)

        #how django sees us {'4':3, '2':5}
        # get cart
        ourcart = self.cart
        #update dictionary/cart
        ourcart[product_id] = product_qty

        self.session.modified = True

        result = self.cart
        return result

    def delete(self, product):
        product_id = str(product)

        # delete from dictionary/cart
        if product_id in self.cart:
            del self.cart[product_id]

        self.session.modified = True
    
    def totals(self):
        # get product ids
        product_ids = self.cart.keys()
        # lookup keys in the products database model
        products = Product.objects.filter(id__in=product_ids)
        # get quantities
        quantities = self.cart
        # start counting from zero
        total = 0

        for key,value in quantities.items():
            key = int(key)
            for product in products:
                #will be taking product's value by product_id as key value pairs and multiplying the value by price {"4":2}
                if product.id == key:
                    if product.is_sale:
                       total = total + (product.sale_price * value)
                    else:
                       total = total + (product.price * value)

        return total 


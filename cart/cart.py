
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
from django.shortcuts import render, get_object_or_404
from .cart import Cart
from store.models import Product
from django.http import JsonResponse

def cart_summary(request):
    # get cart
    cart =  Cart(request)
    cart_products = cart.get_products
    quantities = cart.get_quants
    totals = cart.totals()
    return render(request, 'cart_summary.html',{"cart_products": cart_products, "quantities": quantities, "totals":totals})

def cart_add(request):
    # get cart
    cart = Cart(request)
    # test for post check if they are posting
    if request.POST.get('action') == 'post':
        # what to get after posting
        product_id = int(request.POST.get('product_id'))
        product_qty = int(request.POST.get('product_qty'))

        # look for product in database
        product = get_object_or_404(Product, id=product_id)
        # Save to session
        cart.add(product=product, quantity=product_qty)

        # get cart quantity
        cart_quantity = cart.__len__()



        #return response
        # response = JsonResponse({'Product Name: ': product.name})
        response = JsonResponse({'qty ': cart_quantity})
        return response

    

def cart_delete(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        # what to get after posting
        product_id = int(request.POST.get('product_id'))
        #call delete function in cart
        cart.delete(product=product_id)
        response = JsonResponse({'product':product_id})
        return response

def cart_update(request):
    cart = Cart(request)
    if request.POST.get('action') == 'post':
        # what to get after posting
        product_id = int(request.POST.get('product_id'))
        product_qty = int(request.POST.get('product_qty'))

        cart.update(product=product_id, quantity=product_qty)

        response = JsonResponse({'qty':product_qty})
        return response
        




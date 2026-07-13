from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_summary, name='cart_summary'),
    path('add/', views.cart_add, name='cart_add'),
    path('delete/', views.cart_delete, name='cart_delete'),
    path('update/', views.cart_update, name='cart_update'),

]

# <int:pk> is a path converter that captures an integer value from the URL and passes it as a keyword argument to the view function. In this case, it is used to capture the primary key (pk) of a product and pass it to the home view.
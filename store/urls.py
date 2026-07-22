from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register/', views.register_user, name='register'),
    path('update_user/', views.update_user, name='update_user'),
    path('product/<int:pk>', views.product, name='product'),
    path('category/<str:cat>', views.category, name='category'),
    path('category_summary/', views.category_summary, name='category_summary'),

]

# <int:pk> is a path converter that captures an integer value from the URL and passes it as a keyword argument to the view function. In this case, it is used to capture the primary key (pk) of a product and pass it to the home view.
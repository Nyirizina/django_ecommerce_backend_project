from django.shortcuts import render , redirect
from . models import Product, Category
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .forms import SignUpForm
from django import forms

def category_summary(request):
    categories = Category.objects.all()
    return render(request, 'category_summary.html', {"categories": categories})

def category(request, cat):
    #replace hyphens with spaces in the category name
    cat = cat.replace('-', ' ')
    #Grab the category object from the url
    try:
        #look for the category object in the database
        category = Category.objects.get(name=cat)
        #grab all the products in that category
        products = Product.objects.filter(category=category) 
        return render(request, 'category.html', {'products': products, 'category': category})
    except:
        messages.success(request, "Category does not exist....")
        return redirect('home')


def product(request,pk):
    product= Product.objects.get(id=pk)
    return render(request, 'product.html', {'product': product})


# Create your views here.
def home(request):
    products = Product.objects.all()
    return render(request, 'home.html', {'products': products})
# about view
def about(request):
    return render(request, 'About.html')
# login user view
def login_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "You have been logged in.")
            return redirect('home')
        else:
            messages.error(request, "Please try again.")
            return redirect('login')
    else:
        return render(request, 'login.html')
        

    
# logout user view
def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')

# register user view
def register_user(request):
    form = SignUpForm()
    if request.method == 'POST':
        #check if the form is valid
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']

            # login user
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, "You have registered successfully.")
            return redirect('home')
        else:
             messages.success(request, "Ouups please try again.")
             return redirect('register')   
    else:
        return render(request, 'register.html', {'form':form})




    
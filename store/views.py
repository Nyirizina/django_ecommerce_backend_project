from django.shortcuts import render , redirect
from . models import Product, Category, Profile
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .forms import SignUpForm, UpdateUserForm, ChangePasswordForm, UserInfoForm
from django import forms
from django.db.models import Q

def update_info(request):
    if request.user.is_authenticated:
            # getting user from the db who is requesting
            current_user = Profile.objects.get(user__id=request.user.id)
            form = UserInfoForm(request.POST or None, instance=current_user)
    
            if form.is_valid():
                form.save()
                # loging in user automatically after updating login details
                messages.success(request, "Your info have been updated !!!!")
                return redirect('home')
            return render(request, "update_info.html",{"form":form})
    else:
            messages.success(request, "You must be logged IN!!!")
            return redirect('home')

def update_password(request):
    if request.user.is_authenticated:
        current_user = request.user
        # didi they fill out the form
        if request.method == 'POST':
            form = ChangePasswordForm(current_user, request.POST)
            #CHECK IF FOR IS VALID
            if form.is_valid():
                form.save()
                messages.success(request, "your password have been updated....")
                #log in auto after changing the password
                login(request, current_user)
                return redirect('login')
            else:
                for error in list(form.errors.values()):
                    messages.error(request, error)
                    return redirect('update_password')  

            
        else:
            form = ChangePasswordForm(current_user)
            return render(request, "update_password.html",{'form':form})
    else:
        messages.success(request, "You must be logged in !!")
        return redirect('home')
def update_user(request):
    if request.user.is_authenticated:
        # getting user from the db who is requesting
        current_user = User.objects.get(id=request.user.id)
        users_form = UpdateUserForm(request.POST or None, instance=current_user)

        if users_form.is_valid():
            users_form.save()
            # loging in user automatically after updating login details
            login(request, current_user)
            messages.success(request, "User has been successfully updated !!!!")
            return redirect('home')
        return render(request, "update_user.html",{"users_form":users_form})
    else:
        messages.success(request, "You must be logged IN!!!")
        return redirect('home')


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
            messages.success(request, "You have registered successfully. Please fill in your user info here")
            return redirect('update_info')
        else:
             messages.success(request, "Ouups please try again.")
             return redirect('register')   
    else:
        return render(request, 'register.html', {'form':form})


def search(request):
    #determine if they filled the form
    if request.method == "POST":
        searched = request.POST['searched']
        #query the products (icontains makes it none case sensitive) you can search without issues of letter mismatch
        searched = Product.objects.filter(Q(name__icontains=searched) | Q(description__icontains=searched))
        #test for null
        if not searched:
            messages.success(request, "ouups !! Product not in stock.")
            return render(request, 'search.html', {})
        else:
            return render(request, 'search.html', {'searched':searched})
    else:
       return render(request, 'search.html', {})







    
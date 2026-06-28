from django.shortcuts import render

def login_view(request):
    return render(request, 'login.html')

def login(request):
    return render(request,'login.html')
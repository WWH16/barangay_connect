from django.shortcuts import render

def login(request):
    return render(request,'resident/login.html')

def resident_dashboard(request):
    return render(request,'resident/resident-dashboard.html')
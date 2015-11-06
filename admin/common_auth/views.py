from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, logout as logout_user, login as auth_login, views
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import render, redirect

from forms import RegistrationForm, LoginForm
from models import AdminUser

#@login_required
def home(request):
	context = {'user': request.user}
	return render(request, 'home.html', context)

def register(request):
	if request.user.is_authenticated():
		return redirect('/admin/auth/home')
	if request.method == 'POST':
		form = RegistrationForm(request.POST)
		if form.is_valid():
			username = form.cleaned_data['username']
			email = form.cleaned_data['email']
			password = form.cleaned_data['password']
			user = User.objects.create_user(username=username,
				email=email, password=password)
			user.save()
			admin_user = AdminUser(user=user)
			admin_user.save()
			admin_user = authenticate(username=username, password=password)
			auth_login(request, admin_user)
			return redirect('/admin/auth/home')
		else:
			context = {'form': form}
			return render(request, 'register.html', context)
	else:
		''' User not submitting form, show blank registrations form '''
		form = RegistrationForm()
		context = {'form': form}
		return render(request, 'register.html', context)

def login(request):
	if request.user.is_authenticated():
		return redirect('/admin/auth/home/')
	form = LoginForm(request.POST or None)
	if request.POST and form.is_valid():
		username = form.cleaned_data.get('username')
		password = form.cleaned_data.get('password')
		admin_user = authenticate(username=username, password=password)
		if admin_user:
			auth_login(request, admin_user)
			return redirect('/admin/auth/home/')
		else:
			return redirect('/admin/auth/login/')
	context = {'form': form}
	return render(request, 'login.html', context)

def logout(request):
	logout_user(request)
	return redirect('/admin/auth/login/')
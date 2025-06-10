from django.shortcuts import render, redirect
from django.contrib.auth import login , authenticate
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email')


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        role = request.POST.get('role')

        if form.is_valid():
            user = form.save(commit=False)
            user.role = role
            user.save()
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})



@login_required(login_url='login')  # Explicit login redirection
def dashboard(request):
    if request.user.role == 'admin':
        return render(request, 'dashboards/admin_dashboard.html')
    elif request.user.role == 'teacher':
        return render(request, 'dashboards/teacher_dashboard.html')
    elif request.user.role == 'student':
        return render(request, 'dashboards/student_dashboard.html')
    else:
        return redirect('login')


def custom_login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        role = request.POST['role']

        user = authenticate(request, username=username, password=password)

        if user is not None and user.role == role:
            login(request, user)
            if role == 'admin':
                return redirect('admin_dashboard')
            elif role == 'teacher':
                return redirect('teacher_dashboard')
            elif role == 'student':
                return redirect('student_dashboard')
        else:
            messages.error(request, 'Invalid credentials or role mismatch.')

    return render(request, 'auth/login.html')
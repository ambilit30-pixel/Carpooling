from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages, auth
from django.db.models import Sum
from django.utils import timezone

from .models import Ride, RideShare, UserProfile
from .forms import (
    RegistrationForm, LoginForm, EditInfoForm, ChangePasswordForm,
    DriverForm, RideForm, RideEditForm, ShareForm, ShareEditForm
)

# ---------------------- Authentication ----------------------

def register(request):
    """Register a new user"""
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password2'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email']
            )
            UserProfile.objects.create(user=user, role='user')  # default role
            messages.success(request, 'Registration successful! You can login now.')
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    """Login view"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = auth.authenticate(username=username, password=password)
            if user:
                auth.login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid credentials')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

@login_required
def logout_view(request):
    auth.logout(request)
    return redirect('login')


# ---------------------- Dashboard ----------------------

@login_required
def dashboard(request):
    user = request.user
    user_profile = user.userprofile

    user_rides = Ride.objects.filter(rider=user)
    driving_rides = Ride.objects.filter(driver=user)
    shared_rides = Ride.objects.filter(rideshare__sharer=user)

    return render(request, 'dashboard.html', {
        'user_rides': user_rides,
        'driving_rides': driving_rides,
        'shared_rides': shared_rides,
        'profile': user_profile
    })


# ---------------------- Profile ----------------------

@login_required
def profile(request):
    return render(request, 'profile.html', {'user': request.user})

@login_required
def edit_info(request):
    user = request.user
    if request.method == 'POST':
        form = EditInfoForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
    else:
        form = EditInfoForm(instance=user)
    return render(request, 'edit_info.html', {'form': form})

@login_required
def change_password(request):
    user = request.user
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            if not user.check_password(form.cleaned_data['old_password']):
                messages.error(request, 'Old password incorrect')
            else:
                user.set_password(form.cleaned_data['new_password2'])
                user.save()
                messages.success(request, 'Password changed successfully!')
                return redirect('login')
    else:
        form = ChangePasswordForm()
    return render(request, 'change_password.html', {'form': form})

@login_required
def register_driver(request):
    """Register user as a driver"""
    user = request.user
    if request.method == 'POST':
        form = DriverForm(request.POST, instance=user.userprofile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.role = 'driver'
            profile.save()
            messages.success(request, 'You are now registered as a driver.')
            return redirect('dashboard')
    else:
        form = DriverForm(instance=user.userprofile)
    return render(request, 'register_driver.html', {'form': form})


# ---------------------- Ride Management ----------------------

@login_required
def create_ride(request):
    if request.method == 'POST':
        form = RideForm(request.POST)
        if form.is_valid():
            Ride.objects.create(
                rider=request.user,
                driver=None,
                source=form.cleaned_data['source'],
                destination=form.cleaned_data['destination'],
                arrivaldate=form.cleaned_data['arrivaldate'],
                passenger=form.cleaned_data['passenger'],
                sharable=form.cleaned_data['sharable'],
                status='open'
            )
            messages.success(request, 'Ride created successfully!')
            return redirect('dashboard')
    else:
        form = RideForm()
    return render(request, 'create_ride.html', {'form': form})

@login_required
def edit_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, rider=request.user)
    if ride.status != 'open':
        messages.error(request, 'Only open rides can be edited.')
        return redirect('dashboard')
    if request.method == 'POST':
        form = RideEditForm(request.POST, instance=ride)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ride updated successfully!')
            return redirect('dashboard')
    else:
        form = RideEditForm(instance=ride)
    return render(request, 'edit_ride.html', {'form': form, 'ride': ride})

@login_required
def delete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, rider=request.user)
    if ride.status == 'open':
        ride.delete()
        messages.success(request, 'Ride deleted successfully.')
    else:
        messages.error(request, 'Only open rides can be deleted.')
    return redirect('dashboard')


# ---------------------- Assign / Manage Driver ----------------------

@login_required
def assign_driver(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    drivers = UserProfile.objects.filter(role='driver')
    if request.method == 'POST':
        driver_id = request.POST.get('driver_id')
        driver_user = get_object_or_404(User, id=driver_id)
        ride.driver = driver_user
        ride.save()
        messages.success(request, f'{driver_user.username} assigned as driver.')
        return redirect('dashboard')
    return render(request, 'assign_driver.html', {'ride': ride, 'drivers': drivers})

@login_required
def start_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.driver != request.user:
        messages.error(request, 'Only assigned driver can start the ride.')
    elif ride.status != 'open':
        messages.error(request, 'Ride cannot be started.')
    else:
        ride.status = 'confirmed'
        ride.save()
        messages.success(request, 'Ride started.')
    return redirect('dashboard')

@login_required
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.driver != request.user:
        messages.error(request, 'Only assigned driver can complete the ride.')
    else:
        ride.status = 'complete'
        ride.save()
        messages.success(request, 'Ride completed.')
    return redirect('dashboard')


# ---------------------- Ride Sharing ----------------------

@login_required
def find_rides_to_share(request):
    if request.method == 'POST':
        form = ShareForm(request.POST)
        if form.is_valid():
            dest = form.cleaned_data['destination']
            early, late = form.cleaned_data['earlyarrival'], form.cleaned_data['latearrival']
            passenger_count = form.cleaned_data['passenger']

            rides = Ride.objects.filter(
                destination=dest,
                arrivaldate__range=[early, late],
                sharable=True,
                status='open'
            ).exclude(rider=request.user)

            return render(request, 'share_results.html', {
                'rides': rides,
                'passenger_count': passenger_count
            })
    else:
        form = ShareForm()
    return render(request, 'find_rides.html', {'form': form})

@login_required
def join_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if request.method == 'POST':
        passenger_count = int(request.POST.get('passenger_count', 1))
        taken_seats = ride.rideshare_set.aggregate(total=Sum('passenger_count'))['total'] or 0
        driver_capacity = ride.driver.userprofile.capacity if ride.driver else 0
        available_seats = driver_capacity - ride.passenger - taken_seats
        if passenger_count <= 0:
            messages.error(request, 'Passenger count must be at least 1.')
        elif passenger_count > available_seats:
            messages.error(request, 'Not enough available seats.')
        else:
            RideShare.objects.create(
                ride=ride,
                sharer=request.user,
                passenger_count=passenger_count
            )
            messages.success(request, 'You joined the ride.')
        return redirect('dashboard')
    return render(request, 'join_ride.html', {'ride': ride})

@login_required
def leave_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    RideShare.objects.filter(ride=ride, sharer=request.user).delete()
    messages.success(request, 'You left the ride.')
    return redirect('dashboard')

@login_required
def edit_share(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    share = get_object_or_404(RideShare, ride=ride, sharer=request.user)
    if request.method == 'POST':
        form = ShareEditForm(request.POST, instance=share)
        if form.is_valid():
            form.save()
            messages.success(request, 'Share updated.')
            return redirect('dashboard')
    else:
        form = ShareEditForm(instance=share)
    return render(request, 'edit_share.html', {'form': form, 'ride': ride})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme
import logging

from .models import Ride, RideShare, UserProfile
from .forms import (
    RegistrationForm, LoginForm, EditInfoForm, ChangePasswordForm,
    DriverForm, RideForm, RideEditForm, ShareForm, ShareEditForm
)

# helper
def is_admin(user):
    return user.is_staff or user.is_superuser

logger = logging.getLogger(__name__)

# ---------------------- Authentication ----------------------
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # UserProfile auto-created via signal
            messages.success(request, "Registration successful! You can login now.")
            return redirect('rides:login')
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    # support ?next=/some/path
    next_url = request.GET.get('next') or request.POST.get('next') or None

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Attempt to authenticate
            user = authenticate(request, username=username, password=password)

            # Debug logging (won't show in UI) - enable logging to see these
            if user is None:
                logger.debug("Authentication failed for username=%s", username)
            else:
                logger.debug("Authentication succeeded for username=%s (is_active=%s)", username, user.is_active)

            if user:
                if not user.is_active:
                    messages.error(request, "Account is inactive. Contact admin.")
                else:
                    auth_login(request, user)
                    messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                    # safe redirect
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect('rides:dashboard')
            else:
                # more helpful message
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form, 'next': next_url})


@login_required
def logout_view(request):
    auth_logout(request)
    return redirect('rides:login')


@login_required
@require_POST
def revert_to_passenger(request):
    """
    Allow a logged-in user to switch their role back to 'user' (passenger).
    This respects your 'no verification' policy: switching is immediate.
    """
    profile = getattr(request.user, 'userprofile', None)
    if not profile:
        messages.error(request, "User profile missing.")
        return redirect('rides:dashboard')

    # Optionally clear driver-specific fields if you want (vehicle/plate/capacity)
    # Uncomment if desired:
    # profile.vehicle = ''
    # profile.plate = ''
    # profile.capacity = 0
    # profile.special = ''

    profile.role = UserProfile.ROLE_USER
    profile.save()
    messages.success(request, "You are now set as a passenger.")
    return redirect('rides:profile')


# ---------------------- Dashboard & Profile ----------------------
@login_required
def dashboard(request):
    """
    Dashboard shows:
      - Rides the user posted (user_rides)
      - Rides where user is assigned driver (driving_rides)
      - Rides the user joined as sharer (shared_rides)
    """
    user = request.user
    profile = getattr(user, 'userprofile', None)

    user_rides = Ride.objects.filter(rider=user).order_by('-arrivaldate')
    driving_rides = Ride.objects.filter(driver=user).order_by('-arrivaldate')
    shared_rides = Ride.objects.filter(rideshare__sharer=user).distinct().order_by('-arrivaldate')

    context = {
        'profile': profile,
        'user_rides': user_rides,
        'driving_rides': driving_rides,
        'shared_rides': shared_rides,
    }
    return render(request, 'dashboard.html', context)


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
            messages.success(request, "Profile updated successfully.")
            return redirect('rides:profile')
    else:
        form = EditInfoForm(instance=user)
    return render(request, 'edit_info.html', {'form': form})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data['old_password']):
                messages.error(request, "Old password incorrect")
            else:
                request.user.set_password(form.cleaned_data['new_password1'])
                request.user.save()
                messages.success(request, "Password changed; please login again.")
                return redirect('rides:login')
    else:
        form = ChangePasswordForm()
    return render(request, 'change_password.html', {'form': form})


@login_required
def register_driver(request):
    profile = getattr(request.user, 'userprofile', None)
    if not profile:
        messages.error(request, "User profile missing.")
        return redirect('rides:dashboard')
    if request.method == 'POST':
        form = DriverForm(request.POST, instance=profile)
        if form.is_valid():
            prof = form.save(commit=False)
            prof.role = UserProfile.ROLE_DRIVER
            prof.save()
            messages.success(request, "You are now registered as a driver.")
            return redirect('rides:dashboard')
    else:
        form = DriverForm(instance=profile)
    return render(request, 'register_driver.html', {'form': form})


# ---------------------- Ride CRUD ----------------------
@login_required
def create_ride(request):
    # Optionally require role==driver or vehicle/capacity present (not enforced by default)
    # if request.user.userprofile.role != UserProfile.ROLE_DRIVER:
    #     messages.error(request, "Only drivers can create rides. Register as a driver first.")
    #     return redirect('rides:register_driver')

    if request.method == 'POST':
        form = RideForm(request.POST)
        if form.is_valid():
            ride = form.save(commit=False)
            ride.rider = request.user
            # arrivaldate already timezone-aware via form clean
            ride.save()
            messages.success(request, "Ride created successfully!")
            return redirect('rides:dashboard')
    else:
        form = RideForm()
    return render(request, 'create_ride.html', {'form': form})


@login_required
def edit_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, rider=request.user)
    if ride.status != Ride.STATUS_OPEN:
        messages.error(request, "Only open rides can be edited.")
        return redirect('rides:dashboard')
    if request.method == 'POST':
        form = RideEditForm(request.POST, instance=ride)
        if form.is_valid():
            form.save()
            messages.success(request, "Ride updated successfully!")
            return redirect('rides:dashboard')
    else:
        form = RideEditForm(instance=ride)
    return render(request, 'edit_ride.html', {'form': form, 'ride': ride})


@login_required
@require_POST
def delete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, rider=request.user)
    if ride.status == Ride.STATUS_OPEN:
        ride.delete()
        messages.success(request, "Ride deleted successfully.")
    else:
        messages.error(request, "Only open rides can be deleted.")
    return redirect('rides:dashboard')


# ---------------------- Assign, Start, Complete ----------------------
@login_required
def assign_driver(request, ride_id):
    """
    Assign driver to ride.
    Permission: only ride.rider (creator) or admin may assign.
    """
    ride = get_object_or_404(Ride, id=ride_id)
    if not (request.user == ride.rider or is_admin(request.user)):
        raise PermissionDenied("Only ride creator or admin can assign driver.")

    # drivers are UserProfiles with role='driver'
    drivers = UserProfile.objects.filter(role=UserProfile.ROLE_DRIVER).select_related('user')
    if request.method == 'POST':
        driver_user_id = request.POST.get('driver_id')
        driver_user = get_object_or_404(User, id=driver_user_id)
        # assign and save
        ride.assign_driver(driver_user)
        messages.success(request, f"{driver_user.username} assigned as driver.")
        return redirect('rides:dashboard')
    return render(request, 'assign_driver.html', {'ride': ride, 'drivers': drivers})


@login_required
@require_POST
def start_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.driver != request.user:
        messages.error(request, "Only assigned driver can start the ride.")
        return redirect('rides:dashboard')
    if ride.status != Ride.STATUS_OPEN:
        messages.error(request, "Ride cannot be started.")
        return redirect('rides:dashboard')
    try:
        ride.start()
        messages.success(request, "Ride started.")
    except Exception as e:
        messages.error(request, f"Could not start ride: {e}")
    return redirect('rides:dashboard')


@login_required
@require_POST
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.driver != request.user:
        messages.error(request, "Only assigned driver can complete the ride.")
        return redirect('rides:dashboard')
    try:
        ride.complete()
        messages.success(request, "Ride completed.")
    except Exception as e:
        messages.error(request, f"Could not complete ride: {e}")
    return redirect('rides:dashboard')


# ---------------------- Ride Sharing (search/join/leave/edit) ----------------------
@login_required
def find_rides_to_share(request):
    if request.method == 'POST':
        form = ShareForm(request.POST)
        if form.is_valid():
            dest = form.cleaned_data['destination']
            early = form.cleaned_data['earlyarrival']
            late = form.cleaned_data['latearrival']
            passenger_count = form.cleaned_data['passenger']

            rides = Ride.objects.filter(
                destination__iexact=dest,
                arrivaldate__range=[early, late],
                sharable=True,
                status=Ride.STATUS_OPEN
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
        # passenger_count from form or POST
        try:
            passenger_count = int(request.POST.get('passenger_count', 1))
        except ValueError:
            messages.error(request, "Invalid passenger count.")
            return redirect('rides:dashboard')

        # basic checks
        if passenger_count <= 0:
            messages.error(request, "Passenger count must be at least 1.")
            return redirect('rides:dashboard')
        if not ride.sharable or ride.status != Ride.STATUS_OPEN:
            messages.error(request, "This ride is not available for sharing.")
            return redirect('rides:dashboard')
        if not ride.driver:
            messages.error(request, "Driver not assigned yet; cannot join.")
            return redirect('rides:dashboard')

        # transactional seat reservation to prevent race condition
        try:
            with transaction.atomic():
                # lock ride row
                locked_ride = Ride.objects.select_for_update().get(id=ride.id)
                available_seats = locked_ride.available_seats()
                # check if sharer already exists
                existing = RideShare.objects.filter(ride=locked_ride, sharer=request.user).first()
                # if existing, compute seats excluding their current booked seats
                existing_count = existing.passenger_count if existing else 0
                effective_available = available_seats + existing_count  # because existing_count would be freed if updating
                if passenger_count > effective_available:
                    messages.error(request, "Not enough available seats.")
                    return redirect('rides:dashboard')

                if existing:
                    existing.passenger_count = passenger_count
                    existing.save()
                else:
                    RideShare.objects.create(ride=locked_ride, sharer=request.user, passenger_count=passenger_count)
                messages.success(request, "You joined the ride.")
                return redirect('rides:dashboard')
        except IntegrityError:
            messages.error(request, "Could not join the ride due to a concurrency issue. Try again.")
            return redirect('rides:dashboard')

    # GET: show join page
    return render(request, 'join_ride.html', {'ride': ride})


@login_required
@require_POST
def leave_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    RideShare.objects.filter(ride=ride, sharer=request.user).delete()
    messages.success(request, "You left the ride.")
    return redirect('rides:dashboard')


@login_required
def edit_share(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    share = get_object_or_404(RideShare, ride=ride, sharer=request.user)
    if request.method == 'POST':
        form = ShareEditForm(request.POST, instance=share)
        if form.is_valid():
            new_count = form.cleaned_data['passenger_count']
            # transactional check similar to join
            try:
                with transaction.atomic():
                    locked_ride = Ride.objects.select_for_update().get(id=ride.id)
                    # compute effective available seats including current share
                    available = locked_ride.available_seats() + share.passenger_count
                    if new_count > available:
                        messages.error(request, "Not enough available seats for this update.")
                        return redirect('rides:dashboard')
                    form.save()
                    messages.success(request, "Share updated.")
                    return redirect('rides:dashboard')
            except IntegrityError:
                messages.error(request, "Could not update share due to concurrency. Try again.")
                return redirect('rides:dashboard')
    else:
        form = ShareEditForm(instance=share)
    return render(request, 'edit_share.html', {'form': form, 'ride': ride})

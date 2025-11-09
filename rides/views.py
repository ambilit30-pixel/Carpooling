from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from .models import Ride, RideShare, UserProfile
from .forms import (
    RegistrationForm, LoginForm, EditInfoForm, ChangePasswordForm,
    DriverForm, RideForm, RideEditForm, ShareForm, ShareEditForm
)

def is_admin(user):
    return user.is_staff or user.is_superuser

# ---------------- Auth ----------------
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Registration successful! You can login now.")
            return redirect('rides:login')
    else:
        form = RegistrationForm()
    return render(request, 'rides/register.html', {'form': form})

import logging
logger = logging.getLogger(__name__)



logger = logging.getLogger(__name__)

def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next') or None
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                if not user.is_active:
                    messages.error(request, "Account is inactive.")
                else:
                    auth_login(request, user)
                    messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                    # safe redirect
                    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                        return redirect(next_url)
                    return redirect('rides:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()
    return render(request, 'rides/login.html', {'form': form, 'next': next_url})



@login_required
def logout_view(request):
    auth_logout(request)
    return redirect('rides:login')

# ---------------- Role switching ----------------
@login_required
@require_POST
def revert_to_passenger(request):
    profile = getattr(request.user, 'userprofile', None)
    if not profile:
        messages.error(request, "Profile missing.")
        return redirect('rides:dashboard')
    profile.role = UserProfile.ROLE_USER
    profile.save()
    messages.success(request, "Role set to Passenger.")
    return redirect('rides:dashboard')

@login_required
@require_POST
def set_role_driver(request):
    profile = getattr(request.user, 'userprofile', None)
    if not profile:
        messages.error(request, "Profile missing.")
        return redirect('rides:dashboard')
    profile.role = UserProfile.ROLE_DRIVER
    profile.save()
    messages.success(request, "Role set to Driver.")
    return redirect('rides:dashboard')

# ---------------- Dashboard & profile ----------------
@login_required
def dashboard(request):
    logging.getLogger(__name__).debug("DASHBOARD: request.user: %s, is_authenticated=%s", request.user, request.user.is_authenticated)
    profile = getattr(request.user, 'userprofile', None)
    if profile and profile.role == UserProfile.ROLE_DRIVER:
        # driver dashboard
        pending = Ride.objects.filter(driver=request.user, assignment_status=Ride.ASSIGN_PENDING)
        accepted = Ride.objects.filter(driver=request.user, assignment_status=Ride.ASSIGN_ACCEPTED).order_by('-arrivaldate')
        offered = Ride.objects.filter(rider=request.user).order_by('-arrivaldate')
        context = {'role': 'driver', 'pending': pending, 'accepted': accepted, 'offered': offered, 'profile': profile}
        return render(request, 'rides/dashboard.html', context)
    else:
        # passenger dashboard
        user_rides = Ride.objects.filter(rider=request.user).order_by('-arrivaldate')
        driving_rides = Ride.objects.filter(driver=request.user).order_by('-arrivaldate')
        shared_rides = Ride.objects.filter(rideshare__sharer=request.user).distinct().order_by('-arrivaldate')
        context = {'role': 'passenger', 'user_rides': user_rides, 'driving_rides': driving_rides, 'shared_rides': shared_rides, 'profile': profile}
        return render(request, 'rides/dashboard.html', context)

@login_required
def profile_view(request):
    return render(request, 'rides/profile.html', {'user': request.user})

@login_required
def edit_info(request):
    if request.method == 'POST':
        form = EditInfoForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect('rides:profile')
    else:
        form = EditInfoForm(instance=request.user)
    return render(request, 'rides/edit_info.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data['old_password']):
                messages.error(request, "Old password incorrect.")
            else:
                request.user.set_password(form.cleaned_data['new_password1'])
                request.user.save()
                messages.success(request, "Password changed. Please login again.")
                return redirect('rides:login')
    else:
        form = ChangePasswordForm()
    return render(request, 'rides/change_password.html', {'form': form})

@login_required
def register_driver(request):
    profile = getattr(request.user, 'userprofile', None)
    if request.method == 'POST':
        form = DriverForm(request.POST, instance=profile)
        if form.is_valid():
            prof = form.save(commit=False)
            prof.role = UserProfile.ROLE_DRIVER
            prof.save()
            messages.success(request, "You are registered as a driver.")
            return redirect('rides:dashboard')
    else:
        form = DriverForm(instance=profile)
    return render(request, 'rides/register_driver.html', {'form': form})

# ---------------- Ride CRUD ----------------

def my_rides(request):
    """
    Overview page for current user:
      - created_rides: rides where user is the creator (rider)
      - assigned_rides: rides where user is the assigned driver
      - joined_rides: rides user has joined as a sharer
    """
    user = request.user
    profile = getattr(user, 'userprofile', None)

    # Rides the user created (poster)
    created_rides = Ride.objects.filter(rider=user).order_by('-arrivaldate')

    # Rides where user is the assigned driver
    assigned_rides = Ride.objects.filter(driver=user).order_by('-arrivaldate')

    # Rides where user joined as sharer
    joined_rides = Ride.objects.filter(rideshare__sharer=user).distinct().order_by('-arrivaldate')

    # Helpful aggregation: for each created ride we may want total_sharers or available seats
    # (optional) build small map of ride_id -> total_shared_count
    # But template can call r.available_seats (model method) so it's fine.

    context = {
        'profile': profile,
        'created_rides': created_rides,
        'assigned_rides': assigned_rides,
        'joined_rides': joined_rides,
    }
    return render(request, 'rides/my_rides.html', context)
@login_required
def create_ride(request):
    """
    Create a ride:
     - If the creator is a registered driver -> auto-assign + accepted.
     - If the creator is a passenger but checks "drive_self" -> auto-assign and accepted.
     - Otherwise the ride is created unassigned (assignment_status stays ASSIGN_NONE).
    """
    if request.method == 'POST':
        form = RideForm(request.POST)
        drive_self = request.POST.get('drive_self') == 'on'  # checkbox in the form/template

        if form.is_valid():
            ride = form.save(commit=False)
            ride.rider = request.user

            profile = getattr(request.user, 'userprofile', None)
            is_driver_role = (profile and profile.role == UserProfile.ROLE_DRIVER)

            if is_driver_role:
                # creator is a driver - auto assign and accept
                ride.driver = request.user
                ride.assignment_status = Ride.ASSIGN_ACCEPTED
                ride.assigned_at = timezone.now()
                ride.assigned_by = request.user
            elif drive_self:
                # passenger chooses to drive self -> treat as accepted driver
                ride.driver = request.user
                ride.assignment_status = Ride.ASSIGN_ACCEPTED
                ride.assigned_at = timezone.now()
                ride.assigned_by = request.user
            else:
                # leave unassigned -> assignment_status remains ASSIGN_NONE (default)
                ride.driver = None
                ride.assignment_status = Ride.ASSIGN_NONE

            ride.save()
            messages.success(request, "Ride created.")
            return redirect('rides:dashboard')
    else:
        form = RideForm()
    return render(request, 'rides/create_ride.html', {'form': form})

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
            messages.success(request, "Ride updated.")
            return redirect('rides:dashboard')
    else:
        form = RideEditForm(instance=ride)
    return render(request, 'rides/edit_ride.html', {'form': form, 'ride': ride})

@login_required
@require_POST
def delete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id, rider=request.user)
    if ride.status == Ride.STATUS_OPEN:
        ride.delete()
        messages.success(request, "Ride deleted.")
    else:
        messages.error(request, "Only open rides can be deleted.")
    return redirect('rides:dashboard')

# ---------------- Assign / Accept / Reject ----------------
@login_required
def assign_driver(request, ride_id):
    """
    Assign a driver to a ride.
    - If creator assigns themself or the assignee is the creator -> auto-accept.
    - Otherwise assignment becomes PENDING and driver must accept.
    Only ride.rider (creator) or admin can assign.
    """
    ride = get_object_or_404(Ride, id=ride_id)
    if not (request.user == ride.rider or is_admin(request.user)):
        raise PermissionDenied("Only ride creator or admin can assign driver.")

    drivers = UserProfile.objects.filter(role=UserProfile.ROLE_DRIVER).select_related('user')

    if request.method == 'POST':
        driver_id = request.POST.get('driver_id')
        driver_user = get_object_or_404(User, id=driver_id)

        # capacity check
        cap = getattr(driver_user.userprofile, 'capacity', 0) if hasattr(driver_user, 'userprofile') else 0
        if cap < ride.total_committed():
            messages.error(request, f"Driver capacity ({cap}) is less than already committed seats ({ride.total_committed()}).")
            return redirect('rides:assign_driver', ride_id=ride.id)

        # decide auto_accept
        auto_accept = (driver_user == ride.rider) or (driver_user == request.user)
        ride.assign_driver(driver_user, assigned_by=request.user, auto_accept=auto_accept)
        if auto_accept:
            messages.success(request, f"{driver_user.username} assigned and accepted.")
        else:
            messages.success(request, f"{driver_user.username} assigned (pending acceptance).")
        return redirect('rides:dashboard')

    return render(request, 'rides/assign_driver.html', {'ride': ride, 'drivers': drivers})


@login_required
@require_POST
def accept_assignment(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.driver != request.user:
        raise PermissionDenied("Only the assigned driver can accept this assignment.")
    if ride.assignment_status != Ride.ASSIGN_PENDING:
        messages.error(request, "No pending assignment to accept.")
        return redirect('rides:dashboard')

    try:
        ride.accept_assignment(request.user)
        messages.success(request, "You accepted the assignment.")
    except ValidationError as e:
        messages.error(request, str(e))
    return redirect('rides:dashboard')


@login_required
@require_POST
def reject_assignment(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if ride.driver != request.user:
        raise PermissionDenied("Only the assigned driver can reject this assignment.")
    if ride.assignment_status != Ride.ASSIGN_PENDING:
        messages.error(request, "No pending assignment to reject.")
        return redirect('rides:dashboard')

    try:
        ride.reject_assignment(request.user, clear_driver=True)
        messages.success(request, "You rejected the assignment.")
    except ValidationError as e:
        messages.error(request, str(e))
    return redirect('rides:dashboard')


@login_required
@require_POST
def start_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    try:
        ride.start(request.user)
        messages.success(request, "Ride started.")
    except ValidationError as e:
        messages.error(request, str(e))
    return redirect('rides:dashboard')


@login_required
@require_POST
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    try:
        ride.complete(request.user)
        messages.success(request, "Ride completed.")
    except ValidationError as e:
        messages.error(request, str(e))
    return redirect('rides:dashboard')

# ---------------- Sharing (search / join / leave / edit) ----------------
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
                status=Ride.STATUS_OPEN,
                assignment_status=Ride.ASSIGN_ACCEPTED
            ).exclude(rider=request.user)
            return render(request, 'rides/share_results.html', {'rides': rides, 'passenger_count': passenger_count})
    else:
        form = ShareForm()
    return render(request, 'rides/find_rides.html', {'form': form})

@login_required
def join_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    if request.user.userprofile.role == UserProfile.ROLE_DRIVER:
        messages.error(request, "Drivers cannot join rides as sharers. Switch role to Passenger to join.")
        return redirect('rides:dashboard')

    if request.method == 'POST':
        try:
            passenger_count = int(request.POST.get('passenger_count', 1))
        except (TypeError, ValueError):
            messages.error(request, "Invalid passenger count.")
            return redirect('rides:dashboard')
        ok, msg = ride.join_or_update_share(request.user, passenger_count)
        if ok:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return redirect('rides:dashboard')
    return render(request, 'rides/join_ride.html', {'ride': ride})

@login_required
@require_POST
def leave_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    ok, msg = ride.leave_share(request.user), "You left the ride."
    messages.success(request, msg)
    return redirect('rides:dashboard')

@login_required
def edit_share(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    share = get_object_or_404(RideShare, ride=ride, sharer=request.user)
    if request.method == 'POST':
        form = ShareEditForm(request.POST, instance=share)
        if form.is_valid():
            new_count = form.cleaned_data['passenger_count']
            ok, msg = ride.update_share(request.user, new_count)
            if ok:
                messages.success(request, msg)
                return redirect('rides:dashboard')
            else:
                messages.error(request, msg)
        else:
            messages.error(request, "Please fix the errors.")
    else:
        form = ShareEditForm(instance=share)
    return render(request, 'rides/edit_share.html', {'form': form, 'ride': ride})

# ---------------- Ride detail ----------------
@login_required
def ride_detail(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    return render(request, 'rides/ride_detail.html', {'ride': ride})

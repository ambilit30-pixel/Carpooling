
from django.db import models, transaction, IntegrityError
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

class UserProfile(models.Model):
    ROLE_DRIVER = 'driver'
    ROLE_USER = 'user'
    ROLE_CHOICES = [(ROLE_DRIVER, 'Driver'), (ROLE_USER, 'Passenger')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_USER)
    contact = models.CharField(max_length=30, blank=True)

    # driver-specific
    vehicle = models.CharField(max_length=80, blank=True)
    plate = models.CharField(max_length=30, blank=True)
    capacity = models.PositiveIntegerField(default=0)  # seats in vehicle
    special = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, role=UserProfile.ROLE_USER)



class Ride(models.Model):
    STATUS_OPEN = 'open'
    STATUS_DRIVING = 'driving'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_DRIVING, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    # --- assignment states ---
    ASSIGN_NONE = 'none'        # no driver assigned yet
    ASSIGN_PENDING = 'pending'  # driver assigned, awaiting driver's acceptance
    ASSIGN_ACCEPTED = 'accepted'#
    ASSIGN_REJECTED = 'rejected'
    ASSIGN_CHOICES = [
        (ASSIGN_NONE, 'No driver'),
        (ASSIGN_PENDING, 'Pending'),
        (ASSIGN_ACCEPTED, 'Accepted'),
        (ASSIGN_REJECTED, 'Rejected'),
    ]

    rider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rides')  # creator
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='driven_rides')
    source = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    arrivaldate = models.DateTimeField()
    passenger = models.PositiveIntegerField(default=1)  # seats reserved by creator
    sharable = models.BooleanField(default=False)
    special = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    # use ASSIGN_NONE as default when created with no driver
    assignment_status = models.CharField(
        max_length=20,
        choices=ASSIGN_CHOICES,
        default=ASSIGN_NONE
    )

    assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assignments_made')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-arrivaldate', '-created_at']

    def __str__(self):
        return f"{self.source} → {self.destination} on {self.arrivaldate.strftime('%Y-%m-%d %H:%M')}"

    def available_seats(self):
        """
        Returns:
          - integer >= 0: seats available
          - None: seats unknown (no driver or capacity not set)
        """
        if not self.driver or not hasattr(self.driver, 'userprofile'):
            return None
        cap = getattr(self.driver.userprofile, 'capacity', None)
        try:
            cap = int(cap) if cap is not None else None
        except (TypeError, ValueError):
            cap = None
        if not cap or cap <= 0:
            return None
        shared = self.rideshare_set.aggregate(total=Sum('passenger_count'))['total'] or 0
        seats_left = cap - (self.passenger or 0) - shared
        return max(seats_left, 0)

    def total_committed(self):
        """creator seats + sum of sharers"""
        shared = self.rideshare_set.aggregate(total=Sum('passenger_count'))['total'] or 0
        return (self.passenger or 0) + shared

    def assign_driver(self, user, assigned_by=None, auto_accept=False):
        """
        Assign driver. If auto_accept True, assignment_status becomes ACCEPTED.
        Otherwise set to PENDING.
        """
        self.driver = user
        self.assigned_at = timezone.now()
        self.assigned_by = assigned_by
        if auto_accept:
            self.assignment_status = self.ASSIGN_ACCEPTED
        else:
            self.assignment_status = self.ASSIGN_PENDING
        self.save(update_fields=['driver', 'assignment_status', 'assigned_at', 'assigned_by', 'updated_at'])

    def accept_assignment(self, user):
        """Driver accepts - ensure user is assigned driver and capacity allows current committed seats."""
        if self.driver_id != user.id:
            raise ValidationError("Only the assigned driver can accept.")
        cap = getattr(user.userprofile, 'capacity', None) if hasattr(user, 'userprofile') else None
        try:
            cap = int(cap or 0)
        except (TypeError, ValueError):
            cap = 0
        committed = self.total_committed()
        if cap < committed:
            raise ValidationError("Your vehicle capacity (%d) is less than currently committed seats (%d)." % (cap, committed))
        self.assignment_status = self.ASSIGN_ACCEPTED
        self.save(update_fields=['assignment_status', 'updated_at'])

    def reject_assignment(self, user, clear_driver=True):
        """Driver rejects. By default clear driver field so ride becomes unassigned."""
        if self.driver_id != user.id:
            raise ValidationError("Only the assigned driver can reject.")
        if clear_driver:
            self.driver = None
            self.assignment_status = self.ASSIGN_REJECTED
            self.assigned_at = None
            self.assigned_by = None
            self.save(update_fields=['driver', 'assignment_status', 'assigned_at', 'assigned_by', 'updated_at'])
        else:
            self.assignment_status = self.ASSIGN_REJECTED
            self.save(update_fields=['assignment_status', 'updated_at'])

    def start(self, user):
        """Start ride - only assigned & accepted driver can start."""
        if not self.driver_id or self.driver_id != user.id:
            raise ValidationError("Only the assigned driver can start the ride.")
        if self.assignment_status != self.ASSIGN_ACCEPTED:
            raise ValidationError("Assignment must be accepted before starting.")
        if self.status != self.STATUS_OPEN:
            raise ValidationError("Ride cannot be started.")
        self.status = self.STATUS_DRIVING
        self.save(update_fields=['status', 'updated_at'])

    def complete(self, user):
        if not self.driver_id or self.driver_id != user.id:
            raise ValidationError("Only the assigned driver can complete the ride.")
        if self.status != self.STATUS_DRIVING:
            raise ValidationError("Ride is not in progress.")
        self.status = self.STATUS_COMPLETED
        self.save(update_fields=['status', 'updated_at'])

    # share helpers remain the same (transactional)
    def join_or_update_share(self, user, passenger_count):
        # unchanged from your version (keeps transactional logic)
        if passenger_count <= 0:
            return False, "Passenger count must be at least 1."
        if not self.sharable or self.status != self.STATUS_OPEN:
            return False, "This ride is not available for sharing."
        if not self.driver or self.assignment_status != self.ASSIGN_ACCEPTED:
            return False, "Driver must be assigned and accepted before joining."

        try:
            with transaction.atomic():
                locked = Ride.objects.select_for_update().get(id=self.id)
                existing = locked.rideshare_set.filter(sharer=user).first()
                existing_count = existing.passenger_count if existing else 0
                available = (locked.available_seats() or 0) + existing_count
                if passenger_count > available:
                    return False, "Not enough available seats."
                if existing:
                    existing.passenger_count = passenger_count
                    existing.save(update_fields=['passenger_count'])
                else:
                    RideShare.objects.create(ride=locked, sharer=user, passenger_count=passenger_count)
        except IntegrityError:
            return False, "Could not join due to concurrency. Try again."
        return True, "Joined ride."

    def leave_share(self, user):
        self.rideshare_set.filter(sharer=user).delete()
        return True, "Left the ride."

    def update_share(self, user, new_count):
        if new_count <= 0:
            return False, "Passenger count must be at least 1."
        share = self.rideshare_set.filter(sharer=user).first()
        if not share:
            return False, "No existing share to update."
        try:
            with transaction.atomic():
                locked = Ride.objects.select_for_update().get(id=self.id)
                available = (locked.available_seats() or 0) + share.passenger_count
                if new_count > available:
                    return False, "Not enough available seats for this update."
                share.passenger_count = new_count
                share.save(update_fields=['passenger_count'])
        except IntegrityError:
            return False, "Could not update due to concurrency. Try again."
        return True, "Share updated."


class RideShare(models.Model):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    sharer = models.ForeignKey(User, on_delete=models.CASCADE)
    passenger_count = models.PositiveIntegerField(default=1)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ride', 'sharer')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.sharer.username} shares Ride {self.ride.id} ({self.passenger_count})"

class RideRating(models.Model):
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE)
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    ratee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating = models.PositiveSmallIntegerField(default=5)
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

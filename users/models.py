from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

# ---------------------- UserProfile ----------------------
class UserProfile(models.Model):
    ROLE_DRIVER = 'driver'
    ROLE_USER = 'user'
    ROLE_CHOICES = [
        (ROLE_DRIVER, 'Driver'),
        (ROLE_USER, 'Passenger/User'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_USER)
    contact = models.CharField(max_length=20, blank=True)

    # Driver-specific
    vehicle = models.CharField(max_length=50, blank=True)
    plate = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    special = models.CharField(max_length=100, blank=True)  # e.g., AC, pet-friendly

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

# ensure profile created automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, role=UserProfile.ROLE_USER)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # in case of updates
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance, role=UserProfile.ROLE_USER)

# ---------------------- Ride ----------------------
class Ride(models.Model):
    STATUS_OPEN = 'open'
    STATUS_DRIVING = 'driving'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_DRIVING, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    rider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rides')  # creator of ride
    driver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='driven_rides')
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    arrivaldate = models.DateTimeField()  # store timezone-aware times (USE_TZ=True)
    passenger = models.PositiveIntegerField(default=1)  # seats reserved by creator
    sharable = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    special = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-arrivaldate', '-created_at']

    def __str__(self):
        return f"{self.source} → {self.destination} on {self.arrivaldate.strftime('%Y-%m-%d %H:%M')}"

    def driver_capacity(self):
        if self.driver and hasattr(self.driver, 'userprofile'):
            return self.driver.userprofile.capacity
        return 0

    def shared_passengers(self):
        total = self.rideshare_set.aggregate(total=Sum('passenger_count'))['total']
        return total or 0

    def available_seats(self):
        """
        seats left for new sharers (not counting the creator's passenger seats).
        Formula: driver.capacity - passenger(reserved by creator) - sum(RideShare.passenger_count)
        Returns non-negative int.
        """
        capacity = self.driver_capacity()
        seats_left = capacity - self.passenger - self.shared_passengers()
        return max(seats_left, 0)

    # business actions encapsulated
    def assign_driver(self, user):
        self.driver = user
        self.save(update_fields=['driver', 'updated_at'])

    def start(self):
        if self.status != Ride.STATUS_OPEN:
            raise ValueError("Ride is not open to start.")
        self.status = Ride.STATUS_DRIVING
        self.save(update_fields=['status', 'updated_at'])

    def complete(self):
        if self.status != Ride.STATUS_DRIVING:
            raise ValueError("Ride is not in progress.")
        self.status = Ride.STATUS_COMPLETED
        self.save(update_fields=['status', 'updated_at'])

# ---------------------- RideShare ----------------------
class RideShare(models.Model):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    sharer = models.ForeignKey(User, on_delete=models.CASCADE)
    passenger_count = models.PositiveIntegerField(default=1)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('ride', 'sharer')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.sharer.username} shares Ride {self.ride.id} ({self.passenger_count} seats)"

# ---------------------- RideRating ----------------------
class RideRating(models.Model):
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE)
    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    ratee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating = models.PositiveSmallIntegerField(default=5)  # 1 to 5
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rater.username} rated {self.ratee.username}: {self.rating}/5"

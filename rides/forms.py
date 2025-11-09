from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import UserProfile, Ride, RideShare

class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    # ✅ Add role selection
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Register as")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username already exists")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("Email already in use")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            # ✅ Update or create profile with chosen role
            role = self.cleaned_data.get('role', UserProfile.ROLE_USER)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
        return user

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class EditInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput, label="Old password")
    new_password1 = forms.CharField(widget=forms.PasswordInput, label="New password")
    new_password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm new password")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1')
        p2 = cleaned.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError("New passwords do not match")
        return cleaned

class DriverForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['contact', 'vehicle', 'plate', 'capacity', 'special']
        widgets = {
            'contact': forms.TextInput(attrs={'placeholder': 'Phone or WhatsApp number', 'class': 'field-input', 'type': 'tel'}),
            'vehicle': forms.TextInput(attrs={'placeholder': 'e.g. Toyota Innova', 'class': 'field-input'}),
            'plate': forms.TextInput(attrs={'placeholder': 'KA-01-AB-1234', 'class': 'field-input'}),
            'capacity': forms.NumberInput(attrs={'min': '1', 'class': 'field-input'}),
            'special': forms.Textarea(attrs={'placeholder': 'Any special notes (optional)', 'class': 'field-input'}),
        }

    def clean_capacity(self):
        cap = self.cleaned_data.get('capacity')
        if cap is None or cap <= 0:
            raise ValidationError("Please enter a positive seat capacity for your vehicle.")
        return cap

class RideForm(forms.ModelForm):
    arrivaldate = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    class Meta:
        model = Ride
        fields = ['source', 'destination', 'arrivaldate', 'passenger', 'sharable', 'special']

    def clean_arrivaldate(self):
        dt = self.cleaned_data['arrivaldate']
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        if dt < timezone.now():
            raise ValidationError("Arrival time must be in the future.")
        return dt

class RideEditForm(RideForm):
    class Meta(RideForm.Meta):
        pass

class ShareForm(forms.Form):
    destination = forms.CharField(max_length=200)
    earlyarrival = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    latearrival = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    passenger = forms.IntegerField(min_value=1)

    def clean(self):
        cleaned = super().clean()
        early = cleaned.get('earlyarrival')
        late = cleaned.get('latearrival')
        if early and late:
            if timezone.is_naive(early):
                early = timezone.make_aware(early, timezone.get_current_timezone())
            if timezone.is_naive(late):
                late = timezone.make_aware(late, timezone.get_current_timezone())
            if early > late:
                raise ValidationError("Early arrival cannot be after late arrival")
            cleaned['earlyarrival'] = early 
            cleaned['latearrival'] = late
        return cleaned

class ShareEditForm(forms.ModelForm):
    class Meta:
        model = RideShare
        fields = ['passenger_count']

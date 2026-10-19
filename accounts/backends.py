from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameBackend(ModelBackend):
    """Lets users log in with their username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        field = 'email__iexact' if '@' in username else 'username__iexact'
        try:
            user = User.objects.get(**{field: username})
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)  # equalise timing
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

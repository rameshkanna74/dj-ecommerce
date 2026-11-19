from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    """Authenticate with either the username or the (case-insensitive) email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user_model = get_user_model()
        lookup = {"email__iexact": username} if "@" in username else {"username": username}
        try:
            user = user_model._default_manager.get(**lookup)
        except (user_model.DoesNotExist, user_model.MultipleObjectsReturned):
            # Run the hasher anyway to reduce timing differences between cases.
            user_model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

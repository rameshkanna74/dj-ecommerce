from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class UsernameOrEmailBackend(ModelBackend):
    """Authenticate with either the username or the (case-insensitive) email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        user_model = get_user_model()
        manager = user_model._default_manager
        # Usernames may legally contain "@", so an exact username match wins over an email match.
        user = manager.filter(username=username).first()
        if user is None and "@" in username:
            matches = list(manager.filter(email__iexact=username)[:2])
            user = matches[0] if len(matches) == 1 else None
        if user is None:
            # Run the hasher anyway to reduce timing differences between cases.
            user_model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

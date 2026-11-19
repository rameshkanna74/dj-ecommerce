from django.utils.cache import patch_cache_control, patch_vary_headers


class PublicCacheMixin:
    """
    Let browsers/CDNs cache anonymous GET responses of public endpoints briefly.
    Authenticated responses stay private. Combined with ConditionalGetMiddleware
    (ETag), clients can also revalidate with a cheap 304.
    """

    public_cache_seconds = 60

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.method in ("GET", "HEAD") and response.status_code == 200:
            if request.user.is_authenticated:
                patch_cache_control(response, private=True, no_cache=True)
            else:
                patch_cache_control(response, public=True, max_age=self.public_cache_seconds)
            patch_vary_headers(response, ["Authorization", "Cookie"])
        return response

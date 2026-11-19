from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.template.defaultfilters import filesizeformat

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "gif"]

validate_image_extension = FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)


def validate_image_size(file):
    """Reject uploaded images larger than ``CORECART_MAX_IMAGE_SIZE`` bytes."""
    limit = getattr(settings, "CORECART_MAX_IMAGE_SIZE", 2 * 1024 * 1024)
    size = getattr(file, "size", 0) or 0
    if size > limit:
        raise ValidationError(
            "Image is too large (%(size)s). The maximum size is %(limit)s.",
            code="file_too_large",
            params={"size": filesizeformat(size), "limit": filesizeformat(limit)},
        )


IMAGE_VALIDATORS = [validate_image_extension, validate_image_size]

from django.forms.renderers import TemplatesSetting


class CoreFormRenderer(TemplatesSetting):
    """Renders every ``{{ field.as_field_group }}`` with the shared field template."""

    field_template_name = "includes/form_field.html"

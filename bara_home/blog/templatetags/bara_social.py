from django import template

from blog.social import SOCIAL_PROFILES

register = template.Library()


@register.simple_tag
def bara_social_profiles():
    return SOCIAL_PROFILES.values()

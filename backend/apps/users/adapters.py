from allauth.headless.adapter import DefaultHeadlessAdapter


class CustomHeadlessAdapter(DefaultHeadlessAdapter):
    def serialize_user(self, user):
        data = super().serialize_user(user)
        data["is_staff"] = user.is_staff
        data["is_superuser"] = user.is_superuser
        data["display_name"] = user.get_full_name() or user.get_username()
        return data

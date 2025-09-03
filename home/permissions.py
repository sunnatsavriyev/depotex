from rest_framework.permissions import BasePermission, SAFE_METHODS

class CustomPermission(BasePermission):
    """
    Superuser va Texniklar CRUD qilishi mumkin.
    Monitoring faqat o'qishi mumkin.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # Superuser har narsaga ruxsat
        if user.is_superuser:
            return True

        # Texnik har narsaga ruxsat (CRUD)
        if user.role == "texnik":
            return True

        # Monitoring faqat o'qishi mumkin
        if user.role == "monitoring":
            return request.method in SAFE_METHODS

        # Boshqa holatlarda ruxsat yo'q
        return False



class IsOwnerOrReadOnly(BasePermission):
    """
    Foydalanuvchi faqat o‘z yozuvini update/delete qilishi mumkin,
    lekin boshqalarni faqat o‘qiy oladi.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:  # GET, HEAD, OPTIONS
            return True
        return obj.created_by == request.user
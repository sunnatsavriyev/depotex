from rest_framework.permissions import BasePermission, SAFE_METHODS



class IsTexnik(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user 
            and user.is_authenticated 
            and (user.is_superuser or user.role == "texnik")  
        )


class IsSkladchiOrReadOnly(BasePermission):
    """
    Faqat skladchi yoki superuser yozuv yaratish/tahrirlash/o‘chirish huquqiga ega.
    Boshqalar faqat o‘qiy oladi (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        # Har kim ko‘ra oladi
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        # CRUD faqat skladchi yoki superuserga ruxsat
        return (
            request.user.is_authenticated and
            (request.user.is_superuser or request.user.role == "skladchi")
        ) 


class IsMonitoringReadOnly(BasePermission):
    """
    Monitoring faqat SAFE_METHODS (GET, HEAD, OPTIONS) ishlata oladi.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role == "monitoring":
            return request.method in SAFE_METHODS
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
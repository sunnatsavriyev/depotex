from rest_framework.permissions import BasePermission, SAFE_METHODS



class IsTexnik(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user 
            and user.is_authenticated 
            and (user.is_superuser or user.role == "texnik")  
        )

class IsJadvalchi(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user 
            and user.is_authenticated 
            and (user.is_superuser or user.role == "jadval")  
        )


class IsMonitoringReadOnly(BasePermission):
    """
    Faqat monitoring roli yoki superuser foydalanuvchilarga 
    GET, HEAD, OPTIONS metodlariga ruxsat beradi.
    Boshqa metodlarga (POST, PUT, DELETE) ruxsat yo‘q.
    """
    def has_permission(self, request, view):
        user = request.user
        return (
            user
            and user.is_authenticated
            and (user.is_superuser or user.role == "monitoring")
            and request.method in SAFE_METHODS
        )
    

class IsOwnerOrReadOnly(BasePermission):
    """
    Foydalanuvchi faqat o‘z yozuvini update/delete qilishi mumkin,
    lekin boshqalarni faqat o‘qiy oladi.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:  # GET, HEAD, OPTIONS
            return True
        return obj.created_by == request.user
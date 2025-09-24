from rest_framework.permissions import BasePermission, SAFE_METHODS



class IsTexnik(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user 
            and user.is_authenticated 
            and (user.is_superuser or user.role == "texnik")  
        )


class IsSkladchi(BasePermission):
    """
    Faqat Skladchi foydalanuvchilar CRUD qila oladi.
    """
    def has_permission(self, request, view):
        user = request.user
        return user and user.is_authenticated and (user.is_superuser or user.role == "skladchi") 


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
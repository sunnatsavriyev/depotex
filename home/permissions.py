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
    Skladchi: Ehtiyot qismlar bo‘yicha CRUD huquqi.
    Monitoring va boshqalar: faqat GET ko‘rish (lekin faqat login bo‘lsa).
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Monitoring faqat o‘qiy oladi
        if user.role == "monitoring":
            return request.method in SAFE_METHODS

        # Skladchi CRUD huquqiga ega faqat EhtiyotQism uchun
        if user.role == "skladchi":
            return True  # CRUD allowed in this view only

        # Superuser har doim ruxsatli
        if user.is_superuser:
            return True

        # Texnik faqat o‘qiy oladi (masalan, ehtiyot qismlar ro‘yxatini ko‘rish uchun)
        if user.role == "texnik":
            return request.method in SAFE_METHODS

        return False


class IsMonitoringReadOnly(BasePermission):
    """
    Monitoring: barcha endpointlarda faqat GET, HEAD, OPTIONS.
    Boshqalar: bu klassni o‘tgan holda ruxsat yo‘q.
    """
    def has_permission(self, request, view):
        user = request.user
        return (
            user
            and user.is_authenticated
            and user.role == "monitoring"
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
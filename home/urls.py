from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TamirTuriViewSet, ElektroDepoViewSet,
    EhtiyotQismlariViewSet, HarakatTarkibiViewSet,
    TexnikKorikViewSet, UserViewSet, NosozliklarViewSet,
    get_me
)

router = DefaultRouter()
router.register(r"tamir-turi", TamirTuriViewSet)
router.register(r"elektro-depo", ElektroDepoViewSet)
router.register(r"ehtiyot-qismlari", EhtiyotQismlariViewSet)
router.register(r"harakat-tarkibi", HarakatTarkibiViewSet)
router.register(r"nosozliklar", NosozliklarViewSet)
router.register(r'texnik-korik', TexnikKorikViewSet, basename='texnik-korik')
urlpatterns = [
    path("users/", UserViewSet.as_view({"get": "list", "post": "create"})),  
    path("", include(router.urls)),
    path('me/', get_me, name='get_me'),
]

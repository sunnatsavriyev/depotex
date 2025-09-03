from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TamirTuriViewSet, ElektroDepoViewSet,
    EhtiyotQismlariViewSet, HarakatTarkibiViewSet,
    TexnikKorikViewSet, UserViewSet, NosozliklarViewSet
)

router = DefaultRouter()
router.register(r"tamir-turi", TamirTuriViewSet)
router.register(r"elektro-depo", ElektroDepoViewSet)
router.register(r"ehtiyot-qismlari", EhtiyotQismlariViewSet)
router.register(r"harakat-tarkibi", HarakatTarkibiViewSet)
router.register(r"texnik-korik", TexnikKorikViewSet)
router.register(r"nosozliklar", NosozliklarViewSet)

urlpatterns = [
    path("users/", UserViewSet.as_view({"get": "list", "post": "create"})),  
    path("", include(router.urls)),
    
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import (
    TamirTuriViewSet, ElektroDepoViewSet,
    EhtiyotQismlariViewSet, HarakatTarkibiViewSet,
    TexnikKorikViewSet, UserViewSet, NosozliklarViewSet,
    HarakatTarkibiGetViewSet, NosozliklarGetViewSet,
    TexnikKorikGetViewSet, TexnikKorikStepViewSet,NosozlikStepViewSet,
    get_me
)

# 🔹 Main router
router = DefaultRouter()
router.register(r"tamir-turi", TamirTuriViewSet)
router.register(r"elektro-depo", ElektroDepoViewSet)
router.register(r"ehtiyot-qismlari", EhtiyotQismlariViewSet)
router.register(r"harakat-tarkibi", HarakatTarkibiViewSet)
router.register(r"nosozliklar", NosozliklarViewSet)
router.register(r"texnik-korik", TexnikKorikViewSet, basename="texnik-korik")

# 🔹 Nested router (steps uchun)
korik_router = routers.NestedDefaultRouter(router, r"texnik-korik", lookup="korik")
korik_router.register(r"steps", TexnikKorikStepViewSet, basename="texnik-korik-steps")

# 🔹 Nested router (steps uchun)
nosozlik_router = routers.NestedDefaultRouter(router, r"nosozliklar", lookup="nosozlik")
nosozlik_router.register(r"steps", NosozlikStepViewSet, basename="nosozlik-steps")



urlpatterns = [
    path("users/", UserViewSet.as_view({"get": "list", "post": "create"})),  
    path("", include(router.urls)),           # asosiy router
    path("", include(korik_router.urls)),    # nested router (steps)
    path("", include(nosozlik_router.urls)),
    path("me/", get_me, name="get_me"),
    path("harakat-tarkibi-get/", HarakatTarkibiGetViewSet.as_view({"get": "list"}), name="harakat-tarkibi-get"),
    path("nosozliklar-get/", NosozliklarGetViewSet.as_view({"get": "list"}), name="nosozliklar-get"),
    path("texnik-korik-get/", TexnikKorikGetViewSet.as_view({"get": "list"}), name="texnik-korik-get"),
]

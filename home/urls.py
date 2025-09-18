from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TamirTuriViewSet, ElektroDepoViewSet,
    EhtiyotQismlariViewSet, HarakatTarkibiViewSet,
    TexnikKorikViewSet, UserViewSet, NosozliklarViewSet,
    HarakatTarkibiGetViewSet, NosozliklarGetViewSet,
    TexnikKorikGetViewSet, TexnikKorikStepViewSet,
    NosozlikStepViewSet, KorikNosozlikStatisticsView,
    KunlikYurishViewSet, get_me
)

# 🔹 Main router
router = DefaultRouter()
router.register(r"tamir-turi", TamirTuriViewSet)
router.register(r"elektro-depo", ElektroDepoViewSet)
router.register(r"ehtiyot-qismlari", EhtiyotQismlariViewSet)
router.register(r"harakat-tarkibi", HarakatTarkibiViewSet)
router.register(r"nosozliklar", NosozliklarViewSet)
router.register(r"texnik-korik", TexnikKorikViewSet, basename="texnik-korik")
router.register(r"kunlik-yurish", KunlikYurishViewSet, basename="kunlik-yurish")

# 🔹 Steps end-pointlarini alohida ro‘yxatdan o‘tkazamiz (nested emas)
router.register(r"texnik-korik-steps", TexnikKorikStepViewSet, basename="texnik-korik-steps")
router.register(r"nosozlik-steps", NosozlikStepViewSet, basename="nosozlik-steps")

urlpatterns = [
    path("korik-nosozlik/", KorikNosozlikStatisticsView.as_view(), name="korik-nosozlik-statistics"),
    path("users/", UserViewSet.as_view({"get": "list", "post": "create"})),
    path("", include(router.urls)),  # faqat bitta router, nested yo‘q
    path("me/", get_me, name="get_me"),
    path("harakat-tarkibi-get/", HarakatTarkibiGetViewSet.as_view({"get": "list"}), name="harakat-tarkibi-get"),
    path("nosozliklar-get/", NosozliklarGetViewSet.as_view({"get": "list"}), name="nosozliklar-get"),
    path("texnik-korik-get/", TexnikKorikGetViewSet.as_view({"get": "list"}), name="texnik-korik-get"),
]

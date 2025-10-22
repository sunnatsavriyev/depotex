from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import (
    TamirTuriViewSet, ElektroDepoViewSet,
    EhtiyotQismlariViewSet, HarakatTarkibiViewSet,
    TexnikKorikViewSet, UserViewSet, NosozliklarViewSet,
    HarakatTarkibiGetViewSet, NosozliklarGetViewSet,
    TexnikKorikGetViewSet, TexnikKorikStepViewSet,NosozlikStepViewSet,KorikNosozlikStatisticsView,
    KunlikYurishViewSet,HarakatTarkibiActiveViewSet,EhtiyotQismMiqdorListAPIView,EhtiyotQismMiqdorCreateAPIView,TarkibDetailViewSet,KunlikYurishHistoryAPIView,
    get_me,NosozlikTuriViewSet,NosozlikNotificationViewSet,TexnikKorikJadvalViewSet,HarakatTarkibiHolatStatistikaViewSet,
    TexnikKorikByTypeViewSet,TexnikKorikStepViewSet1,NosozliklarPDFExportView,NosozlikStepViewSet1,NotificationViewSet,
)
routers
router = DefaultRouter()
router.register(r"tamir-turi", TamirTuriViewSet)
router.register(r"elektro-depo", ElektroDepoViewSet)
router.register(r"ehtiyot-qismlari", EhtiyotQismlariViewSet)
router.register(r"harakat-tarkibi", HarakatTarkibiViewSet)
router.register(r"nosozliklar", NosozliklarViewSet)
router.register(r"nosozliklar-export-bytarkib", NosozliklarPDFExportView, basename="nosozliklar-export-bytarkib")
router.register(r"nosozliklar-get1", NosozlikStepViewSet1, basename="nosozliklar-get1")
router.register(r"texnik-korik", TexnikKorikViewSet, basename="texnik-korik")
router.register(r"kunlik-yurish", KunlikYurishViewSet, basename="kunlik-yurish")
router.register(r'tarkib-detail', TarkibDetailViewSet, basename='tarkib-detail')
router.register(r'texnik-korik-bytype', TexnikKorikByTypeViewSet, basename='texnik-korik-bytype')
router.register(r'texnik-korik-step1', TexnikKorikStepViewSet1, basename='texnik-korik-step')
router.register(r'nosozlik-turlari', NosozlikTuriViewSet, basename='nosozlik-turi')
router.register(r"texnik-korik-steps", TexnikKorikStepViewSet, basename="texnik-korik-steps")
router.register(r"nosozlik-steps", NosozlikStepViewSet, basename="nosozlik-steps")
router.register(r"texnik-korik-jadval", TexnikKorikJadvalViewSet, basename="texnik-korik-jadval")
router.register(
    r'harakat-tarkibi-holat-statistika',
    HarakatTarkibiHolatStatistikaViewSet,
    basename='harakat-tarkibi-holat-statistika'
)
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'nosozlik_notifications', NosozlikNotificationViewSet, basename='nosozlik_notifications')



urlpatterns = [
    path("korik-nosozlik/", KorikNosozlikStatisticsView.as_view(), name="korik-nosozlik-statistics"),
    path("users/", UserViewSet.as_view({"get": "list", "post": "create"})),  
    path("", include(router.urls)), 
    path("me/", get_me, name="get_me"),
    path("harakat-tarkibi-get/", HarakatTarkibiGetViewSet.as_view({"get": "list"}), name="harakat-tarkibi-get"),
    path(
        "harakat-tarkibi-active/",
        HarakatTarkibiActiveViewSet.as_view({"get": "list"}),
        name="harakat-tarkibi-active-list",
    ),
    
    path(
        "ehtiyot-qismlari/<int:ehtiyotqism_pk>/miqdorlar/",
        EhtiyotQismMiqdorListAPIView.as_view(),
        name="ehtiyotqism-miqdorlar-list"
    ),
    path(
        "ehtiyot-qismlari/<int:ehtiyotqism_pk>/add-miqdor/",
        EhtiyotQismMiqdorCreateAPIView.as_view(),
        name="ehtiyotqism-miqdorlar-create"
    ),
    path(
        "kunlik-yurish-history/<int:tarkib_id>/",
        KunlikYurishHistoryAPIView.as_view(),
        name="kunlik-yurish-history"
    ),
    path("nosozliklar-get/", NosozliklarGetViewSet.as_view({"get": "list"}), name="nosozliklar-get"),
    path("texnik-korik-get/", TexnikKorikGetViewSet.as_view({"get": "list"}), name="texnik-korik-get"),
]

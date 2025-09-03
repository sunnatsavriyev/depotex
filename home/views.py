from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from .models import (
    TamirTuri, ElektroDepo, EhtiyotQismlari,
    HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar
)
from .serializers import (
    TamirTuriSerializer, ElektroDepoSerializer,
    EhtiyotQismlariSerializer, HarakatTarkibiSerializer,
    TexnikKorikSerializer, UserSerializer, NosozliklarSerializer
)
from .permissions import CustomPermission
from django.contrib.auth import authenticate
from .pagination import CustomPagination
from django_filters.rest_framework import DjangoFilterBackend


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = []  # har bir child ViewSet da override qilinadi
    ordering_fields = "__all__"

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        # Faqat require_login_fields = True bo'lsa tekshiramiz
        if getattr(self, "require_login_fields", False):
            username = request.data.get("username")
            password = request.data.get("password")

            if not username or not password:
                return Response(
                    {"detail": "Username va parol talab qilinadi."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = authenticate(username=username, password=password)
            if not user:
                return Response(
                    {"detail": "Username yoki parol xato."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # request.user ni serializerga yuborish
            context = {"request": request}
        else:
            context = {"request": request}  # boshqa viewlar uchun oddiy context

        serializer = self.get_serializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{self.basename}.pdf"'

        p = canvas.Canvas(response)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, 800, f"{self.basename} ro'yxati:")

        y = 780
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        for obj in serializer.data:
            for key, value in obj.items():
                p.setFont("Helvetica", 11)
                p.drawString(100, y, f"{key}: {value}")
                y -= 15
                if y < 50:
                    p.showPage()
                    y = 800
                    p.setFont("Helvetica-Bold", 14)
                    p.drawString(100, 820, f"{self.basename} ro'yxati (davomi):")
            y -= 10

        p.showPage()
        p.save()
        return response

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        wb = Workbook()
        ws = wb.active
        ws.title = self.basename

        # dict_keys -> list ga aylantirish
        headers = list(serializer.data[0].keys()) if serializer.data else []
        ws.append(headers)

        for obj in serializer.data:
            ws.append([obj.get(h) for h in headers])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{self.basename}.xlsx"'
        wb.save(response)
        return response

class TamirTuriViewSet(BaseViewSet):
    queryset = TamirTuri.objects.all()
    serializer_class = TamirTuriSerializer
    basename = "Tamir Turi"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['tamir_nomi', 'tamirlash_davri', 'tamirlanish_vaqti']   
    ordering_fields = ['tamirlanish_vaqti', 'id']

class ElektroDepoViewSet(BaseViewSet):
    queryset = ElektroDepo.objects.all()
    serializer_class = ElektroDepoSerializer
    basename = "Elektro Depo"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['depo_nomi', 'qisqacha_nomi', 'joylashuvi']   
    ordering_fields = ['qisqacha_nomi', 'id']

class EhtiyotQismlariViewSet(BaseViewSet):
    queryset = EhtiyotQismlari.objects.all()
    serializer_class = EhtiyotQismlariSerializer
    basename = "Ehtiyot Qismlari"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['ehtiyotqism_nomi', 'nomenklatura_raqami']   
    ordering_fields = ['nomenklatura_raqami', 'id']

class HarakatTarkibiViewSet(BaseViewSet):
    queryset = HarakatTarkibi.objects.all()
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi','tarkib_raqami','turi','ishga_tushgan_vaqti','eksplutatsiya_vaqti']   
    ordering_fields = ['ishga_tushgan_vaqti', 'id']

class TexnikKorikViewSet(BaseViewSet):
    queryset = TexnikKorik.objects.all()
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['tamir_nomi','ehtiyotqism_nomi','tarkib_raqami']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"detail": "Username va parol talab qilinadi."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Username yoki parol xato."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NosozliklarViewSet(BaseViewSet):
    queryset = Nosozliklar.objects.all()
    serializer_class = NosozliklarSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['tamir_nomi','ehtiyotqism_nomi','tarkib_raqami']

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"detail": "Username va parol talab qilinadi."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"detail": "Username yoki parol xato."},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

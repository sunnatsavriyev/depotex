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
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes, action
from reportlab.lib import colors
class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_me(request):
    user = request.user
    
    # Headerdan tokenni olish
    auth_header = request.headers.get("Authorization", None)
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    return Response({
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "token": token,  
    })


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = []  
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

            context = {"request": request}
        else:
            context = {"request": request}  

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
        p.setFillColor(colors.darkblue)  # sarlavha rangini o'zgartirish
        p.drawString(100, 800, f"{self.basename} ro'yxati:")

        y = 780
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Serializer data ni o'zgartirish: kalitlarni o'zbekchaga aylantirish
        data = []
        for obj in serializer.data:
            new_obj = {}
            for key, value in obj.items():
                if key == "created_by":
                    new_obj["Yaratdi"] = value
                elif key == "created_at":
                    new_obj["Yaratilgan vaqti"] = value
                elif key == "eksplutatsiya_vaqti":
                    new_obj["Eksplutatsiya masofasi(km)"] = value 
                else:
                    new_obj[key] = value
            data.append(new_obj)

        for obj in data:
            for key, value in obj.items():
                # Kalit (nom) rangini o'zgartirish
                p.setFont("Helvetica-Bold", 11)
                p.setFillColor(colors.blue)  
                p.drawString(100, y, f"{key}:")
                
                # Qiymatni qora rangda yozish
                p.setFont("Helvetica", 11)
                p.setFillColor(colors.black)
                p.drawString(250, y, f"{value}")  # Qiymatni keydan biroz o'ngroqda yozish
                
                y -= 15
                if y < 50:
                    p.showPage()
                    y = 800
                    p.setFont("Helvetica-Bold", 14)
                    p.setFillColor(colors.darkblue)
                    p.drawString(100, 820, f"{self.basename} ro'yxati (davomi):")
            y -= 10

        p.showPage()
        p.save()
        return response

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # Kalitlarni o'zbekchaga o'zgartirish va maxsus nom berish
        data = []
        for obj in serializer.data:
            new_obj = {}
            for key, value in obj.items():
                if key == "created_by":
                    new_obj["Yaratdi"] = value
                elif key == "created_at":
                    new_obj["Yaratilgan vaqti"] = value
                elif key == "eksplutatsiya_vaqti":
                    new_obj["Eksplutatsiya masofasi (km)"] = value
                else:
                    new_obj[key] = value
            data.append(new_obj)

        wb = Workbook()
        ws = wb.active
        ws.title = self.basename

        # Ustun sarlavhalari
        headers = list(data[0].keys()) if data else []
        ws.append(headers)

        # Qiymatlarni bir xil joylashtirish
        for obj in data:
            row = []
            for h in headers:
                row.append(obj.get(h, ""))  # Agar qiymat yo'q bo'lsa, bo'sh qator
            ws.append(row)

        # Ba'zi ustunlarga kenglik berish (ixtiyoriy, chiroyli ko'rinish uchun)
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            adjusted_width = (max_length + 2)
            ws.column_dimensions[col[0].column_letter].width = adjusted_width

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
    pagination_class = CustomPagination
    


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
    queryset = HarakatTarkibi.objects.all().order_by("-id")
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi','tarkib_raqami','turi','ishga_tushgan_vaqti','eksplutatsiya_vaqti']   
    ordering_fields = ['ishga_tushgan_vaqti', 'id']



class TexnikKorikViewSet(viewsets.ModelViewSet):
    queryset = (
        TexnikKorik.objects
        .select_related("tarkib", "tamir_turi", "created_by")
        .prefetch_related("ehtiyot_qismlar")  
        .order_by("-id")
    )
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ["tarkib__nomi", "kamchiliklar_haqida", "bartaraf_etilgan_kamchiliklar", "created_by__username"]
    ordering_fields = ["created_at", "approved_at", "kirgan_vaqti"]

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied("Siz faqat o‘z yozuvlaringizni tahrirlashingiz mumkin.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied("Siz faqat o‘z yozuvlaringizni o‘chira olasiz.")
        instance.delete()


class NosozliklarViewSet(viewsets.ModelViewSet):
    queryset = (
        Nosozliklar.objects
        .select_related("tarkib", "created_by")
        .prefetch_related("ehtiyot_qismlar") 
        .order_by("-id")
    )
    serializer_class = NosozliklarSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ["nosozliklar_haqida", "bartaraf_etilgan_nosozliklar", "tarkib__turi", "created_by__username"]
    ordering_fields = ["created_at", "approved_at", "aniqlangan_vaqti"]

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied("Siz faqat o‘z yozuvlaringizni tahrirlashingiz mumkin.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied("Siz faqat o‘z yozuvlaringizni o‘chira olasiz.")
        instance.delete()
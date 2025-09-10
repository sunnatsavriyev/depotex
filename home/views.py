from rest_framework import viewsets, status, filters, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from .models import (
    TamirTuri, ElektroDepo, EhtiyotQismlari,
    HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, TexnikKorikEhtiyotQism, NosozlikEhtiyotQism, TexnikKorikStep,
)
from .serializers import (
    TamirTuriSerializer, ElektroDepoSerializer,
    EhtiyotQismlariSerializer, HarakatTarkibiSerializer,
    TexnikKorikSerializer, UserSerializer, NosozliklarSerializer, TexnikKorikStepSerializer, NosozlikStepSerializer, NosozlikStep
)
from .permissions import CustomPermission
from django.contrib.auth import authenticate
from .pagination import CustomPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes, action
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image
import io
from reportlab.lib.styles import getSampleStyleSheet
import requests
import django_filters
from rest_framework.exceptions import ValidationError


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
    

    def generate_pdf_detail(self, filename, title, data_list):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            title=title
        )

        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
        elements.append(Spacer(1, 12))

        # Har bir obyekt uchun alohida blok
        for idx, item in enumerate(data_list, start=1):
            elements.append(Paragraph(f"<b>Obyekt #{idx}</b>", styles["Heading2"]))
            elements.append(Spacer(1, 6))

            # 🔹 Avval IMAGE chiqadi
            if "image" in item and item["image"]:
                try:
                    img_resp = requests.get(item["image"], timeout=5)
                    if img_resp.status_code == 200:
                        img_data = io.BytesIO(img_resp.content)
                        img = Image(img_data, width=120, height=80)
                        elements.append(img)
                        elements.append(Spacer(1, 6))
                    else:
                        elements.append(Paragraph("<b>image:</b> [Rasm yuklanmadi]", styles["Normal"]))
                except Exception:
                    elements.append(Paragraph("<b>image:</b> [Rasm yuklashda xato]", styles["Normal"]))

            # 🔹 Keyin qolgan maydonlar
            for key, value in item.items():
                if key.lower() == "image":
                    continue  # image allaqachon chiqarildi
                text = f'<font color="blue"><b>{key}:</b></font> {value}'
                elements.append(Paragraph(text, styles["Normal"]))
                elements.append(Spacer(1, 3))

            # Ajratish chizig‘i
            elements.append(Spacer(1, 6))
            elements.append(HRFlowable(width="100%", color=colors.grey, thickness=0.7, lineCap='round'))
            elements.append(Spacer(1, 12))

        doc.build(elements)

        buffer.seek(0)
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response

    # 🔹 Action endpoint
    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data_list = serializer.data  # serializer natijasini PDF ga uzatamiz
        return self.generate_pdf_detail(self.basename, self.basename + " ro'yxati", data_list)



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


class HarakatTarkibiGetViewSet(BaseViewSet):
    queryset = HarakatTarkibi.objects.all().order_by("-id")
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi', 'tarkib_raqami', 'turi', 'ishga_tushgan_vaqti', 'eksplutatsiya_vaqti']
    ordering_fields = ['ishga_tushgan_vaqti', 'id']
    filterset_fields = ['depo']   

    @action(detail=False, methods=["get"], url_path="by-depo")
    def by_depo(self, request):
        depo_id = request.query_params.get("depo_id")
        if not depo_id:
            return Response({"error": "depo_id query param kerak"}, status=400)

        queryset = self.get_queryset().filter(depo_id=depo_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)



class TexnikKorikFilter(django_filters.FilterSet):
    tamir_turi_nomi = django_filters.CharFilter(
        field_name="tamir_turi__tamir_nomi", lookup_expr="icontains"
    )
    tarkib_raqami = django_filters.CharFilter(
        field_name="tarkib__tarkib_raqami", lookup_expr="icontains"
    )

    class Meta:
        model = TexnikKorik
        fields = ["tamir_turi_nomi", "tarkib_raqami"]





# --- FAQAT GET ---
class TexnikKorikGetViewSet(mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            viewsets.GenericViewSet):
    queryset = (
        TexnikKorik.objects
        .select_related("tarkib", "tamir_turi", "created_by")
        .prefetch_related("ehtiyot_qismlar")
        .order_by("-id")
    )
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = TexnikKorikFilter
    search_fields = [
        "tarkib__tarkib_raqami",
        "kamchiliklar_haqida",
        "bartaraf_etilgan_kamchiliklar",
        "created_by__username",
    ]
    pagination_class = CustomPagination
    ordering_fields = ["created_at", "approved_at", "kirgan_vaqti"]





# class TexnikKorikViewSet(viewsets.ModelViewSet):
#     queryset = (
#         TexnikKorik.objects
#         .select_related("tarkib", "tamir_turi", "created_by")
#         .prefetch_related("ehtiyot_qismlar")
#         .order_by("-id")
#     )
#     serializer_class = TexnikKorikSerializer
#     permission_classes = [IsAuthenticated, CustomPermission]

#     @action(detail=True, methods=["get", "post"], url_path="add-note")
#     def add_note(self, request, pk=None):
#         korik = self.get_object()

#         if request.method == "GET":
#             # Shu korik va uning stepsni ko‘rsatish
#             steps = korik.steps.all().order_by("id")
#             return Response(TexnikKorikSerializer([korik]+list(steps), many=True).data)

#         ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])
#         kamchilik = request.data.get("kamchiliklar_haqida", None)
#         bartaraf = request.data.get("bartaraf_etilgan_kamchiliklar", None)

#         # 🔹 Yangi step yaratish
#         serializer = TexnikKorikSerializer(
#             data=request.data, context={"request": request}
#         )
#         serializer.is_valid(raise_exception=True)
#         new_step = serializer.save(parent=korik)

#         # 🔹 Matn maydonlarini append
#         if kamchilik:
#             new_step.kamchiliklar_haqida = (korik.kamchiliklar_haqida or "") + f"\n{kamchilik}"
#         if bartaraf:
#             new_step.bartaraf_etilgan_kamchiliklar = (korik.bartaraf_etilgan_kamchiliklar or "") + f"\n{bartaraf}"
#         new_step.save()

#         return Response(TexnikKorikSerializer(new_step).data, status=status.HTTP_201_CREATED)

class TexnikKorikViewSet(viewsets.ModelViewSet):
    queryset = TexnikKorik.objects.prefetch_related("steps").all().order_by("-id")
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, CustomPermission]

    @action(detail=True, methods=["post"], url_path="add-step")
    def add_step(self, request, pk=None):
        korik = self.get_object()
        if korik.status == TexnikKorik.Status.BARTARAF_ETILDI:
            return Response({"detail": "Bu korik yakunlangan, yangi step qo'shib bo'lmaydi!"},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = TexnikKorikStepSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        step = serializer.save(korik=korik)
        return Response(TexnikKorikStepSerializer(step).data, status=status.HTTP_201_CREATED)


class TexnikKorikStepViewSet(viewsets.ModelViewSet):
    serializer_class = TexnikKorikStepSerializer
    permission_classes = [IsAuthenticated, CustomPermission]

    def get_queryset(self):
        korik_id = self.kwargs.get("korik_pk")  # nested lookup
        return TexnikKorikStep.objects.filter(korik_id=korik_id).order_by("-id")

    def perform_create(self, serializer):
        user = self.request.user
        korik_id = self.kwargs.get("korik_pk")
        korik = TexnikKorik.objects.filter(id=korik_id).first()

        if not korik or korik.status != TexnikKorik.Status.JARAYONDA:
            raise ValidationError("Avval Texnik Korik boshlang yoki u tugallanmagan!")

        serializer.save(created_by=user, korik=korik)



class NosozliklarFilter(django_filters.FilterSet):
    tamir_turi_nomi = django_filters.CharFilter(
        field_name="tamir_turi__tamir_nomi", lookup_expr="icontains"
    )
    tarkib_raqami = django_filters.CharFilter(
        field_name="tarkib__tarkib_raqami", lookup_expr="icontains"
    )

    class Meta:
        model = Nosozliklar
        fields = ["tamir_turi_nomi", "tarkib_raqami"]


class NosozlikStepFilter(django_filters.FilterSet):
    class Meta:
        model = NosozlikStep
        fields = {
            'nosozlik__nosozliklar_haqida': ['icontains'],
            'bartaraf_etilgan_nosozliklar': ['icontains'],
            'tamir_turi__tamir_nomi': ['icontains'],
            'created_by__username': ['icontains'],
            'created_at': ['exact', 'gte', 'lte'],
            'bartaraf_qilingan_vaqti': ['exact', 'gte', 'lte'],
        }



class NosozliklarGetViewSet(mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            viewsets.GenericViewSet):
    queryset = (
        Nosozliklar.objects
        .select_related("tarkib","created_by")
        .prefetch_related("ehtiyot_qismlar")
        .order_by("-id")
    )
    serializer_class = NosozliklarSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = NosozliklarFilter
    search_fields = [
        "nosozliklar_haqida",
        "bartaraf_etilgan_nosozliklar",
        "tarkib__turi",
        "created_by__username",
    ]
    pagination_class = CustomPagination
    ordering_fields = ["created_at", "approved_at", "aniqlangan_vaqti"]



class NosozlikStepViewSet(viewsets.ModelViewSet):
    queryset = NosozlikStep.objects.select_related("nosozlik", "tamir_turi", "created_by").prefetch_related("ehtiyot_qismlar_step").order_by("-id")
    serializer_class = NosozlikStepSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = NosozlikStepFilter
    search_fields = ['nosozlik__nosozliklar_haqida', 'bartaraf_etilgan_nosozliklar', 'tamir_turi__tamir_nomi', 'created_by__username']
    ordering_fields = ["created_at", "bartaraf_qilingan_vaqti"]
    pagination_class = CustomPagination


    def get_queryset(self):
        nosozlik_id = self.kwargs.get("nosozlik_pk")
        return NosozlikStep.objects.filter(nosozlik_id=nosozlik_id)
    
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
    filterset_class = NosozliklarFilter
    search_fields = [
        "nosozliklar_haqida",
        "bartaraf_etilgan_nosozliklar",
        "tarkib__turi",
        "created_by__username",
    ]
    ordering_fields = ["created_at", "approved_at", "aniqlangan_vaqti"]
    pagination_class = CustomPagination

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied("Siz faqat o‘z yozuvlaringizni tahrirlashingiz mumkin.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by != self.request.user and not self.request.user.is_superuser:
            raise PermissionDenied("Siz faqat o‘z yozuvlaringizni o‘chira olasiz.")
        instance.delete()

    # Qo‘shimcha action: Add note yoki ehtiyot qismlar
    @action(detail=True, methods=["get", "post"], url_path="add-note")
    def add_note(self, request, pk=None):
        nosozlik = self.get_object()

        if request.method == "GET":
            return Response(NosozliklarSerializer(nosozlik).data)

        ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])
        nosozlik_haqida = request.data.get("nosozliklar_haqida", None)
        bartaraf = request.data.get("bartaraf_etilgan_nosozliklar", None)

        for item in ehtiyot_qismlar:
            miqdor = item.get("miqdor", 1)
            eq_id = item.get("ehtiyotqism_id", None)
            if eq_id:
                ehtiyot_qism = EhtiyotQismlari.objects.filter(id=eq_id).first()
            else:
                continue
            if not ehtiyot_qism:
                return Response({"detail": f"Ehtiyot qism id {eq_id} topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

            obj, created = NosozlikEhtiyotQism.objects.get_or_create(
                nosozlik=nosozlik,
                ehtiyot_qism=ehtiyot_qism,
                defaults={"miqdor": miqdor}
            )
            if not created:
                obj.miqdor += miqdor
                obj.save()

        if nosozlik_haqida:
            nosozlik.nosozliklar_haqida = (nosozlik.nosozliklar_haqida or "") + f"\n{nosozlik_haqida}"
        if bartaraf:
            nosozlik.bartaraf_etilgan_nosozliklar = (nosozlik.bartaraf_etilgan_nosozliklar or "") + f"\n{bartaraf}"
        nosozlik.save()
        return Response(NosozliklarSerializer(nosozlik).data, status=status.HTTP_200_OK)
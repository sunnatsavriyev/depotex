from rest_framework import viewsets, status, filters, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from openpyxl import Workbook
from .models import (
    TamirTuri, ElektroDepo, EhtiyotQismlari,
    HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, NosozlikEhtiyotQism, TexnikKorikStep,KunlikYurish,
    Vagon,
)
from .serializers import (
    TamirTuriSerializer, ElektroDepoSerializer,
    EhtiyotQismlariSerializer, HarakatTarkibiSerializer,
    TexnikKorikSerializer, UserSerializer, NosozliklarSerializer, TexnikKorikStepSerializer, NosozlikStepSerializer,
    NosozlikStep,KunlikYurishSerializer,VagonSerializer,
    HarakatTarkibiActiveSerializer
)
from django.db.models import Sum
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
from reportlab.platypus import Paragraph, Spacer, HRFlowable, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from django.db.models import Count
from django.utils.timezone import now
from datetime import timedelta
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

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
    
    def get_queryset(self):
        if self.queryset is not None:
            return self.queryset
        return self.serializer_class.Meta.model.objects.none()

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
        doc = SimpleDocTemplate(buffer, pagesize=A4, title=title)

        styles = getSampleStyleSheet()
        # Rangli va chiroyli style’lar
        title_style = ParagraphStyle('title_style', parent=styles['Title'], textColor=colors.darkblue)
        header_style = ParagraphStyle('header_style', parent=styles['Heading2'], backColor=colors.lightblue, textColor=colors.white)
        step_style = ParagraphStyle('step_style', parent=styles['Heading3'], textColor=colors.darkgreen)
        field_style = ParagraphStyle('field_style', parent=styles['Normal'], textColor=colors.black, leftIndent=10)
        eq_style = ParagraphStyle('eq_style', parent=styles['Normal'], textColor=colors.purple, leftIndent=20)

        elements = []

        # Document title
        elements.append(Paragraph(f"{title}", title_style))
        elements.append(Spacer(1, 12))

        for idx, item in enumerate(data_list, start=1):
            # Asosiy obyekt
            elements.append(Paragraph(f"Obyekt #{idx}", header_style))
            elements.append(Spacer(1, 6))

            # IMAGE
            if "image" in item and item["image"]:
                try:
                    img_resp = requests.get(item["image"], timeout=5)
                    if img_resp.status_code == 200:
                        img_data = io.BytesIO(img_resp.content)
                        img = Image(img_data, width=120, height=80)
                        elements.append(img)
                        elements.append(Spacer(1, 6))
                except:
                    elements.append(Paragraph("<b>image:</b> [Rasm yuklashda xato]", field_style))

            # Asosiy maydonlar
            for key, value in item.items():
                if key.lower() == "image":
                    continue
                if key == "steps" and isinstance(value, dict):
                    results = value.get("results", [])
                    for s_idx, step in enumerate(results, start=1):
                        elements.append(Paragraph(f"{idx},{s_idx} Step", step_style))
                        for skey, svalue in step.items():
                            if skey.lower() == "ehtiyot_qismlar_detail":
                                # Step ehtiyot qismlar
                                for eq in svalue:
                                    eq_text = f"- {eq.get('ehtiyotqism_nomi')} ({eq.get('birligi')}) x {eq.get('miqdor')}"
                                    elements.append(Paragraph(eq_text, eq_style))
                            else:
                                elements.append(Paragraph(f"<b>{skey}:</b> {svalue}", field_style))
                        elements.append(Spacer(1, 4))
                    continue

                if key.lower() == "ehtiyot_qismlar_detail" and isinstance(value, list):
                    # Asosiy obyekt ehtiyot qismlarini ham chiroyli chiqaramiz
                    for eq in value:
                        eq_text = f"- {eq.get('ehtiyotqism_nomi')} ({eq.get('birligi')}) x {eq.get('miqdor')}"
                        elements.append(Paragraph(eq_text, eq_style))
                    elements.append(Spacer(1, 4))
                    continue

                # Oddiy maydonlar
                elements.append(Paragraph(f"<b>{key}:</b> {value}", field_style))
                elements.append(Spacer(1, 2))

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

        wb = Workbook()
        ws = wb.active
        ws.title = self.basename

        # Asosiy ustunlar + step uchun ustunlar
        headers = [
            "ID", "Tarkib", "Tarkib nomi", "Tamir turi", "Tamir turi nomi", 
            "Status", "Kamchiliklar", "Ehtiyot qismlar", "Bartaraf etilgan", 
            "Kirgan vaqti", "Yaratdi", "Yaratilgan vaqti",
            "Step raqami", "Step kamchilik", "Step ehtiyot qismlar", 
            "Step bartaraf etilgan", "Step yaratuvchi", "Step vaqti", "Step status"
        ]
        ws.append(headers)

        for obj in serializer.data:
            # Ehtiyot qismlar
            eq_text = ", ".join(f"{eq['ehtiyotqism_nomi']} ({eq['birligi']}) x {eq['miqdor']}" for eq in obj.get("ehtiyot_qismlar_detail", []))

            # Asosiy obyekt info
            base_data = [
                obj.get("id"), obj.get("tarkib"), obj.get("tarkib_nomi"), obj.get("tamir_turi"),
                obj.get("tamir_turi_nomi"), obj.get("status"), obj.get("kamchiliklar_haqida"),
                eq_text, obj.get("bartaraf_etilgan_kamchiliklar"), obj.get("kirgan_vaqti"),
                obj.get("created_by"), obj.get("created_at")
            ]

            steps = obj.get("steps", [])
            if steps:
                # steps dict bo'lsa -> results ichidan olish
                if isinstance(steps, dict):
                    steps = steps.get("results", [])

                for s_idx, step in enumerate(steps, start=1):
                    step_eq = ", ".join(
                        f"{eq['ehtiyotqism_nomi']} ({eq['birligi']}) x {eq['miqdor']}"
                        for eq in step.get("ehtiyot_qismlar_detail", [])
                    )
                    step_data = [
                        f"{s_idx}",  # Step raqami
                        step.get("kamchiliklar_haqida", ""),
                        step_eq,
                        step.get("bartaraf_etilgan_kamchiliklar", ""),
                        step.get("created_by", ""),
                        step.get("created_at", ""),
                        step.get("status", "")
                    ]
                    ws.append(base_data + step_data)
            else:
                ws.append(base_data + [""]*7)


        # Kenglik berish
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2

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
    queryset = (
    HarakatTarkibi.objects.filter(is_active=True)
    .annotate(total_kilometr=Sum("kunlik_yurishlar__kilometr"))
    .order_by("-id")
    )
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    def get_queryset(self):
        user = self.request.user

        # superuser hammasini ko‘radi
        if user.is_superuser:
            return HarakatTarkibi.objects.all().order_by("-id")

        # texnik faqat o‘z deposidagi tarkiblarni ko‘radi
        if user.role == "texnik" and user.depo:
            return HarakatTarkibi.objects.all().order_by("-id")

        # monitoring hammasini faqat o‘qiy oladi
        if user.role == "monitoring":
            return HarakatTarkibi.objects.all().order_by("-id")

        return HarakatTarkibi.objects.none()
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi','tarkib_raqami','turi','ishga_tushgan_vaqti','eksplutatsiya_vaqti']   
    ordering_fields = ['ishga_tushgan_vaqti', 'id']
    
    # def update(self, request, *args, **kwargs):
    #     partial = kwargs.pop('partial', False)
    #     instance = self.get_object()
    #     serializer = self.get_serializer(instance, data=request.data, partial=partial)
    #     serializer.is_valid(raise_exception=True)
    #     new_instance = serializer.save()

    #     # 🔥 front-end JSON ko‘rishi uchun qaytarish
    #     output_serializer = self.get_serializer(new_instance)
    #     return Response(output_serializer.data, status=status.HTTP_200_OK)



class HarakatTarkibiGetViewSet(BaseViewSet):
    queryset = (
    HarakatTarkibi.objects.filter(is_active=True)
    .annotate(total_kilometr=Sum("kunlik_yurishlar__kilometr"))
    .order_by("-id")
    )
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

        queryset = (
            self.get_queryset()
            .filter(depo_id=depo_id, is_active=True)
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    
    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        obj = self.get_object()
        versions = HarakatTarkibi.objects.filter(
            tarkib_raqami=obj.tarkib_raqami
        ).order_by("-id")

        serializer = self.get_serializer(versions, many=True)
        return Response(serializer.data)


    def perform_create(self, serializer):
        # Agar tarkib_raqami bo‘yicha eski versiya bo‘lsa → uni deactivate qilamiz
        tarkib_raqami = serializer.validated_data.get("tarkib_raqami")
        eski_versiya = (
            HarakatTarkibi.objects.filter(tarkib_raqami=tarkib_raqami, is_active=True)
            .order_by("-id")
            .first()
        )

        if eski_versiya:
            eski_versiya.is_active = False
            eski_versiya.save()

            # yangi obyekt eski versiyaga bog‘lanadi
            serializer.save(
                created_by=self.request.user,
                previous_version=eski_versiya,
                is_active=True,
            )
        else:
            # birinchi versiya bo‘lsa
            serializer.save(created_by=self.request.user, is_active=True)
            
    @action(detail=True, methods=["get"], url_path="vagonlar")
    def vagonlar(self, request, pk=None):
        obj = self.get_object()
        vagonlar = obj.vagon_set.all()  # yoki obj.vagonlar.all() agar related_name="vagonlar"
        serializer = VagonSerializer(vagonlar, many=True)
        return Response(serializer.data)


class HarakatTarkibiActiveViewSet(BaseViewSet):
    queryset = (
        HarakatTarkibi.objects.filter(is_active=True)
        .annotate(total_kilometr=Sum("kunlik_yurishlar__kilometr"))
        .order_by("-id")
    )
    serializer_class = HarakatTarkibiActiveSerializer
    basename = "Harakat Tarkibi Active"
    permission_classes = [IsAuthenticated, CustomPermission]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi', 'tarkib_raqami', 'turi', 'ishga_tushgan_vaqti', 'eksplutatsiya_vaqti']
    ordering_fields = ['ishga_tushgan_vaqti', 'id']
    filterset_fields = ['depo']




class KunlikYurishViewSet(BaseViewSet):
    serializer_class = KunlikYurishSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        qs = KunlikYurish.objects.select_related("tarkib", "created_by")

        if user.role == "texnik" and user.depo:
            qs = qs.filter(tarkib__depo=user.depo)
            
            
        if self.action == "list":
            qs = qs.filter(tarkib__holati="Soz_holatda")

        return qs.order_by("-sana", "-id")

    def perform_create(self, serializer):
        user = self.request.user
        tarkib = serializer.validated_data["tarkib"]

        if user.role == "texnik" and tarkib.depo != user.depo:
            raise PermissionDenied("Siz faqat o‘z depo tarkiblaringiz uchun ma’lumot qo‘shishingiz mumkin.")

        serializer.save(created_by=user)

    # 🔹  Umumiy jami yurilgan km
    @action(detail=True, methods=["get"])
    def total(self, request, pk=None):
        tarkib = self.get_object().tarkib
        total_km = KunlikYurish.objects.filter(tarkib=tarkib).aggregate(Sum("kilometr"))["kilometr__sum"] or 0
        return Response({"tarkib": tarkib.tarkib_raqami, "total_km": total_km})

    # 🔹 Sana bo‘yicha hisoblash
    @action(detail=False, methods=["get"])
    def by_date(self, request):
        tarkib_id = request.query_params.get("tarkib_id")
        sana = request.query_params.get("sana")  # YYYY-MM-DD format

        if not tarkib_id or not sana:
            return Response({"error": "tarkib_id va sana kerak"}, status=400)

        qs = KunlikYurish.objects.filter(tarkib_id=tarkib_id)

        # o‘sha kunda nechchi km
        daily_km = qs.filter(sana=sana).aggregate(Sum("kilometr"))["kilometr__sum"] or 0

        # shu kungacha jami km
        total_until = qs.filter(sana__lte=sana).aggregate(Sum("kilometr"))["kilometr__sum"] or 0

        return Response({
            "tarkib_id": tarkib_id,
            "sana": sana,
            "daily_km": daily_km,
            "total_until": total_until
        })



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





class TexnikKorikViewSet(BaseViewSet):
    queryset = TexnikKorik.objects.prefetch_related("steps").all().order_by("-id")
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "tarkib__tarkib_raqami",
        "tamir_turi__tamir_nomi",
        "created_by__username",
        "id",
    ]
    pagination_class = CustomPagination
    def get_queryset(self):
        user = self.request.user
        qs = TexnikKorik.objects.prefetch_related("steps").order_by("-id")

        if user.role == "texnik" and user.depo:
            qs = qs.filter(tarkib__depo=user.depo)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, description="Step pagination page"),
            OpenApiParameter(name="limit", type=int, location=OpenApiParameter.QUERY, description="Step page size"),
            OpenApiParameter(name="search", type=str, location=OpenApiParameter.QUERY, description="Step search"),
        ]
    )
    def retrieve(self, request, *args, **kwargs):
        """Detail with steps pagination"""
        return super().retrieve(request, *args, **kwargs)
    
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
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]

    search_fields = [
        "id",
        "kamchiliklar_haqida",
        "bartaraf_etilgan_kamchiliklar",
        "created_by__username",
        "korik__tarkib__tarkib_raqami",
        "tamir_turi__tamir_nomi",
    ]

    filterset_fields = ["korik"]  

    def get_queryset(self):
        user = self.request.user
        qs = TexnikKorikStep.objects.all().order_by("-id")

        # faqat o‘z depo uchun texnik
        if user.role == "texnik" and user.depo:
            qs = qs.filter(korik__tarkib__depo=user.depo)

        # query param orqali korik_id
        korik_id = self.request.query_params.get("korik")
        if korik_id:
            qs = qs.filter(korik_id=korik_id)

        return qs

    def perform_create(self, serializer):
        korik = serializer.validated_data.get("korik")
        if not korik or korik.status != korik.Status.JARAYONDA:
            raise ValidationError("Avval Texnik Korik boshlang yoki u tugallanmagan!")
        serializer.save(created_by=self.request.user)


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
        "tarkib__tarkib_raqami",
        "created_by__username",
    ]
    pagination_class = CustomPagination
    ordering_fields = ["created_at", "approved_at", "aniqlangan_vaqti"]


# --- Nosozliklar ViewSet (Texnik Korikga o'xshash) ---
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
        "tarkib__tarkib_raqami",
        "created_by__username",
    ]
    ordering_fields = ["created_at", "approved_at", "aniqlangan_vaqti"]
    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == "texnik" and user.depo:
            qs = qs.filter(tarkib__depo=user.depo)
        return qs

    def perform_create(self, serializer):
        request = self.request
        password = request.data.get("password")
        if not password or not request.user.check_password(password):
            raise ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = request.data.get("yakunlash", False)
        akt_file = request.data.get("akt_file", None)
        ehtiyot_qismlar = request.data.get("ehtiyot_qismlar", [])

        validated_data = serializer.validated_data.copy()
        validated_data.pop("password", None)
        validated_data.pop("yakunlash", None)
        validated_data.pop("akt_file", None)
        validated_data.pop("ehtiyot_qismlar", None)

        nosozlik = Nosozliklar.objects.create(
            created_by=request.user,
            status=Nosozliklar.Status.BARTARAF_ETILDI if yakunlash else Nosozliklar.Status.JARAYONDA,
            akt_file=akt_file,
            **validated_data
        )

        for item in ehtiyot_qismlar:
            eq_obj = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if eq_obj:
                NosozlikEhtiyotQism.objects.create(
                    nosozlik=nosozlik, ehtiyot_qism=eq_obj, miqdor=miqdor
                )

        # ❌ return emas
        serializer.instance = nosozlik   # ✅ DRFga yaratilgan obyektni biriktiramiz


    @action(detail=True, methods=["post"], url_path="add-step")
    def add_step(self, request, pk=None):
        nosozlik = self.get_object()
        if nosozlik.status == Nosozliklar.Status.BARTARAF_ETILDI:
            return Response({"detail": "Bu nosozlik allaqachon yakunlangan, yangi step qo'shib bo'lmaydi!"},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = NosozlikStepSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        step = serializer.save(nosozlik=nosozlik)
        return Response(NosozlikStepSerializer(step, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)





# --- Nosozlik Step ViewSet (Texnik Korik Stepga o'xshash) ---
class NosozlikStepViewSet(viewsets.ModelViewSet):
    serializer_class = NosozlikStepSerializer
    permission_classes = [IsAuthenticated, CustomPermission]
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = NosozlikStepFilter

    search_fields = [
        "id",
        "nosozliklar_haqida",
        "bartaraf_etilgan_nosozliklar",
        "created_by__username",
        "nosozlik__tarkib__tarkib_raqami",
    ]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset().order_by("-id")
        if user.role == "texnik" and user.depo:
            qs = qs.filter(nosozlik__tarkib__depo=user.depo)

        nosozlik_id = self.request.query_params.get("nosozlik")
        if nosozlik_id:
            qs = qs.filter(nosozlik_id=nosozlik_id)
        return qs

    def perform_create(self, serializer):
        request = self.request
        password = request.data.get("password")
        if not password or not request.user.check_password(password):
            raise ValidationError({"password": "Parol noto‘g‘ri."})

        nosozlik = serializer.validated_data.get("nosozlik")
        if not nosozlik or nosozlik.status != Nosozliklar.Status.JARAYONDA:
            raise ValidationError("Avval Nosozlik jarayonini boshlang yoki u tugallanmagan bo‘lishi kerak!")

        # serializer.validated_data dan passwordni olib tashlaymiz
        validated_data = serializer.validated_data.copy()
        validated_data.pop("password", None)

        serializer.save(created_by=request.user, **validated_data)


   
   
    
class KorikNosozlikStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = now().date()
        first_day_this_month = today.replace(day=1)
        first_day_last_month = (first_day_this_month - timedelta(days=1)).replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)

        # 1) Umumiy texnik ko‘riklar soni
        total_korik = TexnikKorik.objects.count()

        # 2) Umumiy nosozliklar soni
        total_nosozlik = Nosozliklar.objects.count()

        # 3) Oxirgi oyda bajarilgan texnik ko‘riklar soni
        last_month_korik = TexnikKorik.objects.filter(
            created_at__date__gte=first_day_last_month,
            created_at__date__lte=last_day_last_month
        ).count()

        # 4) Oxirgi oydagi nosozliklar soni
        last_month_nosozlik = Nosozliklar.objects.filter(
            created_at__date__gte=first_day_last_month,
            created_at__date__lte=last_day_last_month
        ).count()

        # 5) Eng ko‘p texnik ko‘rik va nosozlik qayd etilgan 5 ta tarkib
        korik_counts = (
            TexnikKorik.objects.values("tarkib__id", "tarkib__tarkib_raqami", "tarkib__turi")
            .annotate(total=Count("id"))
        )
        nosozlik_counts = (
            Nosozliklar.objects.values("tarkib__id", "tarkib__tarkib_raqami", "tarkib__turi")
            .annotate(total=Count("id"))
        )

        combined = {}

        # Texnik ko‘riklardan yig‘ish
        for item in korik_counts:
            tid = item["tarkib__id"]
            combined[tid] = {
                "id": tid,
                "raqam": item["tarkib__tarkib_raqami"],
                "turi": item["tarkib__turi"],
                "total": combined.get(tid, {}).get("total", 0) + item["total"],
            }

        # Nosozliklardan yig‘ish
        for item in nosozlik_counts:
            tid = item["tarkib__id"]
            if tid in combined:
                combined[tid]["total"] += item["total"]
            else:
                combined[tid] = {
                    "id": tid,
                    "raqam": item["tarkib__tarkib_raqami"],
                    "turi": item["tarkib__turi"],
                    "total": item["total"],
                }

        # eng ko‘pdan eng kamgacha saralash
        top_5_tarkib = sorted(combined.values(), key=lambda x: x["total"], reverse=True)[:5]

        return Response({
            "total_korik": total_korik,
            "total_nosozlik": total_nosozlik,
            "last_month_korik": last_month_korik,
            "last_month_nosozlik": last_month_nosozlik,
            "top_5_tarkib": top_5_tarkib,
        })

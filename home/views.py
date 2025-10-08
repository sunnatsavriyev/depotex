from rest_framework import viewsets, status, filters, mixins, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from .models import (
    TamirTuri, ElektroDepo, EhtiyotQismlari,
    HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, NosozlikEhtiyotQism, TexnikKorikStep,KunlikYurish,
    Vagon,EhtiyotQismHistory, TexnikKorikEhtiyotQism,
)
from .serializers import (
    TamirTuriSerializer, ElektroDepoSerializer,
    EhtiyotQismlariSerializer, HarakatTarkibiSerializer,
    TexnikKorikSerializer, UserSerializer, NosozliklarSerializer, TexnikKorikStepSerializer, NosozlikStepSerializer,
    NosozlikStep,KunlikYurishSerializer,VagonSerializer,
    HarakatTarkibiActiveSerializer, EhtiyotQismWithMiqdorSerializer,EhtiyotQismHistorySerializer, TarkibFullDetailSerializer,TexnikKorikDetailForStepSerializer,NosozlikDetailForStepSerializer)
from django.utils import timezone
from django.db.models import Sum, F
from django.contrib.auth import authenticate
from .pagination import CustomPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes, action
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image
import io
from reportlab.lib.styles import getSampleStyleSheet
import requests
import django_filters
from rest_framework.exceptions import ValidationError
from reportlab.platypus import Paragraph, Spacer, HRFlowable, Image, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from django.db.models import Count
from django.utils.timezone import now
from datetime import timedelta, datetime
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .permissions import IsMonitoringReadOnly, IsTexnik, IsSkladchi
import json
from reportlab.lib.units import cm
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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
    permission_classes = [IsAuthenticated, IsSkladchi,IsMonitoringReadOnly,IsTexnik]
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
        title_style = ParagraphStyle('title_style', parent=styles['Title'], textColor=colors.darkblue, alignment=1)
        header_style = ParagraphStyle('header_style', parent=styles['Heading2'], textColor=colors.white, backColor=colors.darkblue, alignment=1)
        field_style = ParagraphStyle('field_style', parent=styles['Normal'], textColor=colors.black, fontSize=9, leading=11)

        elements = []
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 20))

        for idx, item in enumerate(data_list, start=1):
            elements.append(Paragraph(f"Obyekt #{idx}", header_style))
            elements.append(Spacer(1, 10))

            # Asosiy jadval (steps va ichki narsalarsiz)
            table_data = [[Paragraph("<b>Maydon</b>", field_style), Paragraph("<b>Qiymat</b>", field_style)]]
            for key, value in item.items():
                if key in ["image", "steps", "vagonlar"]:  # ichki obyektlarni asosiydan chiqarib turamiz
                    continue
                table_data.append([Paragraph(str(key), field_style), Paragraph(str(value), field_style)])

            table = Table(table_data, colWidths=[150, 350])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 15))

            # Agar steps bo‘lsa
            if "steps" in item and isinstance(item["steps"], dict):
                steps = item["steps"].get("results", [])
                if steps:
                    elements.append(Paragraph("🔹 Ko‘rik bosqichlari", header_style))
                    elements.append(Spacer(1, 8))

                    step_table_data = [
                        [Paragraph("<b>ID</b>", field_style),
                        Paragraph("<b>Kamchiliklar</b>", field_style),
                        Paragraph("<b>Kim tomonidan</b>", field_style)]
                    ]

                    for step in steps:
                        step_table_data.append([
                            Paragraph(str(step.get("id")), field_style),
                            Paragraph(str(step.get("kamchiliklar_haqida")), field_style),
                            Paragraph(str(step.get("created_by")), field_style),
                        ])

                    step_table = Table(step_table_data, colWidths=[40, 200, 150])
                    step_table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]))
                    elements.append(step_table)
                    elements.append(Spacer(1, 20))

            elements.append(HRFlowable(width="100%", color=colors.darkgrey, thickness=0.7))
            elements.append(Spacer(1, 20))

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response

    # 🔹 PDF eksport
    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data_list = serializer.data
        return self.generate_pdf_detail(self.basename, f"{self.basename.capitalize()} ro'yxati", data_list)



    excel_headers = None        # optional: ["ID", "Name", ...]
    excel_filename = None       # optional: "my_export.xlsx"
    exclude_excel_fields = ["image", "vagonlar", "steps"]   # keraksiz ustunlar

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)

        wb = Workbook()
        ws = wb.active
        ws.title = (getattr(self, "basename", None) or self.__class__.__name__).capitalize()

        # Headerlar
        headers = self.get_excel_headers(serializer)
        if headers:
            ws.append(headers)

            # Header style
            header_fill = PatternFill("solid", fgColor="4F81BD")
            header_font = Font(bold=True, color="FFFFFF")
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin")
        )

        # Data yozish
        for row_data in self.format_excel_data(serializer.data, headers=headers):
            ws.append(row_data)

        # Border & alignment
        if ws.max_row >= 2:
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center", wrap_text=True)

        # Column auto width
        for col in ws.columns:
            try:
                max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2
            except Exception:
                pass

        # Fayl nomi
        filename = self.excel_filename or f"{(getattr(self, 'basename', None) or self.__class__.__name__).lower()}.xlsx"
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    def get_excel_headers(self, serializer):
        """
        Agar child viewset excel_headers bersa — uni ishlatamiz.
        Aks holda serializer.data[0].keys() dan olamiz va exclude qilamiz.
        """
        headers = []
        if getattr(self, "excel_headers", None):
            headers = list(self.excel_headers)
        elif getattr(serializer, "data", None):
            if len(serializer.data) > 0 and isinstance(serializer.data[0], dict):
                headers = list(serializer.data[0].keys())

        # exclude qilingan ustunlarni olib tashlaymiz
        exclude = getattr(self, "exclude_excel_fields", [])
        headers = [h for h in headers if h not in exclude]
        return headers

    def format_excel_data(self, data_list, headers=None):
        """
        Serializer.data ichidan faqat kerakli headerlarga mos qiymatlarni olib beradi.
        """
        rows = []
        headers = headers or []
        if not data_list:
            return rows

        for obj in data_list:
            row = []
            for h in headers:
                value = obj.get(h, "")
                if isinstance(value, (list, dict)):
                    try:
                        value = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        value = str(value)
                row.append(value if value is not None else "")
            rows.append(row)
        return rows


class TamirTuriViewSet(BaseViewSet):
    queryset = TamirTuri.objects.all()
    serializer_class = TamirTuriSerializer
    basename = "Tamir Turi"
    permission_classes = [IsAuthenticated,IsTexnik]
    require_login_fields = False
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['tamir_nomi', 'tamirlash_davri', 'tamirlanish_vaqti']   
    ordering_fields = ['tamirlanish_vaqti', 'id']
    pagination_class = CustomPagination
    


class ElektroDepoViewSet(BaseViewSet):
    queryset = ElektroDepo.objects.all()
    serializer_class = ElektroDepoSerializer
    basename = "Elektro Depo"
    permission_classes = [IsAuthenticated, IsTexnik]
    require_login_fields = False
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['depo_nomi', 'qisqacha_nomi', 'joylashuvi']   
    ordering_fields = ['qisqacha_nomi', 'id']
    

class EhtiyotQismlariViewSet(viewsets.ModelViewSet):
    queryset = EhtiyotQismlari.objects.all().order_by('-id')
    serializer_class = EhtiyotQismlariSerializer
    permission_classes = [IsAuthenticated, IsSkladchi]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['ehtiyotqism_nomi', 'nomenklatura_raqami']
    ordering_fields = ['id', 'nomenklatura_raqami']
    pagination_class = CustomPagination
    
    
class EhtiyotQismMiqdorListAPIView(APIView):
        permission_classes = [IsAuthenticated, IsSkladchi]

        def get(self, request, ehtiyotqism_pk):
            try:
                ehtiyot_qism = EhtiyotQismlari.objects.get(pk=ehtiyotqism_pk)
            except EhtiyotQismlari.DoesNotExist:
                return Response({"error": "Ehtiyot qism topilmadi"}, status=status.HTTP_404_NOT_FOUND)

            history = EhtiyotQismHistory.objects.filter(
                ehtiyot_qism=ehtiyot_qism
            ).order_by('-created_at')

            jami_miqdor = history.aggregate(total=Sum('miqdor'))['total'] or 0
            serializer = EhtiyotQismHistorySerializer(history, many=True)

            return Response({
                "id": ehtiyot_qism.id,
                "ehtiyotqism_nomi": ehtiyot_qism.ehtiyotqism_nomi,
                "birligi": ehtiyot_qism.birligi,
                "depo": ehtiyot_qism.depo.qisqacha_nomi,
                "jami_miqdor": jami_miqdor,
                "history": serializer.data
            })

class EhtiyotQismMiqdorCreateAPIView(generics.CreateAPIView):
    serializer_class = EhtiyotQismHistorySerializer
    permission_classes = [IsAuthenticated, IsSkladchi]

    def perform_create(self, serializer):
        ehtiyotqism_pk = self.kwargs.get("ehtiyotqism_pk")
        ehtiyot_qism = EhtiyotQismlari.objects.get(pk=ehtiyotqism_pk)

        serializer.save(
            ehtiyot_qism=ehtiyot_qism,
            created_by=self.request.user
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        ehtiyotqism_pk = self.kwargs.get("ehtiyotqism_pk")
        ehtiyot_qism = EhtiyotQismlari.objects.get(pk=ehtiyotqism_pk)

        history = EhtiyotQismHistory.objects.filter(
            ehtiyot_qism=ehtiyot_qism
        ).order_by("-created_at")

        jami_miqdor = history.aggregate(total=Sum("miqdor"))['total'] or 0

        response.data = {
            "status": "Miqdor qo'shildi",
            "id": ehtiyot_qism.id,
            "jami_miqdor": jami_miqdor,
            "history": EhtiyotQismHistorySerializer(history, many=True).data,
        }
        return response
        

class HarakatTarkibiViewSet(BaseViewSet):
    queryset = (
    HarakatTarkibi.objects.filter(is_active=True)
    .annotate(total_kilometr=Sum("kunlik_yurishlar__kilometr"))
    .order_by("-id")
    )
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, IsTexnik]
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
    



class HarakatTarkibiGetViewSet(BaseViewSet):
    queryset = (
    HarakatTarkibi.objects.filter(is_active=True)
    .annotate(total_kilometr=Sum("kunlik_yurishlar__kilometr"))
    .order_by("-id")
    )
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, IsTexnik]
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
    permission_classes = [IsAuthenticated, IsTexnik]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi', 'tarkib_raqami', 'turi', 'ishga_tushgan_vaqti', 'eksplutatsiya_vaqti']
    ordering_fields = ['ishga_tushgan_vaqti', 'id']
    filterset_fields = ['depo']




class KunlikYurishViewSet(BaseViewSet):
    serializer_class = KunlikYurishSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
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

    @action(detail=True, methods=["get"])
    def total(self, request, pk=None):
        tarkib = self.get_object().tarkib
        total_km = KunlikYurish.objects.filter(tarkib=tarkib).aggregate(Sum("kilometr"))["kilometr__sum"] or 0
        return Response({"tarkib": tarkib.tarkib_raqami, "total_km": total_km})

    @action(detail=False, methods=["get"])
    def by_date(self, request):
        tarkib_id = request.query_params.get("tarkib_id")
        sana = request.query_params.get("sana")  

        if not tarkib_id or not sana:
            return Response({"error": "tarkib_id va sana kerak"}, status=400)

        try:
            sana_date = datetime.strptime(sana, "%d-%m-%Y").date()
        except ValueError:
            return Response({"error": "Sana format noto‘g‘ri, DD-MM-YYYY bo‘lishi kerak"}, status=400)

        qs = KunlikYurish.objects.filter(tarkib_id=tarkib_id)

        daily_km = qs.filter(sana=sana_date).aggregate(Sum("kilometr"))["kilometr__sum"] or 0
        total_until = qs.filter(sana__lte=sana_date).aggregate(Sum("kilometr"))["kilometr__sum"] or 0

        return Response({
            "tarkib_id": tarkib_id,
            "sana": sana,
            "daily_km": daily_km,
            "total_until": total_until
        })

class KunlikYurishHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTexnik]
    pagination_class = CustomPagination

    def get(self, request, tarkib_id, *args, **kwargs):
        qs = KunlikYurish.objects.filter(
            tarkib_id=tarkib_id
        ).select_related("tarkib", "created_by").order_by("-sana", "-id")

        serializer = KunlikYurishSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)
    
    @action(detail=False, methods=["get"])
    def by_date(self, request):
        tarkib_id = request.query_params.get("tarkib_id")
        sana = request.query_params.get("sana")  # kutilayotgan format: "DD:MM:YYYY"

        if not tarkib_id or not sana:
            return Response({"error": "tarkib_id va sana kerak"}, status=400)

        try:
            sana_date = datetime.strptime(sana, "%d-%m-%Y").date()
        except ValueError:
            return Response({"error": "Sana format noto‘g‘ri, DD-MM-YYYY bo‘lishi kerak"}, status=400)

        qs = KunlikYurish.objects.filter(tarkib_id=tarkib_id)

        daily_km = qs.filter(sana=sana_date).aggregate(Sum("kilometr"))["kilometr__sum"] or 0
        total_until = qs.filter(sana__lte=sana_date).aggregate(Sum("kilometr"))["kilometr__sum"] or 0

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
        .prefetch_related(
            "texnikkorikehtiyotqism_set__ehtiyot_qism",  # ✅ Asosiy ko'rik ehtiyot qismlari
            "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",  # ✅ Step ehtiyot qismlari
            "steps"  # ✅ Steplarni ham prefetch qilish
        )
        .order_by("-id")
    )
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
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


    
    def get_queryset(self):
        user = self.request.user
        qs = (
            TexnikKorik.objects
            .select_related("tarkib", "tamir_turi", "created_by")
            .prefetch_related(
                "texnikkorikehtiyotqism_set__ehtiyot_qism",
                "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",
                "steps"
            )
            .order_by("-id")
        )

        if user.role == "texnik" and user.depo:
            qs = qs.filter(tarkib__depo=user.depo)
        return qs



class TexnikKorikViewSet(BaseViewSet):
    queryset = TexnikKorik.objects.prefetch_related("steps").all().order_by("-id")
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = [
        "tarkib__tarkib_raqami",
        "tamir_turi__tamir_nomi",
        "created_by__username",
        "id",
    ]
    pagination_class = CustomPagination
    
    
    def create(self, request, *args, **kwargs):
        # FormData dan ehtiyot_qismlarni JSON ga o'girish
        if 'ehtiyot_qismlar' in request.data and isinstance(request.data['ehtiyot_qismlar'], str):
            try:
                request.data._mutable = True
                request.data['ehtiyot_qismlar'] = json.loads(request.data['ehtiyot_qismlar'])
                request.data._mutable = False
            except Exception as e:
                print(f"❌ JSON parse xatosi: {e}")
                
        print("YUBORILGAN EHTIYOT QISMLAR:", request.data.get("ehtiyot_qismlar"))

        response = super().create(request, *args, **kwargs)

        # CREATE dan keyin yangi yaratilgan korikni to'liq yuklab olish
        if response.status_code == status.HTTP_201_CREATED:
            korik_id = response.data.get('id')
            if korik_id:
                try:
                    korik = (
                        TexnikKorik.objects
                        .select_related("tarkib", "tamir_turi", "created_by")
                        .prefetch_related(
                            "texnikkorikehtiyotqism_set__ehtiyot_qism",
                            "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",
                            "steps"
                        )
                        .get(id=korik_id)
                    )
                    serializer = self.get_serializer(korik)
                    response.data = serializer.data
                except Exception as e:
                    print(f"❌ Korikni yuklab olishda xato: {e}")

        return response
    
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
            return Response(
                {"detail": "Bu korik yakunlangan, yangi step qo'shib bo'lmaydi!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TexnikKorikStepSerializer(
            data=request.data,
            context={"request": request, "korik": korik}  # 👈 korikni contextga qo‘shdik
        )
        serializer.is_valid(raise_exception=True)
        step = serializer.save()  # 👈 korikni save ichida olib beradi
        return Response(TexnikKorikStepSerializer(step).data, status=status.HTTP_201_CREATED)

# class TexnikKorikViewSet(BaseViewSet):
#     queryset = (
#         TexnikKorik.objects
#         .select_related("tarkib", "tamir_turi", "created_by")
#         .prefetch_related(
#             "texnikkorikehtiyotqism_set__ehtiyot_qism",
#             "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",
#             "steps"
#         )
#         .order_by("-id")
#     )
#     serializer_class = TexnikKorikSerializer
#     permission_classes = [IsAuthenticated, IsTexnik]
#     filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
#     search_fields = [
#         "tarkib__tarkib_raqami",
#         "tamir_turi__tamir_nomi",
#         "created_by__username",
#         "id",
#     ]
#     pagination_class = CustomPagination
    
#     def get_queryset(self):
#         user = self.request.user
#         qs = (
#             TexnikKorik.objects
#             .select_related("tarkib", "tamir_turi", "created_by")
#             .prefetch_related(
#                 "texnikkorikehtiyotqism_set__ehtiyot_qism",
#                 "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",
#                 "steps"
#             )
#             .order_by("-id")
#         )

#         if user.role == "texnik" and user.depo:
#             qs = qs.filter(tarkib__depo=user.depo)
#         return qs

#     def create(self, request, *args, **kwargs):
#         """CREATE so'rovini qayta ishlash"""
#         print("🔴 CREATE so'rovi keldi")
#         print(f"Request data: {request.data}")
#         print(f"Request FILES: {request.FILES}")
        
#         # FormData dan ehtiyot_qismlarni JSON ga o'girish
#         if 'ehtiyot_qismlar' in request.data and isinstance(request.data['ehtiyot_qismlar'], str):
#             try:
#                 request.data._mutable = True
#                 request.data['ehtiyot_qismlar'] = json.loads(request.data['ehtiyot_qismlar'])
#                 request.data._mutable = False
#             except Exception as e:
#                 print(f"❌ JSON parse xatosi: {e}")
        
#         response = super().create(request, *args, **kwargs)
        
#         # CREATE dan keyin yangi yaratilgan korikni to'liq yuklab olish
#         if response.status_code == status.HTTP_201_CREATED:
#             korik_id = response.data.get('id')
#             if korik_id:
#                 try:
#                     korik = (
#                         TexnikKorik.objects
#                         .select_related("tarkib", "tamir_turi", "created_by")
#                         .prefetch_related(
#                             "texnikkorikehtiyotqism_set__ehtiyot_qism",
#                             "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",
#                             "steps"
#                         )
#                         .get(id=korik_id)
#                     )
#                     serializer = self.get_serializer(korik)
#                     response.data = serializer.data
#                     print("✅ Response yangilandi")
#                 except Exception as e:
#                     print(f"❌ Korikni yuklab olishda xato: {e}")
        
#         return response

#     @extend_schema(
#         parameters=[
#             OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, description="Step pagination page"),
#             OpenApiParameter(name="limit", type=int, location=OpenApiParameter.QUERY, description="Step page size"),
#             OpenApiParameter(name="search", type=str, location=OpenApiParameter.QUERY, description="Step search"),
#         ]
#     )
#     def retrieve(self, request, *args, **kwargs):
#         """Detail with steps pagination"""
#         return super().retrieve(request, *args, **kwargs)
    
#     @action(detail=True, methods=["post"], url_path="add-step")
#     def add_step(self, request, pk=None):
#         korik = self.get_object()
#         if korik.status == TexnikKorik.Status.BARTARAF_ETILDI:
#             return Response(
#                 {"detail": "Bu korik yakunlangan, yangi step qo'shib bo'lmaydi!"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = TexnikKorikStepSerializer(
#             data=request.data,
#             context={"request": request, "korik": korik}
#         )
#         serializer.is_valid(raise_exception=True)
#         step = serializer.save()
        
#         # Step yaratilgandan keyin to'liq yuklab olish
#         step_with_prefetch = (
#             TexnikKorikStep.objects
#             .select_related("korik", "tamir_turi", "created_by")
#             .prefetch_related("texnikkorikehtiyotqismstep_set__ehtiyot_qism")
#             .get(id=step.id)
#         )
        
#         return Response(
#             TexnikKorikStepSerializer(step_with_prefetch).data, 
#             status=status.HTTP_201_CREATED
#         )

class TexnikKorikStepViewSet(BaseViewSet):
    serializer_class = TexnikKorikStepSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
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
        korik_id = self.request.query_params.get("korik")
        if not korik_id:
            # agar frontend yubormasa ham, context orqali olishga urinamiz
            korik_id = self.kwargs.get("korik_pk") or self.request.data.get("korik")

        if not korik_id:
            raise ValidationError({"korik": "Texnik korik ID aniqlanmadi!"})

        try:
            korik = TexnikKorik.objects.get(id=korik_id)
        except TexnikKorik.DoesNotExist:
            raise ValidationError({"korik": "Bunday Texnik Korik topilmadi!"})

        if korik.status != TexnikKorik.Status.JARAYONDA:
            raise ValidationError({"korik": "Avval Texnik Korik boshlang yoki u tugallangan."})

        serializer.context["korik"] = korik 
        serializer.save()



# class TexnikKorikStepViewSet(BaseViewSet):
#     serializer_class = TexnikKorikStepSerializer
#     permission_classes = [IsAuthenticated, IsTexnik]
#     pagination_class = CustomPagination
#     filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]

#     search_fields = [
#         "id",
#         "kamchiliklar_haqida",
#         "bartaraf_etilgan_kamchiliklar",
#         "created_by__username",
#         "korik__tarkib__tarkib_raqami",
#         "tamir_turi__tamir_nomi",
#     ]
#     filterset_fields = ["korik"]

#     def get_queryset(self):
#         user = self.request.user
#         qs = (
#             TexnikKorikStep.objects
#             .select_related("korik", "tamir_turi", "created_by")
#             .prefetch_related("texnikkorikehtiyotqismstep_set__ehtiyot_qism")
#             .order_by("-id")
#         )

#         # faqat o'z depo uchun texnik
#         if user.role == "texnik" and user.depo:
#             qs = qs.filter(korik__tarkib__depo=user.depo)

#         # query param orqali korik_id
#         korik_id = self.request.query_params.get("korik")
#         if korik_id:
#             qs = qs.filter(korik_id=korik_id)

#         return qs

#     def create(self, request, *args, **kwargs):
        
#         # FormData dan ehtiyot_qismlarni JSON ga o'girish
#         if 'ehtiyot_qismlar' in request.data and isinstance(request.data['ehtiyot_qismlar'], str):
#             try:
#                 request.data._mutable = True
#                 request.data['ehtiyot_qismlar'] = json.loads(request.data['ehtiyot_qismlar'])
#                 request.data._mutable = False
#             except Exception as e:
#                 print(f"❌ STEP JSON parse xatosi: {e}")
        
#         response = super().create(request, *args, **kwargs)
        
#         # CREATE dan keyin yangi yaratilgan stepni to'liq yuklab olish
#         if response.status_code == status.HTTP_201_CREATED:
#             step_id = response.data.get('id')
#             if step_id:
#                 try:
#                     step = (
#                         TexnikKorikStep.objects
#                         .select_related("korik", "tamir_turi", "created_by")
#                         .prefetch_related("texnikkorikehtiyotqismstep_set__ehtiyot_qism")
#                         .get(id=step_id)
#                     )
#                     serializer = self.get_serializer(step)
#                     response.data = serializer.data
#                     print("✅ STEP Response yangilandi")
#                 except Exception as e:
#                     print(f"❌ Stepni yuklab olishda xato: {e}")
        
#         return response

#     def perform_create(self, serializer):
#         korik_id = self.request.query_params.get("korik")
#         if not korik_id:
#             # agar frontend yubormasa ham, context orqali olishga urinamiz
#             korik_id = self.kwargs.get("korik_pk") or self.request.data.get("korik")

#         if not korik_id:
#             raise ValidationError({"korik": "Texnik korik ID aniqlanmadi!"})

#         try:
#             korik = TexnikKorik.objects.get(id=korik_id)
#         except TexnikKorik.DoesNotExist:
#             raise ValidationError({"korik": "Bunday Texnik Korik topilmadi!"})

#         if korik.status != TexnikKorik.Status.JARAYONDA:
#             raise ValidationError({"korik": "Avval Texnik Korik boshlang yoki u tugallangan."})

#         serializer.context["korik"] = korik 
#         serializer.save()





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
    permission_classes = [IsAuthenticated, IsTexnik]
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

class NosozliklarViewSet(BaseViewSet):
    queryset = (
        Nosozliklar.objects
        .select_related("tarkib", "created_by")
        .prefetch_related("ehtiyot_qismlar")
        .order_by("-id")
    )
    serializer_class = NosozliklarSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
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
    
    
    @action(detail=True, methods=["post"], url_path="add-step")
    def add_step(self, request, pk=None):
        nosozlik = self.get_object()
        if nosozlik.status == Nosozliklar.Status.BARTARAF_ETILDI:
            return Response({"detail": "Bu nosozlik yakunlangan, yangi step qo‘shib bo‘lmaydi!"},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = NosozlikStepSerializer(
            data=request.data,
            context={"request": request, "nosozlik": nosozlik}  # 👈 avtomatik context
        )
        serializer.is_valid(raise_exception=True)
        step = serializer.save()
        return Response(NosozlikStepSerializer(step).data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        request = self.request
        password = request.data.get("password")
        if not password or not request.user.check_password(password):
            raise ValidationError({"password": "Parol noto‘g‘ri."})

        yakunlash = serializer.validated_data.pop("yakunlash", False)
        akt_file = serializer.validated_data.pop("akt_file", None)
        ehtiyot_qismlar = serializer.validated_data.pop("ehtiyot_qismlar", [])

        nosozlik = serializer.save(
            created_by=request.user,
            akt_file=akt_file,
            status=Nosozliklar.Status.BARTARAF_ETILDI if yakunlash else Nosozliklar.Status.JARAYONDA
        )

        # 🔹 Ehtiyot qismlarni ishlatish
        for item in ehtiyot_qismlar:
            eq_obj = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if eq_obj:
                NosozlikEhtiyotQism.objects.create(
                    nosozlik=nosozlik, ehtiyot_qism=eq_obj, miqdor=miqdor
                )
                EhtiyotQismHistory.objects.create(
                    ehtiyot_qism=eq_obj,
                    miqdor=-miqdor,
                    created_by=request.user
                )

        # 🔹 Agar yakunlansa → tarkibni ham yangilash
        if yakunlash:
            nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
            nosozlik.bartarafqilingan_vaqti = timezone.now()
            nosozlik.save(update_fields=["status", "bartarafqilingan_vaqti"])

            nosozlik.tarkib.holati = "Soz_holatda"
            nosozlik.tarkib.save(update_fields=["holati"])




# --- Nosozlik Step ViewSet ---
class NosozlikStepViewSet(BaseViewSet):
    serializer_class = NosozlikStepSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
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
        qs = NosozlikStep.objects.all().order_by("-id")
        if user.role == "texnik" and user.depo:
            qs = qs.filter(nosozlik__tarkib__depo=user.depo)

        # frontend → /api/nosozlik-steps/?nosozlik=5
        nosozlik_id = self.request.query_params.get("nosozlik")
        if nosozlik_id:
            qs = qs.filter(nosozlik_id=nosozlik_id)
        return qs

    def perform_create(self, serializer):
        request = self.request
        password = request.data.get("password")
        if not password or not request.user.check_password(password):
            raise ValidationError({"password": "Parol noto‘g‘ri."})

        nosozlik_id = self.request.query_params.get("nosozlik")
        if not nosozlik_id:
            raise ValidationError({"nosozlik": "nosozlik_id yuborilmagan!"})

        try:
            nosozlik = Nosozliklar.objects.get(id=nosozlik_id)
        except Nosozliklar.DoesNotExist:
            raise ValidationError({"nosozlik": "Bunday nosozlik topilmadi!"})

        if nosozlik.status != Nosozliklar.Status.JARAYONDA:
            raise ValidationError({"nosozlik": "Avval nosozlik boshlang yoki u tugallanmagan."})

        # --- Step yaratish ---
        yakunlash = serializer.validated_data.pop("yakunlash", False)
        ehtiyot_qismlar = serializer.validated_data.pop("ehtiyot_qismlar", [])

        step = serializer.save(
            nosozlik=nosozlik,
            created_by=request.user,
            yakunlash=yakunlash
        )

        # --- Step ehtiyot qismlari ---
        for item in ehtiyot_qismlar:
            eq_obj = item.get("ehtiyot_qism")
            miqdor = item.get("miqdor", 1)
            if eq_obj:
                NosozlikEhtiyotQism.objects.create(
                    nosozlik=nosozlik,
                    ehtiyot_qism=eq_obj,
                    miqdor=miqdor,
                    step=step,  # step bilan bog‘lash
                )
                EhtiyotQismHistory.objects.create(
                    ehtiyot_qism=eq_obj,
                    miqdor=-miqdor,
                    created_by=request.user,
                    step=step
                )

        # --- Agar step yakunlansa → asosiy nosozlikni ham yakunlash ---
        if yakunlash:
            nosozlik.status = Nosozliklar.Status.BARTARAF_ETILDI
            nosozlik.bartaraf_qilingan_vaqti = timezone.now()
            nosozlik.save(update_fields=["status", "bartaraf_qilingan_vaqti"])

            nosozlik.tarkib.holati = "Soz_holatda"
            nosozlik.tarkib.save(update_fields=["holati"])



   
   
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

        # ✅ 4) Oxirgi 10 ta nosozlik (eng so‘nggilari)
        last_10_nosozlik = list(
            Nosozliklar.objects.select_related("tarkib")
            .order_by("-created_at")[:10]
            .values(
                "id",
                "tarkib__tarkib_raqami",
                "tarkib__turi",
                "bartaraf_etilgan_nosozliklar",
                "created_at"
            )
        )

        korik_counts = (
            TexnikKorik.objects.values("tarkib__id", "tarkib__tarkib_raqami", "tarkib__turi")
            .annotate(total=Count("id"))
        )
        nosozlik_counts = (
            Nosozliklar.objects.values("tarkib__id", "tarkib__tarkib_raqami", "tarkib__turi")
            .annotate(total=Count("id"))
        )

        combined = {}
        for item in korik_counts:
            tid = item["tarkib__id"]
            combined[tid] = {
                "id": tid,
                "raqam": item["tarkib__tarkib_raqami"],
                "turi": item["tarkib__turi"],
                "total": combined.get(tid, {}).get("total", 0) + item["total"],
            }

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

        top_5_tarkib = sorted(combined.values(), key=lambda x: x["total"], reverse=True)[:5]

        top_10_ehtiyot_qism = list(
        EhtiyotQismlari.objects.annotate(
            qoshilgan=Sum("ehtiyotqism_hist__miqdor"),
            ishlatilgan=(
                Sum("texnikkorikehtiyotqism__miqdor") +
                Sum("texnikkorikehtiyotqismstep__miqdor") +
                Sum("nosozlikehtiyotqism__miqdor") +
                Sum("nosozlikehtiyotqismstep__miqdor")
            )
        )
        .annotate(
            jami_miqdor=F("qoshilgan") - F("ishlatilgan")
        )
        .values("id", "ehtiyotqism_nomi", "birligi", "jami_miqdor")
        .order_by("jami_miqdor")[:10]
    )

        return Response({
            "total_korik": total_korik,
            "total_nosozlik": total_nosozlik,
            "last_month_korik": last_month_korik,
            "last_10_nosozlik": last_10_nosozlik,
            "top_5_tarkib": top_5_tarkib,
            "top_10_ehtiyot_qism": top_10_ehtiyot_qism,
        })

class TarkibDetailViewSet(BaseViewSet):
    permission_classes = [IsAuthenticated, IsTexnik, IsMonitoringReadOnly]

    def get_queryset(self):
        return HarakatTarkibi.objects.filter(is_active=True)

    def get_serializer(self, *args, **kwargs):
        return TarkibFullDetailSerializer(*args, **kwargs)

    def check_permissions(self, request):
        if request.user.is_superuser:
            return
        return super().check_permissions(request)

    def retrieve(self, request, pk=None):
        tarkib = self.get_queryset().filter(pk=pk).first()
        if not tarkib:
            return Response({"detail": "Tarkib topilmadi."}, status=404)

        texnik_koriklar = TexnikKorik.objects.filter(tarkib=tarkib)
        tamir_turi_count = texnik_koriklar.values('tamir_turi__tamir_nomi').annotate(count=Count('id'))
        texnik_korik_summary = [{"tamir_turi": t["tamir_turi__tamir_nomi"], "soni": t["count"]} for t in tamir_turi_count]

        nosozliklar = Nosozliklar.objects.filter(tarkib=tarkib)
        nosozlik_data = NosozlikDetailForStepSerializer(nosozliklar, many=True, context={'request': request}).data

        response_data = {
            "tarkib_id": tarkib.id,
            "tarkib_raqami": tarkib.tarkib_raqami,
            "depo_nomi": tarkib.depo.qisqacha_nomi if tarkib.depo else None,
            "guruhi": tarkib.guruhi,
            "turi": tarkib.turi,
            "holati": tarkib.holati,
            "tarkib_photo": request.build_absolute_uri(tarkib.image.url) if getattr(tarkib, 'image', None) else None,
            "ishga_tushgan_vaqti": tarkib.ishga_tushgan_vaqti,
            "eksplutatsiya_vaqti": tarkib.eksplutatsiya_vaqti,
            "created_at": tarkib.created_at,
            "previous_version": tarkib.previous_version.id if getattr(tarkib, 'previous_version', None) else None,
            "created_by": tarkib.created_by.username if getattr(tarkib, 'created_by', None) else None,
            "is_active": tarkib.is_active,
            "texnik_korik_soni_turi": texnik_korik_summary,
            "nosozliklar": nosozlik_data,
        }
        return Response(response_data)

    @action(detail=True, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request, pk=None):
        tarkib = self.get_queryset().filter(pk=pk).first()
        if not tarkib:
            return Response({"detail": "Tarkib topilmadi."}, status=404)

        texnik_koriklar = TexnikKorik.objects.filter(tarkib=tarkib)
        tamir_turi_count = texnik_koriklar.values('tamir_turi__tamir_nomi').annotate(count=Count('id'))
        texnik_korik_summary = [[t["tamir_turi__tamir_nomi"], t["count"]] for t in tamir_turi_count]

        nosozliklar = Nosozliklar.objects.filter(tarkib=tarkib)
        nosozlik_data = [[n.id, n.nosozliklar_haqida, n.bartaraf_etilgan_nosozliklar, n.status] for n in nosozliklar]

        # PDF tayyorlash
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Tarkib_{tarkib.id}.pdf"'
        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        # --- Tarkib umumiy ma'lumotlari ---
        elements.append(Paragraph(f"Tarkib #{tarkib.id} ({tarkib.tarkib_raqami})", styles['Heading2']))
        elements.append(Paragraph(f"Depo: {tarkib.depo.qisqacha_nomi if tarkib.depo else ''}", styles['Normal']))
        elements.append(Paragraph(f"Guruhi: {tarkib.guruhi}, Turi: {tarkib.turi}", styles['Normal']))
        elements.append(Paragraph(f"Holati: {tarkib.holati}", styles['Normal']))
        elements.append(Paragraph(f"Ishga tushgan vaqti: {tarkib.ishga_tushgan_vaqti}", styles['Normal']))
        elements.append(Paragraph(f"Eksplutatsiya vaqti: {tarkib.eksplutatsiya_vaqti}", styles['Normal']))
        elements.append(Paragraph(f"Created by: {tarkib.created_by.username if tarkib.created_by else ''}", styles['Normal']))
        elements.append(Spacer(1, 12))

        # --- Tarkib rasmi ---
        if getattr(tarkib, 'image', None):
            try:
                img_path = tarkib.image.path
                img = Image(img_path, width=12*cm, height=8*cm)  # o‘lchamini sozlash mumkin
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 12))
            except:
                pass  # agar rasm topilmasa, o'tkazib yuboradi

        # --- Texnik koriklar jadvali ---
        if texnik_korik_summary:
            elements.append(Paragraph("Texnik koriklar soni har bir tamir turida", styles['Heading3']))
            table_data = [["Tamir turi", "Soni"]] + texnik_korik_summary
            t = Table(table_data, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 12))

        # --- Nosozliklar jadvali ---
        if nosozlik_data:
            elements.append(Paragraph("Nosozliklar batafsil", styles['Heading3']))
            table_data = [["ID", "Nosozliklar", "Bartaf etilgan", "Holati"]] + nosozlik_data
            t = Table(table_data, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('ALIGN', (1,1), (-1,-1), 'LEFT'),
            ]))
            elements.append(t)

        doc.build(elements)
        return response

    @action(detail=True, methods=["get"], url_path="export-excel")
    def export_excel(self, request, pk=None):
        tarkib = self.get_queryset().filter(pk=pk).first()
        if not tarkib:
            return Response({"detail": "Tarkib topilmadi."}, status=404)

        texnik_koriklar = TexnikKorik.objects.filter(tarkib=tarkib)
        tamir_turi_count = texnik_koriklar.values('tamir_turi__tamir_nomi').annotate(count=Count('id'))

        nosozliklar = Nosozliklar.objects.filter(tarkib=tarkib)

        wb = Workbook()
        ws = wb.active
        ws.title = f"Tarkib_{tarkib.id}"

        # --- Tarkib umumiy ma'lumotlari ---
        general_info = [
            ["Tarkib ID", tarkib.id],
            ["Tarkib raqami", tarkib.tarkib_raqami],
            ["Depo", tarkib.depo.qisqacha_nomi if tarkib.depo else ""],
            ["Guruhi", tarkib.guruhi],
            ["Turi", tarkib.turi],
            ["Holati", tarkib.holati],
            ["Ishga tushgan vaqti", tarkib.ishga_tushgan_vaqti],
            ["Eksplutatsiya vaqti", tarkib.eksplutatsiya_vaqti],
            ["Created by", tarkib.created_by.username if tarkib.created_by else ""],
        ]
        for row in general_info:
            ws.append(row)
        ws.append([])  # bo‘sh qator

        # --- Texnik koriklar jadvali ---
        ws.append(["Texnik koriklar (soni tamir turi bo‘yicha)"])
        ws.append(["Tamir turi", "Soni"])
        for t in tamir_turi_count:
            ws.append([t['tamir_turi__tamir_nomi'], t['count']])
        ws.append([])

        # --- Nosozliklar jadvali ---
        ws.append(["Nosozliklar batafsil"])
        ws.append(["ID", "Nosozliklar", "Bartaf etilgan", "Holati"])
        for n in nosozliklar:
            ws.append([n.id, n.nosozliklar_haqida, n.bartaraf_etilgan_nosozliklar, n.status])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="Tarkib_{tarkib.id}.xlsx"'
        wb.save(response)
        return response
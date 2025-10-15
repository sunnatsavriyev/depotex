from rest_framework import viewsets, status, filters, mixins, generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from .models import (
    TamirTuri, ElektroDepo, EhtiyotQismlari,
    HarakatTarkibi, TexnikKorik, CustomUser, Nosozliklar, NosozlikEhtiyotQism, TexnikKorikStep,KunlikYurish,
    Vagon,EhtiyotQismHistory, TexnikKorikEhtiyotQism,NosozlikTuri,NosozlikNotification,TexnikKorikJadval,
)
from .serializers import (
    TamirTuriSerializer, ElektroDepoSerializer,TexnikKorikJadvalSerializer,
    EhtiyotQismlariSerializer, HarakatTarkibiSerializer,
    TexnikKorikSerializer, UserSerializer, NosozliklarSerializer, TexnikKorikStepSerializer, NosozlikStepSerializer,
    NosozlikStep,KunlikYurishSerializer,VagonSerializer,NosozlikTuriSerializer,NosozlikNotificationSerializer,
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
from .permissions import IsMonitoringReadOnly, IsTexnik, IsSkladchiOrReadOnly
import json
from reportlab.lib.units import cm
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from io import BytesIO
import qrcode
from collections import defaultdict
import pandas as pd
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
    permission_classes = [IsAuthenticated, IsSkladchiOrReadOnly,IsMonitoringReadOnly,IsTexnik]
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

            # Asosiy jadval
            table_data = [[Paragraph("<b>Maydon</b>", field_style), Paragraph("<b>Qiymat</b>", field_style)]]
            for key, value in item.items():
                if key in ["image", "steps", "vagonlar", "ehtiyot_qismlar_detail"]:
                    continue
                table_data.append([Paragraph(str(key), field_style), Paragraph(str(value), field_style)])

            # Ehtiyot qismlarni birlashtirib yozish
            if "ehtiyot_qismlar_detail" in item and isinstance(item["ehtiyot_qismlar_detail"], list):
                qismlar_list = []
                for part in item["ehtiyot_qismlar_detail"]:
                    nomi = part.get("ehtiyot_qism_nomi", "")
                    miqdor = part.get("ishlatilgan_miqdor", 0)
                    birligi = part.get("birligi", "")
                    qismlar_list.append(f"{nomi}: {miqdor} {birligi}")
                table_data.append([Paragraph("Ehtiyot qismlar", field_style), Paragraph(", ".join(qismlar_list), field_style)])

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

            # Steps jadvali (alohida)
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
    def get_permissions(self):
        # READ (detail view) uchun public; boshqa actionlar uchun normal role-based permissionlar qoʻyiladi
        if self.action in ['retrieve', 'list']:
            return [AllowAny()]
        return [IsAuthenticated()] 
    

class EhtiyotQismlariViewSet(viewsets.ModelViewSet):
    queryset = EhtiyotQismlari.objects.all().order_by('-id')
    serializer_class = EhtiyotQismlariSerializer
    permission_classes = [IsAuthenticated, IsSkladchiOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['ehtiyotqism_nomi', 'nomenklatura_raqami']
    ordering_fields = ['id', 'nomenklatura_raqami']
    pagination_class = CustomPagination
    
    
class EhtiyotQismMiqdorListAPIView(APIView):
        permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated, IsSkladchiOrReadOnly]

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
    search_fields = ['guruhi','tarkib_raqami','turi','ishga_tushgan_vaqti','eksplutatsiya_vaqti','holati']   
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
    search_fields = ['guruhi', 'tarkib_raqami', 'turi', 'ishga_tushgan_vaqti', 'eksplutatsiya_vaqti','holati']
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
    basename = "harakat-tarkibi-active"  # ✅ Bo‘sh joysiz
    permission_classes = [IsAuthenticated, IsTexnik]
    require_login_fields = False
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi', 'tarkib_raqami', 'turi', 'ishga_tushgan_vaqti', 'eksplutatsiya_vaqti', 'holati']
    ordering_fields = ['ishga_tushgan_vaqti', 'id']
    filterset_fields = ['depo']



class HarakatTarkibiHolatStatistikaViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsTexnik]

    # --- Asosiy statistikani chiqarish ---
    def list(self, request):
        queryset = HarakatTarkibi.objects.filter(is_active=True)

        nosozlikda = queryset.filter(holati="Nosozlikda")
        texnik_korikda = queryset.filter(holati="Texnik ko‘rikda")

        nosozlik_serializer = HarakatTarkibiActiveSerializer(nosozlikda, many=True)
        texnik_serializer = HarakatTarkibiActiveSerializer(texnik_korikda, many=True)

        return Response({
            "nosozlikda_soni": nosozlikda.count(),
            "nosozlikda_tarkiblar": nosozlik_serializer.data,
            "texnik_korikda_soni": texnik_korikda.count(),
            "texnik_korikda_tarkiblar": texnik_serializer.data,
        })

    # --- PDF EXPORT ---
    @action(detail=False, methods=["get"], url_path="export-nosozlikda-pdf")
    def export_nosozlikda_pdf(self, request):
        queryset = HarakatTarkibi.objects.filter(is_active=True, holati="Nosozlikda")

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
        elements = []

        title = Paragraph(
            "<b><font size=14 color='red'>Nosozlikda bo‘lgan tarkiblar ro‘yxati</font></b>",
            ParagraphStyle('title', alignment=1)
        )
        elements += [title, Spacer(1, 10)]

        data = [["#", "Tarkib raqami", "Turi", "Masofa", "Holati"]]
        for i, obj in enumerate(queryset, 1):
            data.append([
                i,
                str(obj.tarkib_raqami or "-"),
                str(obj.turi or "-"),
                str(getattr(obj, 'masofa', "-")),
                str(obj.holati or "-"),
            ])

        table = Table(data, hAlign='CENTER', colWidths=[1*cm, 4*cm, 4*cm, 3*cm, 5*cm])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.darkblue),  # 🔹 Header matnini darkblue qilish
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),              # Headerlarni o‘rtaga tekislash
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),            # Vertikal markazlashtirish
            ('FONTSIZE', (0, 0), (-1, 0), 11),                 # Header matn o‘lchami
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),   # Headerni qalin qilish
        ]))
        elements.append(table)

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"Nosozlikda_Tarkiblar_{datetime.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # --- PDF: Texnik ko‘rikdagilar ---
    @action(detail=False, methods=["get"], url_path="export-texnik-pdf")
    def export_texnik_pdf(self, request):
        queryset = HarakatTarkibi.objects.filter(is_active=True, holati="Texnik ko‘rikda")

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
        elements = []

        title = Paragraph(
            "<b><font size=14 color='blue'>Texnik ko‘rikda bo‘lgan tarkiblar ro‘yxati</font></b>",
            ParagraphStyle('title', alignment=1)
        )
        elements += [title, Spacer(1, 10)]

        data = [["#", "Tarkib raqami", "Turi", "Masofa", "Holati"]]
        for i, obj in enumerate(queryset, 1):
            data.append([
                i,
                str(obj.tarkib_raqami or "-"),
                str(obj.turi or "-"),
                str(getattr(obj, 'masofa', "-")),
                str(obj.holati or "-"),
            ])

        table = Table(data, hAlign='CENTER', colWidths=[1*cm, 4*cm, 4*cm, 3*cm, 5*cm])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ]))
        elements.append(table)

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf, content_type="application/pdf")
        filename = f"TexnikKorik_Tarkiblar_{datetime.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # --- EXCEL EXPORT ---
    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        queryset = HarakatTarkibi.objects.filter(is_active=True)
        nosozlikda = queryset.filter(holati="Nosozlikda")
        texnik_korikda = queryset.filter(holati="Texnik ko‘rikda")

        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Nosozlikda"
        ws2 = wb.create_sheet("Texnik ko‘rikda")

        headers = ["#", "Tarkib raqami", "Turi", "Masofa", "Holati"]

        for sheet, data in [(ws1, nosozlikda), (ws2, texnik_korikda)]:
            sheet.append(headers)
            for i, obj in enumerate(data, 1):
                sheet.append([
                    i,
                    str(obj.tarkib_raqami or "-"),
                    str(obj.turi or "-"),
                    str(getattr(obj, 'masofa', "-")),
                    str(obj.holati or "-"),
                ])
            for col in range(1, len(headers) + 1):
                sheet.column_dimensions[get_column_letter(col)].width = 20

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"HarakatTarkibi_Statistika_{datetime.now().strftime('%Y%m%d')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response




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
            "texnikkorikehtiyotqism_set__ehtiyot_qism",  
            "steps__texnikkorikehtiyotqismstep_set__ehtiyot_qism",  
            "steps" 
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
        




class NosozliklarFilter(django_filters.FilterSet):
    nosozlik_turi = django_filters.CharFilter(
        field_name="nosozliklar_haqida__nosozlik_turi",
        lookup_expr="icontains"
    )
    tarkib_raqami = django_filters.CharFilter(
        field_name="tarkib__tarkib_raqami",
        lookup_expr="icontains"
    )

    class Meta:
        model = Nosozliklar
        fields = ["nosozlik_turi", "tarkib_raqami", "status"]


class NosozlikStepFilter(django_filters.FilterSet):
    nosozlik_turi = django_filters.CharFilter(
        field_name="nosozlik__nosozliklar_haqida__nosozlik_turi",
        lookup_expr="icontains"
    )
    bartaraf_etilgan_nosozliklar = django_filters.CharFilter(
        lookup_expr="icontains"
    )
    tamir_turi = django_filters.CharFilter(
        field_name="tamir_turi__tamir_nomi",
        lookup_expr="icontains"
    )

    class Meta:
        model = NosozlikStep
        fields = ["nosozlik_turi", "bartaraf_etilgan_nosozliklar", "tamir_turi", "status"]
        
        
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


class NosozlikTuriViewSet(viewsets.ModelViewSet):
    queryset = NosozlikTuri.objects.all().order_by("-id")
    serializer_class = NosozlikTuriSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
    
    

class NosozliklarViewSet(BaseViewSet):
    queryset = (
        Nosozliklar.objects
        .select_related("tarkib", "created_by")
        .prefetch_related("steps")
        .order_by("-id")
    )
    serializer_class = NosozliklarSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = NosozliklarFilter
    search_fields = [
        "nosozliklar_haqida__nosozliklar_haqida",
        "bartaraf_etilgan_nosozliklar",
        "tarkib__tarkib_raqami",
        "created_by__username",
        "id",
    ]
    pagination_class = CustomPagination

    def create(self, request, *args, **kwargs):
        # FormData dan ehtiyot qismlarni JSON formatga o‘girish
        if 'ehtiyot_qismlar' in request.data and isinstance(request.data['ehtiyot_qismlar'], str):
            try:
                request.data._mutable = True
                request.data['ehtiyot_qismlar'] = json.loads(request.data['ehtiyot_qismlar'])
                request.data._mutable = False
            except Exception as e:
                print(f"❌ JSON parse xatosi: {e}")

        print("YUBORILGAN NOSOZLIK EHTIYOT QISMLAR:", request.data.get("ehtiyot_qismlar"))

        response = super().create(request, *args, **kwargs)

        # CREATE dan keyin yangilangan obyektni to‘liq qaytarish
        if response.status_code == status.HTTP_201_CREATED:
            nosozlik_id = response.data.get("id")
            if nosozlik_id:
                try:
                    nosozlik = (
                        Nosozliklar.objects
                        .select_related("tarkib", "created_by")
                        .prefetch_related(
                            "ehtiyot_qism_aloqalari__ehtiyot_qism",
                            "steps__ehtiyot_qismlar_step__ehtiyot_qism",
                            "steps"
                        )
                        .get(id=nosozlik_id)
                    )
                    serializer = self.get_serializer(nosozlik)
                    response.data = serializer.data
                except Exception as e:
                    print(f"❌ Nosozlikni yuklashda xato: {e}")

        return response

    def get_queryset(self):
        user = self.request.user
        qs = Nosozliklar.objects.prefetch_related("steps").order_by("-id")
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
        nosozlik = self.get_object()
        if nosozlik.status == Nosozliklar.Status.BARTARAF_ETILDI:
            return Response(
                {"detail": "Bu nosozlik yakunlangan, yangi step qo‘shib bo‘lmaydi!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = NosozlikStepSerializer(
            data=request.data,
            context={"request": request, "nosozlik": nosozlik}
        )
        serializer.is_valid(raise_exception=True)
        step = serializer.save()
        return Response(NosozlikStepSerializer(step).data, status=status.HTTP_201_CREATED)



class NosozlikStepViewSet(BaseViewSet):
    serializer_class = NosozlikStepSerializer
    permission_classes = [IsAuthenticated, IsTexnik]
    pagination_class = CustomPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_class = NosozlikStepFilter
    search_fields = [
        "id",
        "nosozliklar_haqida__nosozliklar_haqida",
        "bartaraf_etilgan_nosozliklar",
        "created_by__username",
        "nosozlik__tarkib__tarkib_raqami",
    ]
    filterset_fields = ["nosozlik"]

    def get_queryset(self):
        user = self.request.user
        qs = NosozlikStep.objects.all().order_by("-id")

        if user.role == "texnik" and user.depo:
            qs = qs.filter(nosozlik__tarkib__depo=user.depo)

        nosozlik_id = self.request.query_params.get("nosozlik")
        if nosozlik_id:
            qs = qs.filter(nosozlik_id=nosozlik_id)
        return qs

    def perform_create(self, serializer):
        nosozlik_id = self.request.query_params.get("nosozlik")
        if not nosozlik_id:
            nosozlik_id = self.kwargs.get("nosozlik_pk") or self.request.data.get("nosozlik")

        if not nosozlik_id:
            raise ValidationError({"nosozlik": "Nosozlik ID aniqlanmadi!"})

        try:
            nosozlik = Nosozliklar.objects.get(id=nosozlik_id)
        except Nosozliklar.DoesNotExist:
            raise ValidationError({"nosozlik": "Bunday Nosozlik topilmadi!"})

        if nosozlik.status != Nosozliklar.Status.JARAYONDA:
            raise ValidationError({"nosozlik": "Avval Nosozlik boshlang yoki u yakunlangan."})

        serializer.context["nosozlik"] = nosozlik
        serializer.save()



class NosozlikNotificationListView(generics.ListAPIView):
    queryset = NosozlikNotification.objects.all().order_by("-last_occurrence")
    serializer_class = NosozlikNotificationSerializer
 
 
   
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
                "nosozliklar_haqida__nosozlik_turi",  
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
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['guruhi','holati']

    def get_queryset(self):
        return HarakatTarkibi.objects.all()

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
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from io import BytesIO
        import qrcode
        from datetime import datetime

        tarkib = self.get_queryset().filter(pk=pk).first()
        if not tarkib:
            return Response({"detail": "Tarkib topilmadi."}, status=404)

        texnik_koriklar = TexnikKorik.objects.filter(tarkib=tarkib)
        nosozliklar = Nosozliklar.objects.filter(tarkib=tarkib).order_by('-id')[:5]

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Tarkib_{tarkib.tarkib_raqami}.pdf"'

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=1 * cm,
            bottomMargin=1 * cm,
            leftMargin=1 * cm,
            rightMargin=1 * cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        # --- Sarlavha ---
        title = Paragraph(
            f"<b>{tarkib.tarkib_raqami}</b><br/>"
            f"<b>Harakat tarkibining texnik ko‘rsatkichlari bo‘yicha to‘liq ma’lumot</b>",
            ParagraphStyle('title', parent=styles['Title'], alignment=1, leading=18, textColor=colors.darkblue),
        )
        elements.append(title)
        elements.append(Spacer(1, 10))

        # --- Rasm ---
        if getattr(tarkib, 'image', None):
            try:
                img = Image(tarkib.image.path, width=18.5 * cm, height=9.5 * cm)
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 10))
            except:
                pass

        # --- Ekspluatatsiya ma’lumotlari ---
        ekspl_data = [
            [
                Paragraph(f"<font color='red'><b>{h}</b></font>", styles['Normal'])
                for h in ["Ekspluatatsiyaga qo‘yilgan sana", "Turi", "Nomeri", "Masofa", "Hozirgi holati"]
            ],
            [
                Paragraph(f"<b>{tarkib.ishga_tushgan_vaqti.strftime('%d-%m-%Y') if tarkib.ishga_tushgan_vaqti else '-'}</b>", 
                            styles['Normal']),
                Paragraph(f"<b>{tarkib.guruhi or '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{tarkib.tarkib_raqami or '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{str(getattr(tarkib, 'masofa', '–'))}</b>", styles['Normal']),
                Paragraph(f"<b>{tarkib.holati or '-'}</b>", styles['Normal']),
            ],
        ]

        # Jadval eni sahifa eni bo‘ylab teng bo‘lishi uchun
        full_width = A4[0] - 2 * cm

        # Ustun kengliklarini belgilash (Nomeri ustunini biroz kengroq qilamiz)
        col_widths = [
            full_width * 0.18,  # Ekspluatatsiya sana
            full_width * 0.18,  # Turi
            full_width * 0.26,  # Nomeri (kattaroq)
            full_width * 0.18,  # Masofa
            full_width * 0.20,  # Hozirgi holati
        ]

        ekspl_table = Table(ekspl_data, hAlign='CENTER', colWidths=col_widths)
        ekspl_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))

        elements.append(ekspl_table)
        elements.append(Spacer(1, 12))

        # --- Texnik ko‘riklar tarixi ---
        elements.append(Paragraph(
            "<b><font color='red' size=12>Texnik ko‘riklar tarixi</font></b>",
            ParagraphStyle('h3', alignment=1)
        ))
        elements.append(Spacer(1, 6))

        # Barcha tamir turlarini bazadan olish
        from home.models import TamirTuri
        tamir_turlari = TamirTuri.objects.all().values_list('tamir_nomi', flat=True)

        # Har bir tamir turi uchun hisob
        korik_counts = {t: 0 for t in tamir_turlari}
        for tk in texnik_koriklar:
            if tk.tamir_turi and tk.tamir_turi.tamir_nomi in korik_counts:
                korik_counts[tk.tamir_turi.tamir_nomi] += 1

        # Jadval uchun ma’lumot tayyorlash
        korik_data = [[Paragraph("<b><font color='black'>Ta’mir turi</font></b>", styles['Normal'])] +
                    [Paragraph(f"<font color='red'><b>{t}</b></font>", styles['Normal']) for t in tamir_turlari]]

        korik_values = [
            Paragraph(f"<b><font color='blue'>{korik_counts[t]}</font></b>", styles['Normal'])
            if korik_counts[t] > 0 else Paragraph("<b>-</b>", styles['Normal'])
            for t in tamir_turlari
        ]

        korik_data.append([Paragraph("<b>Soni</b>", styles['Normal'])] + korik_values)

        # Jadval kengliklarini moslashtirish (dinamik)
        col_width = (A4[0] - 2 * cm) / (len(tamir_turlari) + 1)
        korik_table = Table(korik_data, hAlign='CENTER', colWidths=[col_width] * (len(tamir_turlari) + 1))

        korik_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(korik_table)
        elements.append(Spacer(1, 12))

        # --- Nosozliklar tarixi ---
        elements.append(Paragraph("<b><font color='red' size=12>Nosozliklar tarixi</font></b>",
                                ParagraphStyle('h3', alignment=1)))
        elements.append(Spacer(1, 6))

        nosoz_data = [[
            Paragraph(f"<font color='darkblue'><b>{h}</b></font>", styles['Normal'])
            for h in ["No", "Nosozlik sababi", "Aniqlangan sana", "Bartarf etilgan sana"]
        ]]

        for i, n in enumerate(nosozliklar, 1):
            aniqlangan = getattr(n, 'aniqlangan_vaqti', None)
            bartaraf = getattr(n, 'bartaraf_etilgan_vaqti', None)
            aniqlangan_str = aniqlangan.strftime("%Y-%m-%d") if isinstance(aniqlangan, datetime) else "-"
            bartaraf_str = bartaraf.strftime("%Y-%m-%d") if isinstance(bartaraf, datetime) else "-"

            nosoz_data.append([
                Paragraph(f"<b>{str(i)}</b>", styles['Normal']),
                Paragraph(f"<b>{n.nosozliklar_haqida or '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{aniqlangan_str}</b>", styles['Normal']),
                Paragraph(f"<b>{bartaraf_str}</b>", styles['Normal']),
            ])

        nosoz_table = Table(nosoz_data, hAlign='CENTER', colWidths=[1.5 * cm, 10 * cm, 3.5 * cm, 3.5 * cm])
        nosoz_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(nosoz_table)
        elements.append(Spacer(1, 15))

        # --- QR kod va pastki fon ---
        qr_url = f"https://depo-main.vercel.app/depo/{tarkib.id}"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=3, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_img = Image(qr_buffer, width=2.5 * cm, height=2.5 * cm)
        qr_img.hAlign = 'RIGHT'

        footer_text = Paragraph(
            """<font size=9><b>
            Hujjatning haqiqiyligini tekshirish uchun QR kodni skanerlang.<br/>
            <font color='blue'><b>depo.tm1.uz</b></font> sayti orqali tasdiqlangan.<br/>
            Ushbu hisobotdagi barcha ma’lumotlar uchun xodim mas’uldir.
            </b></font>""",
            ParagraphStyle('footer', parent=styles['Normal'], alignment=0, leading=12),
        )

        footer_table = Table([[footer_text, qr_img]], colWidths=[14 * cm, 3 * cm])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ]))
        elements.append(footer_table)

        # --- Sahifa border ---
        def draw_border(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.rect(0.8 * cm, 0.8 * cm, A4[0] - 1.6 * cm, A4[1] - 1.6 * cm)
            canvas.restoreState()

        doc.build(elements, onFirstPage=draw_border, onLaterPages=draw_border)

        buffer.seek(0)
        response.write(buffer.getvalue())
        buffer.close()
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
   
   
   

class TexnikKorikByTypeViewSet(BaseViewSet):
    queryset = TexnikKorik.objects.select_related("tarkib", "tamir_turi", "created_by")
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated]

    # -------- PDF EXPORT --------
    @action(detail=False, methods=["get"], url_path=r"(?P<tarkib_id>\d+)/(?P<tamir_turi_id>\d+)/export-pdf")
    def export_pdf(self, request, tarkib_id=None, tamir_turi_id=None):
        queryset = self.get_queryset().filter(tarkib_id=tarkib_id, tamir_turi_id=tamir_turi_id)
        if not queryset.exists():
            return HttpResponse("Ma'lumot topilmadi", status=404)

        tarkib = queryset.first().tarkib
        tamir_turi = queryset.first().tamir_turi

        buffer = BytesIO()
        response = HttpResponse(content_type="application/pdf")
        filename = f"{tarkib.tarkib_raqami}_{tamir_turi.tamir_nomi}_koriklar.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
        styles = getSampleStyleSheet()
        elements = []
        title_text = (
            f"<b><font color='red'>{tarkib.tarkib_raqami}</font></b> harakat tarkibining "
            f"<br/><b><font color='red'>{tamir_turi.tamir_nomi}</font></b> texnik ko'rigi bo‘yicha to'liq ma'lumot"
        )
        # --- Sarlavha ---
        title = Paragraph(
            title_text,
            ParagraphStyle('title', parent=styles['Title'], alignment=1, textColor=colors.darkblue),
        )
        elements.append(title)
        elements.append(Spacer(1, 10))

        # --- Rasm ---
        if getattr(tarkib, 'image', None):
            try:
                img = Image(tarkib.image.path, width=15.5 * cm, height=6.5 * cm)
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 10))
            except:
                pass

        # --- Ekspluatatsiya ma’lumotlari ---
        ekspl_data = [
            [
                Paragraph(f"<font color='red'><b>{h}</b></font>", styles['Normal'])
                for h in ["Ekspluatatsiyaga qo‘yilgan sana", "Turi", "Nomeri", "Masofa", "Hozirgi holati"]
            ],
            [
                Paragraph(f"<b>{tarkib.ishga_tushgan_vaqti.strftime('%d-%m-%Y') if tarkib.ishga_tushgan_vaqti else '-'}</b>", 
                            styles['Normal']),
                Paragraph(f"<b>{tarkib.guruhi or '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{tarkib.tarkib_raqami or '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{str(getattr(tarkib, 'masofa', '–'))}</b>", styles['Normal']),
                Paragraph(f"<b>{tarkib.holati or '-'}</b>", styles['Normal']),
            ],
        ]

        # Jadval eni sahifa eni bo‘ylab teng bo‘lishi uchun
        full_width = A4[0] - 2 * cm

        # Ustun kengliklarini belgilash (Nomeri ustunini biroz kengroq qilamiz)
        col_widths = [
            full_width * 0.18,  # Ekspluatatsiya sana
            full_width * 0.18,  # Turi
            full_width * 0.26,  # Nomeri (kattaroq)
            full_width * 0.18,  # Masofa
            full_width * 0.20,  # Hozirgi holati
        ]

        ekspl_table = Table(ekspl_data, hAlign='CENTER', colWidths=col_widths)
        ekspl_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))

        elements.append(ekspl_table)
        elements.append(Spacer(1, 12))

        # --- Texnik ko‘riklar tarixi (Soddalashtirilgan) ---
        history_title = Paragraph(
            f"<b><font color='red'>{tamir_turi.tamir_nomi} texnik ko'rigi tarixi</font></b>",
            ParagraphStyle('h3', alignment=1)
        )
        elements.append(history_title)
        elements.append(Spacer(1, 6))

        data = [[
            Paragraph(f"<font color='darkblue'><b>{h}</b></font>", styles['Normal'])
            for h in ["No", "Kirgan sana", "Chiqqan sana", "Kimlar qilgani"]
        ]]

        for i, k in enumerate(queryset, 1):
            users = []
            if getattr(k, "step_yozgan", None):
                users.append(k.step_yozgan.username)
            if getattr(k, "yakunlagan", None):
                users.append(k.yakunlagan.username)
            if getattr(k, "created_by", None):
                users.append(k.created_by.username)
            users_str = ", ".join(users) if users else "-"

            data.append([
                i,
                k.kirgan_vaqti.strftime("%d-%m-%Y %H:%M") if k.kirgan_vaqti else "-",
                k.chiqqan_vaqti.strftime("%d-%m-%Y %H:%M") if k.chiqqan_vaqti else "-",
                users_str
            ])

        # Jadval ustunlarini full_width ga tenglab berish
        col_widths_history = [full_width * 0.1, full_width * 0.3, full_width * 0.3, full_width * 0.3]

        history_table = Table(data, hAlign='CENTER', colWidths=col_widths_history)
        history_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.6, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(history_table)
        elements.append(Spacer(1, 12))

        # --- QR kod ---
        qr_url = f"https://depo-main.vercel.app/depo/{tarkib.id}"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=3, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_img = Image(qr_buffer, width=2.5 * cm, height=2.5 * cm)
        qr_img.hAlign = 'RIGHT'

        footer_text = Paragraph(
            """<font size=9><b>
            Hujjatning haqiqiyligini tekshirish uchun QR kodni skanerlang.<br/>
            <font color='blue'><b>depo.tm1.uz</b></font> sayti orqali tasdiqlangan.<br/>
            Ushbu hisobotdagi barcha ma’lumotlar uchun xodim mas’uldir.
            </b></font>""",
            ParagraphStyle('footer', parent=styles['Normal'], alignment=0, leading=12),
        )

        footer_table = Table([[footer_text, qr_img]], colWidths=[14 * cm, 3 * cm])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ]))
        elements.append(footer_table)

        # --- Sahifa border ---
        def draw_border(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.rect(0.8 * cm, 0.8 * cm, A4[0] - 1.6 * cm, A4[1] - 1.6 * cm)
            canvas.restoreState()

        doc.build(elements, onFirstPage=draw_border, onLaterPages=draw_border)

        buffer.seek(0)
        response.write(buffer.getvalue())
        buffer.close()
        return response


    # -------- EXCEL EXPORT --------
    @action(detail=False, methods=["get"], url_path=r"(?P<tarkib_id>\d+)/(?P<tamir_turi_id>\d+)/export-excel")
    def export_excel(self, request, tarkib_id=None, tamir_turi_id=None):
        queryset = self.get_queryset().filter(tarkib_id=tarkib_id, tamir_turi_id=tamir_turi_id)
        if not queryset.exists():
            return HttpResponse("Ma'lumot topilmadi", status=404)

        tarkib = queryset.first().tarkib
        tamir_turi = queryset.first().tamir_turi

        wb = Workbook()
        ws = wb.active
        ws.title = "Texnik Ko'riklar"

        ws.merge_cells("A1:G1")
        ws["A1"] = f"{tarkib.tarkib_raqami} — {tamir_turi.tamir_nomi} bo‘yicha texnik ko‘riklar"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        ws.append([])
        ws.append(["Ekspluatatsiya", "Turi", "Raqami", "Masofa", "Holati"])
        ws.append([
            str(tarkib.eksplutatsiya_vaqti or "-"),
            tarkib.turi or "-",
            tarkib.tarkib_raqami or "-",
            getattr(tarkib, "masofa", "-"),
            tarkib.holati or "-",
        ])
        ws.append([])

        ws.append(["#", "Kirgan sana", "Chiqqan sana", "Status", "Kamchiliklar", "Bart. etilgan", "Yaratgan xodim"])
        for i, k in enumerate(queryset, 1):
            ws.append([
                i,
                str(k.kirgan_vaqti or "-"),
                str(k.chiqqan_vaqti or "-"),
                k.status or "-",
                k.kamchiliklar_haqida or "-",
                k.bartaraf_etilgan_kamchiliklar or "-",
                k.created_by.username if k.created_by else "-",
            ])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"{tarkib.tarkib_raqami}_{tamir_turi.tamir_nomi}_koriklar.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

class TexnikKorikStepViewSet1(ViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TexnikKorikStep.objects.select_related(
            "korik__tarkib", "tamir_turi", "created_by"
        ).prefetch_related("ehtiyot_qismlar").all()

    @action(detail=False, methods=["get"], url_path=r"(?P<korik_id>\d+)/export-pdf")
    def export_pdf(self, request, korik_id=None):
        # --- Korikni olish ---
        try:
            korik = TexnikKorik.objects.select_related("tarkib", "tamir_turi").get(id=korik_id)
        except TexnikKorik.DoesNotExist:
            return HttpResponse("Bunday Texnik Ko‘rik topilmadi", status=404)

        # --- Shu korik bo‘yicha barcha steplar ---
        steps = self.get_queryset().filter(korik=korik).order_by("id")
        if not steps.exists():
            return HttpResponse("Bu ko‘rik bo‘yicha steplar topilmadi", status=404)

        buffer = BytesIO()
        response = HttpResponse(content_type="application/pdf")
        filename = f"Korik_{korik.id}_steps.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
        styles = getSampleStyleSheet()
        elements = []

        # --- Title tepa ---
        title_text = (
            f"<b><font color='red'>{korik.tarkib.tarkib_raqami if korik.tarkib else '-'}</font></b> harakat tarkibining "
            f"<b><font color='red'>{korik.created_at.strftime('%d-%m-%Y') if korik.created_at else '-'}</font></b> da o'tkazilgan "
            f"<b><font color='red'>{korik.tamir_turi.tamir_nomi if korik.tamir_turi else '-'}</font></b> texnik ko‘rigi bo'yicha to'liq ma'lumot"
        )
        title = Paragraph(
            title_text, 
            ParagraphStyle('title', parent=styles['Title'], alignment=1, textColor=colors.darkblue)
        )
        elements.append(title)
        elements.append(Spacer(1, 10))

        # --- Tarkib rasmi ---
        if getattr(korik.tarkib, 'image', None):
            try:
                img = Image(korik.tarkib.image.path, width=15.5*cm, height=6.5*cm)
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 10))
            except:
                pass

        # --- Ekspluatatsiya jadvali ---
        ekspl_data = [
            [
                Paragraph(f"<font color='red'><b>{h}</b></font>", styles['Normal'])
                for h in ["Ekspluatatsiyaga qo‘yilgan sana", "Turi", "Nomeri", "Masofa", "Hozirgi holati"]
            ],
            [
                Paragraph(f"<b>{korik.tarkib.ishga_tushgan_vaqti.strftime('%d-%m-%Y') if getattr(korik.tarkib, 'ishga_tushgan_vaqti', None) else '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{korik.tarkib.guruhi if getattr(korik.tarkib, 'guruhi', None) else '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{korik.tarkib.tarkib_raqami if getattr(korik.tarkib, 'tarkib_raqami', None) else '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{korik.tarkib.masofa if getattr(korik.tarkib, 'masofa', None) else '-'}</b>", styles['Normal']),
                Paragraph(f"<b>{korik.tarkib.holati if getattr(korik.tarkib, 'holati', None) else '-'}</b>", styles['Normal']),
            ],
        ]
        full_width = A4[0]-2*cm
        col_widths = [full_width*0.18, full_width*0.18, full_width*0.26, full_width*0.18, full_width*0.20]

        ekspl_table = Table(ekspl_data, hAlign='CENTER', colWidths=col_widths)
        ekspl_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.6, colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ]))
        elements.append(ekspl_table)
        elements.append(Spacer(1, 12))

        # --- Texnik ko‘rik steplari ---
        created_at_str = korik.created_at.strftime('%d-%m-%Y') if getattr(korik, 'created_at', None) else '-'
        tamir_turi_nomi = getattr(korik.tamir_turi, 'tamir_nomi', '-') if getattr(korik, 'tamir_turi', None) else '-'
        tarkib_raqami = getattr(korik.tarkib, 'tarkib_raqami', '-') if getattr(korik, 'tarkib', None) else '-'

        history_title_text = f"<font color='red'>{created_at_str}</font> da o'tkazilgan " \
                            f"<font color='red'>{tamir_turi_nomi}</font> texnik ko'rigi bo'yicha to'liq ma'lumot"
        history_title = Paragraph(
            history_title_text,
            ParagraphStyle('h3', alignment=1, leading=14, textColor=colors.darkblue)
        )
        elements.append(history_title)
        elements.append(Spacer(1, 6))

        # --- Qizil chiziq Title dan keyin ---
        title_line = Table(
            [[""]],
            colWidths=[A4[0] - 2 * cm],
            style=TableStyle([('LINEABOVE', (0,0), (-1,-1), 1, colors.red)])
        )
        elements.append(title_line)
        elements.append(Spacer(1, 6))

        # --- Steplar ---
        for i, step in enumerate(steps, 1):
            created_by = getattr(step.created_by, 'username', '-')
            kamchilik = getattr(step, "kamchiliklar_haqida", '-')

            ehtiyot_qismlar_qs = getattr(step, 'ehtiyot_qismlar', None)
            if ehtiyot_qismlar_qs is not None:
                ehtiyot_qismlar_detail = ", ".join([
                    getattr(eq, 'ehtiyot_qism_nomi', '-') for eq in ehtiyot_qismlar_qs.all()
                ]) or "-"
            else:
                ehtiyot_qismlar_detail = "-"

            step_date = step.created_at.strftime("%d-%m-%Y") if getattr(step, 'created_at', None) else "-"

            # Step matni: {} ichidagilar qizil, qolgan darkblue
            step_text = (
                f"<font color='darkblue'>{tarkib_raqami} harakat tarkibi "
                f"<font color='red'>{step_date}</font> da "
                f"<font color='red'>{created_by}</font> Depo navbatchisi tomonidan "
                f"<font color='red'>{tamir_turi_nomi}</font> texnik ko'rigiga ro'yhatga olindi.<br/><br/>"
                f"Depo navbatchisi aniqlagan kamchiliklar: <font color='red'>{kamchilik}</font><br/>"
                f"Depo navbatchisi ishlatgan ehtiyot qismlar: <font color='red'>{ehtiyot_qismlar_detail}</font>"
                f"</font>"
            )

            p = Paragraph(
                step_text,
                ParagraphStyle('Normal', alignment=1, leading=12)
            )
            elements.append(p)
            elements.append(Spacer(1, 6))

            # --- Chiziq Step dan keyin ---
            step_line = Table(
                [[""]],
                colWidths=[A4[0] - 2 * cm],
                style=TableStyle([('LINEABOVE', (0,0), (-1,-1), 1, colors.red)])
            )
            elements.append(step_line)
            elements.append(Spacer(1, 6))

        # --- Yakuniy matn: AKT ---
        akt_text = f"<font color='darkblue'>Tamir turi <font color='red'>{tamir_turi_nomi}</font> to'liq yakunlanganligi bo'yicha AKT ilova qilindi.</font>"
        akt_para = Paragraph(
            akt_text,
            ParagraphStyle('Normal', alignment=1, leading=12)
        )
        elements.append(Spacer(1, 12))
        elements.append(akt_para)
        elements.append(Spacer(1, 6))



        # --- Footer va QR ---
        qr_url = f"https://depo-main.vercel.app/depo/{korik.tarkib.id if korik.tarkib else 0}"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=3, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_buffer = BytesIO()
        qr.make_image(fill_color="black", back_color="white").save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_img = Image(qr_buffer, width=2.5*cm, height=2.5*cm)
        qr_img.hAlign = 'RIGHT'

        footer_text = Paragraph(
            """<font size=9><b>
            Hujjatning haqiqiyligini tekshirish uchun QR kodni skanerlang.<br/>
            <font color='blue'><b>depo.tm1.uz</b></font> sayti orqali tasdiqlangan.<br/>
            Ushbu hisobotdagi barcha ma’lumotlar uchun xodim mas’uldir.
            </b></font>""",
            ParagraphStyle('footer', parent=styles['Normal'], alignment=0, leading=12),
        )
        footer_table = Table([[footer_text, qr_img]], colWidths=[14*cm, 3*cm])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.lightblue),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 0.8, colors.black),
        ]))
        elements.append(footer_table)

        # --- Border ---
        def draw_border(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1)
            canvas.rect(0.8*cm, 0.8*cm, A4[0]-1.6*cm, A4[1]-1.6*cm)
            canvas.restoreState()

        doc.build(elements, onFirstPage=draw_border, onLaterPages=draw_border)
        buffer.seek(0)
        response.write(buffer.getvalue())
        buffer.close()
        return response


    @action(detail=True, methods=["get"], url_path="export-excel")
    def export_step_excel(self, request, pk=None):
        try:
            korik = TexnikKorik.objects.get(id=pk)
        except TexnikKorik.DoesNotExist:
            return HttpResponse("Bunday Texnik Korik topilmadi", status=404)

        steps = self.get_queryset().filter(korik=korik).order_by("id")
        if not steps.exists():
            return HttpResponse("Bu ko'rik bo'yicha steplar topilmadi", status=404)

        wb = Workbook()
        ws = wb.active
        ws.title = "Texnik Ko'rik Steplar"

        ws.append(["#", "Tarkib raqami", "Tamir turi", "Kamchiliklar", "Ehtiyot qismlar", "Step yozgan", "Sana"])

        for i, step in enumerate(steps, 1):
            tarkib_raqami = getattr(getattr(step.korik, 'tarkib', None), 'tarkib_raqami', '-')
            tamir_turi = getattr(step.tamir_turi, 'tamir_nomi', '-')
            kamchilik = step.kamchiliklar_haqida or "-"
            ehtiyot_qismlar_detail = ", ".join([getattr(eq, 'ehtiyot_qism_nomi', '-') for eq in step.ehtiyot_qismlar.all()]) or "-"
            created_by = getattr(step.created_by, 'username', '-')
            step_date = step.created_at.strftime("%d-%m-%Y") if step.created_at else "-"

            ws.append([
                i,
                tarkib_raqami,
                tamir_turi,
                kamchilik,
                ehtiyot_qismlar_detail,
                created_by,
                step_date
            ])

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="Korik_{korik.id}_steps.xlsx"'
        wb.save(response)
        return response

    
    
    
    
    
class TexnikKorikJadvalViewSet(viewsets.ModelViewSet):
    queryset = TexnikKorikJadval.objects.select_related("tarkib", "tamir_turi", "created_by")
    serializer_class = TexnikKorikJadvalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ["tarkib__tarkib_raqami", "tamir_turi__tamir_nomi"]
    filterset_fields = ["tarkib", "tamir_turi", "sana"]
    ordering_fields = ["sana", "created_at"]
    
    
    def get_queryset(self):
        return (
            TexnikKorikJadval.objects
            .select_related("tarkib", "tamir_turi", "created_by")
            .filter(tarkib__is_active=True)
    )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        
        
    @action(detail=False, methods=["get"])
    def export_excel(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        data = [
            {
                "Tarkib": j.tarkib.tarkib_raqami,
                "Depo": j.tarkib.depo.qisqacha_nomi if j.tarkib.depo else "",
                "Tamir turi": j.tamir_turi.tamir_nomi,
                "Sana": j.sana.strftime("%d.%m.%Y"),
                "Yaratgan": j.created_by.username if j.created_by else "",
            }
            for j in queryset
        ]
        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_excel(output, index=False)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="texnik_korik_jadval.xlsx"'
        return response

    @action(detail=False, methods=["get"])
    def export_pdf(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()
        data = [["Tarkib", "Depo", "Tamir turi", "Sana", "Yaratgan"]]
        for j in queryset:
            data.append([
                j.tarkib.tarkib_raqami,
                j.tarkib.depo.qisqacha_nomi if j.tarkib.depo else "",
                j.tamir_turi.tamir_nomi,
                j.sana.strftime("%d.%m.%Y"),
                j.created_by.username if j.created_by else "",
            ])
        table = Table(data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        doc.build([Paragraph("Texnik ko‘rik jadvali", styles["Title"]), table])
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="texnik_korik_jadval.pdf"'
        return response

    
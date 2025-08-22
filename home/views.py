from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from rest_framework import status
from .models import (
    TamirTuri, ElektroDepo, EhtiyotQismlari,
    HarakatTarkibi, TexnikKorik, CustomUser,Nossozliklar
)
from .serializers import (
    TamirTuriSerializer, ElektroDepoSerializer,
    EhtiyotQismlariSerializer, HarakatTarkibiSerializer,
    TexnikKorikSerializer, UserSerializer, NossozliklarSerializer
)
from .permissions import (
    CustomPermission
) 
from django.contrib.auth import authenticate

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated] 


class BaseViewSet(viewsets.ModelViewSet):
    
    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_pdf(self, request):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{self.basename}.pdf"'

        p = canvas.Canvas(response)
        p.setFont("Helvetica", 12)
        p.drawString(100, 800, f"{self.basename} ro'yxati:")

        y = 780
        for obj in self.get_queryset():
            p.drawString(100, y, str(obj))
            y -= 20

        p.showPage()
        p.save()
        return response

class TamirTuriViewSet(BaseViewSet):
    queryset = TamirTuri.objects.all()
    serializer_class = TamirTuriSerializer
    basename = "Tamir Turi"
    permission_classes = [IsAuthenticated, CustomPermission]


class ElektroDepoViewSet(BaseViewSet):
    queryset = ElektroDepo.objects.all()
    serializer_class = ElektroDepoSerializer
    basename = "Elektro Depo"
    permission_classes = [IsAuthenticated, CustomPermission]


class EhtiyotQismlariViewSet(BaseViewSet):
    queryset = EhtiyotQismlari.objects.all()
    serializer_class = EhtiyotQismlariSerializer
    basename = "Ehtiyot Qismlari"
    permission_classes = [IsAuthenticated, CustomPermission]


class HarakatTarkibiViewSet(BaseViewSet):
    queryset = HarakatTarkibi.objects.all()
    serializer_class = HarakatTarkibiSerializer
    basename = "Harakat Tarkibi"
    permission_classes = [IsAuthenticated, CustomPermission]

class TexnikKorikViewSet(BaseViewSet):
    queryset = TexnikKorik.objects.all()
    serializer_class = TexnikKorikSerializer
    permission_classes = [IsAuthenticated, CustomPermission]

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


class NossozliklarViewSet(BaseViewSet):
    queryset = Nossozliklar.objects.all()
    serializer_class = NossozliklarSerializer
    permission_classes = [IsAuthenticated, CustomPermission]

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
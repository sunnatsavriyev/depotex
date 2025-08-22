from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("monitoring", "Monitoring"),
        ("texnik", "Texnik"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.username} - {self.role}"


class TamirTuri(models.Model):
    tamir_nomi = models.CharField(max_length=255)
    tamirlash_davri = models.CharField(
        max_length=50,
        help_text="Masofa bo‘yicha: 5505 ± 10 km"
    )
    tamirlanish_vaqti = models.CharField(
        max_length=50,
        help_text="Masalan: 1 soat, 6 oy, 30 daqiqa",
        default="1 soat"
    )

    def __str__(self):
        return self.tamir_nomi


class ElektroDepo(models.Model):
    depo_nomi = models.CharField(max_length=255)
    qisqacha_nomi = models.CharField(max_length=50)
    joylashuvi = models.CharField(max_length=255)

    def __str__(self):
        return self.depo_nomi


class EhtiyotQismlari(models.Model):
    ehtiyotqism_nomi = models.CharField(max_length=255)
    nomenklatura_raqami = models.CharField(max_length=100)

    def __str__(self):
        return self.ehtiyotqism_nomi


class HarakatTarkibi(models.Model):
    depo = models.ForeignKey(ElektroDepo, on_delete=models.CASCADE, related_name="tarkiblar")
    guruhi = models.CharField(max_length=100)
    turi = models.CharField(max_length=100)
    tarkib_raqami = models.CharField(max_length=100, unique=True)
    ishga_tushgan_vaqti = models.DateField()
    eksplutatsiya_vaqti = models.IntegerField(help_text="Oylar sonida")
    image = models.ImageField(upload_to="tarkiblar/", blank=True, null=True)
    holati = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.tarkib_raqami} - {self.turi}" 


class TexnikKorik(models.Model):
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.CASCADE, related_name="koriklar")
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari', on_delete=models.CASCADE, related_name="koriklar")
    tarkib = models.ForeignKey('HarakatTarkibi', on_delete=models.CASCADE, related_name="koriklar")
    kirgan_vaqti = models.DateTimeField(default=timezone.now)
    chiqqan_vaqti = models.DateTimeField(default=timezone.now)
    kamchiliklar = models.TextField()

    def __str__(self):
        return f"{self.tarkib} - {self.kirgan_vaqti}"


class Nossozliklar(models.Model):
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari', on_delete=models.CASCADE, related_name="nosozliklar")
    tarkib = models.ForeignKey('HarakatTarkibi', on_delete=models.CASCADE, related_name="nosozliklar")
    nosozliklar = models.TextField()
    aniqlangan_vaqti = models.DateTimeField(default=timezone.now)         
    bartarafqilingan_vaqti = models.DateTimeField(default=timezone.now)   

    def __str__(self):
        return f"{self.tarkib} - {self.aniqlangan_vaqti}"

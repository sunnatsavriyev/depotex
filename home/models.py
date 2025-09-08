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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tamir_nomi


class ElektroDepo(models.Model):
    depo_nomi = models.CharField(max_length=255)
    qisqacha_nomi = models.CharField(max_length=50)
    joylashuvi = models.CharField(max_length=255)
    image = models.ImageField(upload_to="depo/", blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.depo_nomi
    

class EhtiyotQismlari(models.Model):
    ehtiyotqism_nomi = models.CharField(max_length=255, unique=True)
    nomenklatura_raqami = models.CharField(max_length=100)
    birligi = models.CharField(
        max_length=50,
        choices=[
            ("dona", "Dona"),
            ("para", "Para"),
            ("metr", "Metr"),
            ("litr", "Litr"),
        ],
        default="dona"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.ehtiyotqism_nomi} ({self.birligi})"


# ✅ ManyToMany uchun oraliq jadval
class TexnikKorikEhtiyotQism(models.Model):
    korik = models.ForeignKey("TexnikKorik", on_delete=models.CASCADE)
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.CASCADE)
    miqdor = models.PositiveIntegerField(default=1)  # masalan 3 litr yoki 2 dona

    def __str__(self):
        return f"{self.ehtiyot_qism.ehtiyotqism_nomi} - {self.miqdor} {self.ehtiyot_qism.birligi}"

    def save(self, *args, **kwargs):
        # Bu yerda kerak bo‘lsa miqdorni tekshirish yoki avtomatik formatlash
        # Masalan, agar moy bo‘lsa, avtomatik "litr" qo‘shish
        if self.ehtiyot_qism.birligi.lower() == "litr" and not isinstance(self.miqdor, float):
            self.miqdor = float(self.miqdor)  # yoki boshqa formatlash
        super().save(*args, **kwargs)


class NosozlikEhtiyotQism(models.Model):
    nosozlik = models.ForeignKey("Nosozliklar", on_delete=models.CASCADE)
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.CASCADE)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.ehtiyot_qism.ehtiyotqism_nomi} - {self.miqdor} {self.ehtiyot_qism.birligi}"

    def save(self, *args, **kwargs):
        # Agar kerak bo'lsa, miqdorni float qilish yoki maxsus formatlash
        if self.ehtiyot_qism.birligi.lower() == "litr" and not isinstance(self.miqdor, float):
            self.miqdor = float(self.miqdor)
        super().save(*args, **kwargs)




class HarakatTarkibi(models.Model):
    depo = models.ForeignKey(ElektroDepo, on_delete=models.CASCADE, related_name="tarkiblar")
    guruhi = models.CharField(max_length=100)
    turi = models.CharField(max_length=100)
    tarkib_raqami = models.CharField(max_length=100, unique=True)
    ishga_tushgan_vaqti = models.DateField()
    eksplutatsiya_vaqti = models.BigIntegerField(help_text="km da")
    image = models.ImageField(upload_to="tarkiblar/", blank=True, null=True)

    CHOICES = [
        ("Soz_holatda", "Soz_holatda"),
        ("Texnik_korikda", "Texnik_korikda"),
        ("Nosozlikda", "Nosozlikda"),
    ]
    holati = models.CharField(choices=CHOICES, max_length=100, default="Soz_holatda")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tarkib_raqami} - {self.turi} ({self.holati})"




class TexnikKorik(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Texnik_korikda", "Texnik_korikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    tarkib = models.ForeignKey('HarakatTarkibi', on_delete=models.CASCADE, related_name="koriklar")
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True, related_name="koriklar")
    ehtiyot_qismlar = models.ManyToManyField(
        "EhtiyotQismlari",
        through="TexnikKorikEhtiyotQism",
        related_name="koriklar",
        blank=True
    )
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)

    kirgan_vaqti = models.DateTimeField(default=timezone.now)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)

    akt_file = models.FileField(upload_to="korik_aktlar/", null=True, blank=True)  
    image = models.ImageField(upload_to="korik_images/", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='kirgan_foydalanuvchilar'
    )
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.kirgan_vaqti = timezone.now()
            self.status = TexnikKorik.Status.JARAYONDA
            self.tarkib.holati = "Texnik_korikda"
            self.tarkib.save()
        else:
            old = TexnikKorik.objects.filter(id=self.id).first()
            if old:
                self.kirgan_vaqti = old.kirgan_vaqti

        # ✅ faqat tugatish bosilganda akt fayl yuklanadi
        if self.akt_file and self.status != TexnikKorik.Status.BARTARAF_ETILDI:
            self.status = TexnikKorik.Status.BARTARAF_ETILDI
            self.chiqqan_vaqti = timezone.now()
            self.tarkib.holati = "Soz_holatda"
            self.tarkib.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tarkib} — {self.status} ({self.created_by})"
    
    @property
    def ehtiyot_qismlar_miqdor(self):
        """
        List of spare parts with quantity and unit.
        """
        result = []
        for eq in self.ehtiyot_qismlar.all():
            through_obj = TexnikKorikEhtiyotQism.objects.get(korik=self, ehtiyot_qism=eq)
            result.append(f"{eq.ehtiyotqism_nomi} - {through_obj.miqdor} {eq.birligi}")
        return result





class Nosozliklar(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Nosozlikda", "Nosozlikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    ehtiyot_qismlar = models.ManyToManyField(
        "EhtiyotQismlari",
        through="NosozlikEhtiyotQism",
        related_name="nosozliklar",
        blank=True
    )
    tarkib = models.ForeignKey('HarakatTarkibi', on_delete=models.CASCADE, related_name="nosozliklar")
    nosozliklar_haqida = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)

    aniqlangan_vaqti = models.DateTimeField(default=timezone.now)         
    bartarafqilingan_vaqti = models.DateTimeField(null=True, blank=True)

    bartaraf_etilgan_nosozliklar = models.TextField(blank=True, help_text="Bartaraf etilish jarayonida bajarilgan ishlar")
    image = models.ImageField(upload_to="nosozlik_images/", blank=True)
    akt_file = models.FileField(upload_to="nosozlik_aktlar/", null=True, blank=True) 

    created_by = models.ForeignKey("CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.dastlabki_holat = self.tarkib.holati
            self.status = Nosozliklar.Status.JARAYONDA
            self.tarkib.holati = "Nosozlikda"
            self.tarkib.save()

        # ✅ tugatishda akt fayl yuklanadi
        if self.akt_file and self.status != Nosozliklar.Status.BARTARAF_ETILDI:
            if not self.bartaraf_etilgan_nosozliklar:
                raise ValueError("Nosozlik tugatish uchun 'bartaraf etilgan nosozliklar' yozilishi shart.")
            self.status = Nosozliklar.Status.BARTARAF_ETILDI
            self.bartarafqilingan_vaqti = timezone.now()
            self.tarkib.holati = "Soz_holatda"
            self.tarkib.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tarkib} - {self.status} ({self.created_by})"

    @property
    def ehtiyot_qismlar_miqdor(self):
        result = []
        for eq in self.ehtiyot_qismlar.all():
            through_obj = NosozlikEhtiyotQism.objects.get(nosozlik=self, ehtiyot_qism=eq)
            result.append(f"{eq.ehtiyotqism_nomi} - {through_obj.miqdor} {eq.birligi}")
        return result

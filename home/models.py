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

    depo = models.ForeignKey(
        "ElektroDepo",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="users"
    )

    def __str__(self):
        return f"{self.username} - {self.role} ({self.depo.qisqacha_nomi if self.depo else 'Depo yo‘q'})"



class TamirTuri(models.Model):
    tamir_nomi = models.CharField(max_length=255)

    # masofa uchun
    tamirlash_davri = models.CharField(
        max_length=50,
        help_text="Masofa bo‘yicha: 5505 ± 10 km"
    )

    # vaqt uchun
    Vaqt_Choices = [
        ("soat", "Soat"),
        ("kun", "Kun"),
        ("oy", "Oy"),
    ]
    tamirlanish_miqdori = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Vaqt soni: masalan, 4"
    )
    tamirlanish_vaqti = models.CharField(
        max_length=10,
        choices=Vaqt_Choices,
        help_text="Vaqt birligi: soat/kun/oy"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Masalan: "To-1 (5000 km, 4 soat)"
        return f"{self.tamir_nomi} ({self.tamirlash_davri}, {self.tamirlanish_miqdori} {self.tamirlanish_vaqti})"


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
    korik = models.ForeignKey('TexnikKorik',on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari',on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.korik} - {self.ehtiyot_qism} ({self.miqdor})"



class TexnikKorikEhtiyotQismStep(models.Model):
    korik_step = models.ForeignKey('TexnikKorikStep',on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari',on_delete=models.SET_NULL, null=True, blank=True)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.korik_step} - {self.ehtiyot_qism} ({self.miqdor})"
        







class HarakatTarkibi(models.Model):
    depo = models.ForeignKey(ElektroDepo, related_name="tarkiblar", on_delete=models.SET_NULL, null=True, blank=True)
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
    
    
    
class KunlikYurish(models.Model):
    tarkib = models.ForeignKey(
        HarakatTarkibi,
        on_delete=models.SET_NULL,
        null=True,
        related_name="kunlik_yurishlar"
    )
    sana = models.DateField(default=timezone.now)
    kilometr = models.PositiveIntegerField(help_text="Yurilgan km")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sana", "-id"]

    def __str__(self):
        return f"{self.tarkib.tarkib_raqami} - {self.sana} - {self.kilometr} km"
 


class TexnikKorik(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Texnik_korikda", "Texnik_korikda"
        BARTARAF_ETILDI = "Soz_holatda", "Soz_holatda"

    tarkib = models.ForeignKey('HarakatTarkibi',on_delete=models.SET_NULL, null=True, blank=True,related_name="koriklar")
    tamir_turi = models.ForeignKey('TamirTuri',on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)
    ehtiyot_qismlar = models.ManyToManyField("EhtiyotQismlari", through="TexnikKorikEhtiyotQism", blank=True)
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)
    kirgan_vaqti = models.DateTimeField(default=timezone.now)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)
    akt_file = models.FileField(upload_to="texnik_korik_aktlar/", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    yakunlash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # 🔹 Yangi korik ochilsa
        if not self.id:
            ongoing = TexnikKorik.objects.filter(
                tarkib=self.tarkib,
                status=TexnikKorik.Status.JARAYONDA
            )
            if ongoing.exists():
                raise ValueError("Bu tarkib bo'yicha yakunlanmagan texnik ko'rik mavjud!")

            self.kirgan_vaqti = timezone.now()
            self.status = TexnikKorik.Status.JARAYONDA

            # ✅ Tarkibni "Texnik_korikda" holatiga o'tkazamiz
            self.tarkib.holati = "Texnik_korikda"
            self.tarkib.save()

        else:
            # eski yozuvni olib kelamiz
            old = TexnikKorik.objects.filter(id=self.id).first()
            if old:
                self.kirgan_vaqti = old.kirgan_vaqti

        # 🔹 Korikni yakunlash
        if self.yakunlash:
            if not self.chiqqan_vaqti or not self.akt_file:
                raise ValueError("Yakunlash uchun chiqish vaqti va akt fayl majburiy!")

            if self.status != TexnikKorik.Status.BARTARAF_ETILDI:
                self.status = TexnikKorik.Status.BARTARAF_ETILDI
                # ✅ Yakunlanganda tarkibni "Soz_holatda" qilamiz
                self.tarkib.holati = "Soz_holatda"
                self.tarkib.save()

        super().save(*args, **kwargs)


class TexnikKorikStep(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Jarayonda", "Jarayonda"
        BARTARAF_ETILDI = "Yakunlandi", "Yakunlandi"
    korik = models.ForeignKey(TexnikKorik, on_delete=models.SET_NULL,null=True, blank=True, related_name="steps")
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qismlar = models.ManyToManyField(
    "EhtiyotQismlari",
    through="TexnikKorikEhtiyotQismStep",
    blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.JARAYONDA
    )
    kamchiliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_kamchiliklar = models.TextField(blank=True)
    akt_file = models.FileField(upload_to="akt/", null=True, blank=True)
    chiqqan_vaqti = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Step qo'shish faqat yakunlanmagan korikka
        if self.korik.status == TexnikKorik.Status.BARTARAF_ETILDI:
            raise ValueError("Bu korik yakunlangan, yangi step qo'shib bo'lmaydi!")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Step: {self.korik.tarkib} — {self.created_by}"



class NosozlikEhtiyotQismStep(models.Model):
    step = models.ForeignKey('NosozlikStep', on_delete=models.SET_NULL,null=True, blank=True, related_name="ehtiyot_qismlar_step")
    ehtiyot_qism = models.ForeignKey('EhtiyotQismlari', on_delete=models.SET_NULL,null=True, blank=True,)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.step} - {self.ehtiyot_qism.ehtiyotqism_nomi} ({self.miqdor} {self.ehtiyot_qism.birligi})"



class NosozlikEhtiyotQism(models.Model):
    nosozlik = models.ForeignKey("Nosozliklar", on_delete=models.SET_NULL,null=True, blank=True, related_name="ehtiyot_qism_aloqalari")
    ehtiyot_qism = models.ForeignKey("EhtiyotQismlari", on_delete=models.SET_NULL,null=True, blank=True,)
    miqdor = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.ehtiyot_qism.ehtiyotqism_nomi} - {self.miqdor} {self.ehtiyot_qism.birligi}"

    def save(self, *args, **kwargs):
        # Agar kerak bo'lsa, miqdorni float qilish yoki maxsus formatlash
        if self.ehtiyot_qism.birligi.lower() == "litr" and not isinstance(self.miqdor, float):
            self.miqdor = float(self.miqdor)
        super().save(*args, **kwargs)



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
    tarkib = models.ForeignKey('HarakatTarkibi', on_delete=models.SET_NULL,null=True, blank=True, related_name="nosozliklar")
    nosozliklar_haqida = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.JARAYONDA, editable=False)

    aniqlangan_vaqti = models.DateTimeField(default=timezone.now)         
    bartarafqilingan_vaqti = models.DateTimeField(null=True, blank=True)

    bartaraf_etilgan_nosozliklar = models.TextField(blank=True, help_text="Bartaraf etilish jarayonida bajarilgan ishlar")
    image = models.ImageField(upload_to="nosozlik_images/", blank=True)
    akt_file = models.FileField(upload_to="nosozlik_aktlar/", null=True, blank=True) 

    created_by = models.ForeignKey("CustomUser", on_delete=models.SET_NULL, null=True, blank=True)
    yakunlash = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # yangi yozuv bo‘lsa
        if not self.id:
            self.aniqlangan_vaqti = timezone.now()
            self.status = Nosozliklar.Status.JARAYONDA
            self.tarkib.holati = "Nosozlikda"
            self.tarkib.save()
        else:
            old = Nosozliklar.objects.filter(id=self.id).first()
            if old:
                self.aniqlangan_vaqti = old.aniqlangan_vaqti

        # ✅ yakunlash sharti
        if self.yakunlash:
            if not self.bartarafqilingan_vaqti or not self.akt_file:
                raise ValueError("Yakunlash uchun bartaraf etilgan vaqt va akt fayl majburiy!")
            if self.status != Nosozliklar.Status.BARTARAF_ETILDI:
                self.status = Nosozliklar.Status.BARTARAF_ETILDI
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




class NosozlikStep(models.Model):
    class Status(models.TextChoices):
        JARAYONDA = "Jarayonda", "Jarayonda"
        BARTARAF_ETILDI = "Yakunlandi", "Yakunlandi"

    nosozlik = models.ForeignKey(Nosozliklar, on_delete=models.SET_NULL,null=True, blank=True, related_name="steps")
    tamir_turi = models.ForeignKey('TamirTuri', on_delete=models.SET_NULL, null=True, blank=True)
    ehtiyot_qismlar = models.ManyToManyField(
        'EhtiyotQismlari',
        through='NosozlikEhtiyotQismStep',
        blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.JARAYONDA)
    nosozliklar_haqida = models.TextField(blank=True)
    bartaraf_etilgan_nosozliklar = models.TextField(blank=True)
    akt_file = models.FileField(upload_to='nosozlik_step_aktlar/', null=True, blank=True)
    bartaraf_qilingan_vaqti = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Step faqat yakunlanmagan nosozliklarga qo‘shiladi
        if self.nosozlik.status == Nosozliklar.Status.BARTARAF_ETILDI:
            raise ValueError("Bu nosozlik yakunlangan, yangi step qo'shib bo'lmaydi!")

        # Agar step yakunlanayotgan bo‘lsa
        if self.bartaraf_qilingan_vaqti and self.akt_file:
            self.status = self.Status.BARTARAF_ETILDI

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nosozlik.tarkib} — Step ({self.status})"